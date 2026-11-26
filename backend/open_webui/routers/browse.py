import asyncio
import contextlib
import time
from typing import Annotated

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, StringConstraints

from open_webui.utils.auth import bearer_security, get_verified_user
from open_webui.utils.browse import (
    BINDING_ID,
    MAX_WS_MESSAGE,
    RECONNECT_WINDOW,
    SOCKET_PROTOCOL,
    BrowseSocket,
    require_login_claims,
    token_matches,
)

router = APIRouter()


class BindForm(BaseModel):
    deviceId: Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9_-]{16,128}$')]
    extensionOrigin: str


@router.post('/bind')
async def bind_browser(
    request: Request,
    response: Response,
    form: BindForm,
    user=Depends(get_verified_user),
    auth=Depends(bearer_security),
):
    manager = request.app.state.browse
    manager.require_enabled()
    if auth is None or getattr(request.state, 'auth_type', None) != 'jwt':
        raise HTTPException(401, 'Open WebUI Bearer token is required')
    if form.extensionOrigin not in manager.origins:
        raise HTTPException(403, 'browse_origin_denied')
    claims = require_login_claims(request, user.id)
    binding, pair_code = await manager.bind(user.id, form.deviceId, claims)
    response.headers['Cache-Control'] = 'no-store'
    return {
        'bindingId': binding.id,
        'socketToken': binding.socket_token,
        'pairCode': pair_code,
        'userId': binding.user_id,
        'relayPort': binding.port,
    }


@router.delete('/bind/{binding_id}', status_code=204)
async def revoke_browser(request: Request, binding_id: str, auth=Depends(bearer_security)):
    manager = request.app.state.browse
    manager.require_enabled()
    if auth is None:
        raise HTTPException(401, 'Browse socket Bearer token is required')
    binding = manager.get(binding_id)
    if binding is not None:
        if not token_matches(auth.credentials, binding.socket_token):
            raise HTTPException(403, 'Invalid Browse socket token')
        manager.retire(binding)
    return Response(status_code=204)


async def extension_to_relay(websocket, upstream):
    while True:
        message = await websocket.receive()
        if message['type'] == 'websocket.disconnect':
            return 1000
        text = message.get('text')
        data = message.get('bytes')
        if text is not None:
            await upstream.send_str(text)
        elif data is not None:
            await upstream.send_bytes(data)


async def relay_to_extension(upstream, websocket):
    while True:
        message = await upstream.receive()
        if message.type == aiohttp.WSMsgType.TEXT:
            await websocket.send_text(message.data)
        elif message.type == aiohttp.WSMsgType.BINARY:
            await websocket.send_bytes(message.data)
        elif message.type == aiohttp.WSMsgType.CLOSE:
            return message.data if message.data not in (0, 1005, 1006, 1015) else 1000
        elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.ERROR):
            return 1011


@router.websocket('/socket/{binding_id}')
async def browser_socket(websocket: WebSocket, binding_id: str):
    manager = websocket.app.state.browse
    origin = websocket.headers.get('origin')
    if manager.session is None or manager.closed or origin not in manager.origins or not BINDING_ID.fullmatch(binding_id):
        await websocket.close(code=1008)
        return

    binding = manager.get(binding_id)
    if binding is None:
        await websocket.close(code=1008)
        return
    protocol = next(
        (
            value
            for value in websocket.scope.get('subprotocols', [])
            if value.startswith(SOCKET_PROTOCOL) and token_matches(value[len(SOCKET_PROTOCOL) :], binding.socket_token)
        ),
        None,
    )
    if protocol is None:
        await websocket.close(code=1008)
        return
    try:
        valid = await manager.validate_binding(binding)
    except HTTPException as exc:
        if exc.detail != 'browse_auth_unavailable':
            raise
        await websocket.accept(subprotocol=protocol)
        await websocket.close(code=1013)
        return
    if not valid or binding.socket is not None:
        await websocket.close(code=1008)
        return

    current = BrowseSocket()
    binding.socket = current
    accepted = False
    close_code = 1011
    tasks = []
    try:
        async with asyncio.timeout(5):
            current.upstream = await manager.session.ws_connect(
                f'{binding.url}/extension', origin=origin, max_msg_size=MAX_WS_MESSAGE
            )
        if not manager.socket_live(binding, current):
            close_code = 4006
            return
        await websocket.accept(subprotocol=protocol)
        accepted = True
        binding.connected_once = True
        tasks = [
            asyncio.create_task(extension_to_relay(websocket, current.upstream)),
            asyncio.create_task(relay_to_extension(current.upstream, websocket)),
            asyncio.create_task(current.disconnected.wait()),
        ]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if current.disconnected.is_set():
            close_code = 4006
        else:
            for task in reversed(tasks[:2]):
                if task in done:
                    close_code = task.result()
                    break
    except (aiohttp.ClientError, OSError, RuntimeError, TimeoutError, WebSocketDisconnect):
        pass
    finally:
        current.disconnected.set()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if current.upstream is not None:
            with contextlib.suppress(aiohttp.ClientError, OSError, TimeoutError):
                async with asyncio.timeout(2):
                    await current.upstream.close()
        if binding.socket is current:
            binding.socket = None
            if accepted:
                binding.offline_until = time.monotonic() + RECONNECT_WINDOW
        with contextlib.suppress(OSError, RuntimeError, WebSocketDisconnect):
            await websocket.close(code=close_code)
