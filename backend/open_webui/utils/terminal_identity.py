"""终端请求的会话归属验证和工作区签名。"""

import base64
import hashlib
import hmac
import json
import time

from fastapi import HTTPException
from open_webui.models.chats import Chats
from open_webui.utils.chat_id import is_saved_chat_id, is_temporary_chat_id
from open_webui.utils.headers import normalize_bearer_token

_WORKSPACE_HEADERS = {'x-user-id', 'x-session-id', 'x-workspace-context', 'x-workspace-signature'}


async def verify_terminal_chat_access(request, user, chat_id: str) -> None:
    if not isinstance(chat_id, str) or not chat_id.strip() or len(chat_id.encode('utf-8')) > 1024:
        raise HTTPException(status_code=400, detail='A valid terminal chat is required')
    if is_temporary_chat_id(chat_id):
        from open_webui.utils.chat import get_temporary_chat

        owner = await get_temporary_chat(request.app.state.redis, chat_id)
        if owner and owner.get('user_id') == user.id:
            return
    elif is_saved_chat_id(chat_id):
        if await Chats.is_chat_owner(chat_id, user.id) or await Chats.get_accessible_chat_by_id(
            chat_id, user, permission='write'
        ):
            return
    elif chat_id.startswith('channel:'):
        from open_webui.models.access_grants import AccessGrants
        from open_webui.models.channels import Channels

        channel = await Channels.get_channel_by_id(chat_id.removeprefix('channel:'))
        if channel and (
            user.role == 'admin'
            or (
                await Channels.is_user_channel_member(channel.id, user.id)
                if channel.type in {'group', 'dm'}
                else await AccessGrants.has_access(
                    user_id=user.id, resource_type='channel', resource_id=channel.id, permission='write'
                )
            )
        ):
            return
    raise HTTPException(status_code=404, detail='Chat expired or unavailable')


async def terminal_identity_headers(request, connection: dict, user, chat_id: str | None, headers: dict) -> dict:
    """覆盖身份头；有效会话使用现有 Bearer 密钥签发短时工作区凭证。"""
    result = {key: value for key, value in headers.items() if key.lower() not in _WORKSPACE_HEADERS}
    result['X-User-Id'] = user.id
    if not chat_id:
        return result
    await verify_terminal_chat_access(request, user, chat_id)
    result['X-Session-Id'] = chat_id
    if connection.get('server_type') == 'orchestrator' or connection.get('policy_id'):
        return result
    if connection.get('auth_type', 'bearer') != 'bearer':
        return result
    key = normalize_bearer_token(connection.get('key', ''))
    if not key:
        return result
    payload = json.dumps(
        {'v': 1, 'user': user.id, 'chat': chat_id, 'exp': int(time.time()) + 300},
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')
    context = base64.urlsafe_b64encode(payload).decode('ascii').rstrip('=')
    result['X-Workspace-Context'] = context
    result['X-Workspace-Signature'] = hmac.new(
        key.encode('utf-8'), b'open-terminal/workspace/v1\0' + context.encode('ascii'), hashlib.sha256
    ).hexdigest()
    return result
