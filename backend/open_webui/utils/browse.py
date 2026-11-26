import asyncio
import contextlib
import json
import logging
import os
import re
import secrets
import socket
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
from fastapi import HTTPException

from open_webui.utils.auth import get_verified_user_by_id, is_valid_token

log = logging.getLogger(__name__)

BINDING_ID = re.compile(r'[A-Za-z0-9_-]{43}')
SOCKET_PROTOCOL = 'openwebui-browse.'
PAIR_WINDOW = 5 * 60
RECONNECT_WINDOW = 3 * 60
BINDING_LIFETIME = 24 * 60 * 60
MAX_BINDINGS = 32
MAX_USER_BINDINGS = 4
MAX_USER_PAIRING = 2
MAX_WS_MESSAGE = 64 * 1024 * 1024
MAX_HANDOFF_SECONDS = 600
HANDOFF_TOOLS = {'handoff', 'demonstrate'}
BROWSE_TOOLS = {
    'status', 'tabs', 'navigate', 'snapshot', 'screenshot', 'screenshot_diff', 'console', 'network',
    'click', 'fill', 'type', 'press', 'select', 'hover', 'drag', 'scroll', 'wait_for', 'dialog',
    'eval', 'emulate', 'webmcp',
    *HANDOFF_TOOLS,
}


def require_login_claims(request, user_id):
    claims = getattr(request.state, 'claims', None) or {}
    sid = claims.get('sid')
    if (
        getattr(request.state, 'auth_type', None) != 'jwt'
        or claims.get('id') != user_id
        or claims.get('typ') != 'session'
        or not isinstance(sid, str)
        or not sid
    ):
        raise HTTPException(403, 'browse_session_invalid')
    return claims


def multiple_workers_configured():
    for variable in ('UVICORN_WORKERS', 'WEB_CONCURRENCY'):
        try:
            if int(os.getenv(variable, '')) > 1:
                return True
        except ValueError:
            continue
    return False


def token_matches(value: str, expected: str) -> bool:
    return value.isascii() and secrets.compare_digest(value, expected)


async def stop_process(process):
    if process and process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()


@dataclass(eq=False)
class BrowseSocket:
    disconnected: asyncio.Event = field(default_factory=asyncio.Event)
    upstream: aiohttp.ClientWebSocketResponse | None = None


@dataclass(eq=False)
class Binding:
    id: str
    socket_token: str
    user_id: str
    device_id: str
    login_claims: dict
    home: tempfile.TemporaryDirectory
    port: int
    process: asyncio.subprocess.Process | None = None
    relay_token: str = ''
    pair_code: str = ''
    expires_at: float = 0
    connected_once: bool = False
    offline_until: float = 0
    socket: BrowseSocket | None = None
    cleanup: asyncio.Task | None = None

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}'

    @property
    def live(self):
        now = time.monotonic()
        token_expiry = self.login_claims.get('exp')
        return (
            self.cleanup is None
            and self.process is not None
            and self.process.returncode is None
            and now < self.expires_at
            and (token_expiry is None or time.time() < token_expiry)
            and (self.socket is not None or now < self.offline_until)
        )


class BrowseManager:
    def __init__(self, redis=None):
        self.redis = redis
        self.binary = os.getenv('BROWSE_BINARY', '').strip()
        self.session = None
        self.bindings = {}
        self.devices = {}
        self.starting = {}
        self.cleanups = set()
        self.sweeper = None
        self.closed = False

    async def start(self):
        if multiple_workers_configured():
            if self.binary:
                log.warning('Browse requires a single WebUI worker and has been disabled')
            return
        if self.binary:
            self.session = aiohttp.ClientSession(trust_env=False)
            self.sweeper = asyncio.create_task(self.sweep())

    def require_enabled(self):
        if self.session is None or self.closed:
            raise HTTPException(503, 'Browse is disabled')

    async def close(self):
        self.closed = True
        if self.sweeper:
            self.sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.sweeper
        if self.starting:
            await asyncio.gather(*self.starting.values(), return_exceptions=True)
        for binding in list(self.bindings.values()):
            self.retire(binding)
        if self.cleanups:
            await asyncio.gather(*self.cleanups)
        if self.session:
            await self.session.close()

    async def sweep(self):
        while True:
            await asyncio.sleep(10)
            await asyncio.gather(*(self.check_idle_binding(binding) for binding in list(self.bindings.values())))

    async def check_idle_binding(self, binding):
        try:
            await self.validate_binding(binding)
        except HTTPException as exc:
            if exc.detail != 'browse_auth_unavailable':
                raise

    async def login_is_valid(self, claims):
        expiry = claims.get('exp')
        if expiry is not None and time.time() >= expiry:
            return False
        try:
            async with asyncio.timeout(3):
                return bool(
                    await is_valid_token(claims, self.redis, require_revocation_check=True)
                    and await get_verified_user_by_id(claims['id'])
                )
        except Exception as exc:
            log.warning('Could not verify Browse login session', exc_info=True)
            raise HTTPException(503, 'browse_auth_unavailable') from exc

    async def validate_binding(self, binding):
        if not binding.live or not await self.login_is_valid(binding.login_claims):
            self.retire(binding)
            return False
        return binding.live

    def retire(self, binding):
        if binding.cleanup:
            return binding.cleanup
        self.bindings.pop(binding.id, None)
        key = (binding.user_id, binding.login_claims['sid'], binding.device_id)
        if self.devices.get(key) is binding:
            del self.devices[key]
        if binding.socket:
            binding.socket.disconnected.set()
        binding.cleanup = asyncio.create_task(self.dispose(binding))
        self.cleanups.add(binding.cleanup)
        binding.cleanup.add_done_callback(self.cleanups.discard)
        return binding.cleanup

    @staticmethod
    async def dispose(binding):
        try:
            await stop_process(binding.process)
        finally:
            try:
                await asyncio.to_thread(binding.home.cleanup)
            except OSError:
                log.warning('Could not remove Browse relay state', exc_info=True)

    def get(self, binding_id):
        binding = self.bindings.get(binding_id)
        if binding and not binding.live:
            self.retire(binding)
            return None
        return binding

    async def json_request(self, binding, method, path, *, timeout=5, **kwargs):
        headers = {'Authorization': f'Bearer {binding.relay_token}'} if binding.relay_token else {}
        async with self.session.request(
            method,
            f'{binding.url}{path}',
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout, connect=5),
            allow_redirects=False,
            **kwargs,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def bind(self, user_id, device_id, login_claims):
        self.require_enabled()
        key = (user_id, login_claims['sid'], device_id)
        if pending := self.starting.get(key):
            return await asyncio.shield(pending)
        if previous := self.devices.get(key):
            if previous.live:
                return previous, previous.pair_code
            self.retire(previous)
        occupied = self.devices.keys() | self.starting.keys()
        owned = [k for k in occupied if k[0] == user_id]
        pairing = sum(k not in self.devices or not self.devices[k].connected_once for k in owned)
        if len(owned) >= MAX_USER_BINDINGS or pairing >= MAX_USER_PAIRING:
            raise HTTPException(429, 'browse_user_capacity')
        if len(occupied) >= MAX_BINDINGS:
            raise HTTPException(503, 'Browse is at capacity')

        pending = asyncio.create_task(self.start_binding(key, dict(login_claims)))
        self.starting[key] = pending
        pending.add_done_callback(lambda task: self.finish_start(key, task))
        return await asyncio.shield(pending)

    def finish_start(self, key, task):
        if self.starting.get(key) is task:
            del self.starting[key]
        if not task.cancelled():
            task.exception()

    async def start_binding(self, key, login_claims):
        user_id, _, device_id = key
        binding = None
        try:
            # Closing the reservation before exec leaves a small bind race. PID verification below fails closed.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            home = tempfile.TemporaryDirectory(prefix='webui-browse-')
            binding = Binding(
                secrets.token_urlsafe(32), secrets.token_urlsafe(32), user_id, device_id, login_claims, home, port
            )
            files = Path(home.name) / 'files'
            files.mkdir(mode=0o700)
            env = {
                key: os.environ[key]
                for key in ('PATH', 'LANG', 'LC_ALL', 'TZ', 'SYSTEMROOT', 'WINDIR')
                if key in os.environ
            }
            env.update(
                OPENCODE_BROWSER_HOME=home.name,
                OPENCODE_BROWSER_PORT=str(port),
                OPENCODE_BROWSER_AUTOSTART='0',
                BROWSE_PRIVATE_FILE_ROOT=str(files),
                TMPDIR=str(files),
                TEMP=str(files),
                TMP=str(files),
            )
            binary = Path(self.binary)
            if not binary.is_absolute():
                raise OSError('BROWSE_BINARY must be an absolute native executable path')
            binding.process = await asyncio.create_subprocess_exec(
                str(binary), 'serve', env=env, cwd=home.name,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await self.wait_for_relay(binding)
            binding.relay_token = (Path(home.name) / 'relay-token').read_text(encoding='utf-8').strip()
            if not BINDING_ID.fullmatch(binding.relay_token):
                raise ValueError('Browse relay did not create an API token')
            binding.pair_code = await self.mint(binding, binary, env)
            if not await self.login_is_valid(binding.login_claims):
                raise HTTPException(403, 'browse_session_invalid')
            self.require_enabled()
            if binding.process.returncode is not None:
                raise ValueError('Browse relay exited during pairing')

            now = time.monotonic()
            binding.expires_at = now + BINDING_LIFETIME
            binding.offline_until = now + PAIR_WINDOW
            self.bindings[binding.id] = binding
            self.devices[key] = binding
            return binding, binding.pair_code
        except (OSError, ValueError, aiohttp.ClientError, TimeoutError) as exc:
            log.warning('Could not start Browse relay: %s', type(exc).__name__)
            raise HTTPException(503, 'Could not start Browse relay') from exc
        finally:
            if binding is not None and self.bindings.get(binding.id) is not binding:
                await asyncio.shield(self.retire(binding))

    async def wait_for_relay(self, binding):
        async with asyncio.timeout(10):
            while binding.process.returncode is None:
                try:
                    response = await self.json_request(binding, 'GET', '/version', timeout=1)
                except (aiohttp.ClientError, TimeoutError):
                    await asyncio.sleep(0.05)
                    continue
                if (
                    isinstance(response, dict)
                    and response.get('pid') == binding.process.pid
                    and response.get('runtime') == 'rust'
                ):
                    if response.get('privateFileRoot') is not True:
                        raise HTTPException(503, 'Browse Relay must be built from ck-openwebui-browse with private file roots')
                    return
                raise ValueError('Unexpected service on Browse relay port')
        raise ValueError('Browse relay exited before readiness')

    @staticmethod
    async def mint(binding, binary, env):
        process = await asyncio.create_subprocess_exec(
            str(binary), 'pair', '--mint-json', env=env, cwd=binding.home.name,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
        finally:
            await stop_process(process)
        result = json.loads(stdout)
        if not isinstance(result, dict):
            raise ValueError('Unexpected Browse pairing response')
        code = result.get('code')
        if process.returncode or result.get('port') != binding.port or not isinstance(code, str) or not code:
            raise ValueError('Unexpected Browse pairing response')
        return code

    async def ready(self, user_id, session_id, binding_id):
        self.require_enabled()
        binding = self.get(binding_id)
        if (
            binding is None
            or binding.user_id != user_id
            or binding.login_claims['sid'] != session_id
            or not await self.validate_binding(binding)
        ):
            raise HTTPException(404, 'Browse binding is unavailable')
        current = binding.socket
        if (
            current is None
            or current.disconnected.is_set()
            or current.upstream is None
            or current.upstream.closed
        ):
            raise HTTPException(409, 'Browse extension is not connected')
        try:
            state = await self.json_request(binding, 'GET', '/extension/status')
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise HTTPException(503, 'Browse relay is unavailable') from exc
        if state.get('connected') is not True or not self.socket_live(binding, current):
            raise HTTPException(409, 'Browse extension is not connected')
        return binding, current

    def socket_live(self, binding, current):
        return binding.live and binding.socket is current and not current.disconnected.is_set()

    async def tool_call(self, user_id, session_id, binding_id, name, default_tab, properties, arguments):
        binding, current = await self.ready(user_id, session_id, binding_id)
        args = {key: value for key, value in arguments.items() if key in properties}
        if name != 'tabs' and default_tab is not None and 'tab' in properties and args.get('tab') is None:
            args['tab'] = default_tab
        timeout = 180
        if name in HANDOFF_TOOLS:
            seconds = args.get('timeoutSeconds')
            if seconds is None:
                seconds = MAX_HANDOFF_SECONDS
            if type(seconds) is not int or not 1 <= seconds <= MAX_HANDOFF_SECONDS:
                return {'error': f'timeoutSeconds must be between 1 and {MAX_HANDOFF_SECONDS}'}
            timeout = seconds + 30

        if not self.socket_live(binding, current):
            return {'error': 'Browse extension disconnected'}
        call = asyncio.create_task(self.json_request(
            binding, 'POST', '/tools/call', timeout=timeout, json={'name': name, 'arguments': args}
        ))
        disconnected = asyncio.create_task(current.disconnected.wait())
        try:
            await asyncio.wait((call, disconnected), return_when=asyncio.FIRST_COMPLETED)
            if not self.socket_live(binding, current):
                return {'error': 'Browse extension disconnected'}
            output = call.result()
            if not await self.validate_binding(binding) or not self.socket_live(binding, current):
                return {'error': 'Browse login session or connection is unavailable'}
        except TimeoutError:
            return {'error': 'Browse tool timed out'}
        except aiohttp.ClientError:
            return {'error': 'Browse relay is unavailable'}
        finally:
            for task in (call, disconnected):
                task.cancel()
            await asyncio.gather(call, disconnected, return_exceptions=True)
        if output.get('isError'):
            text = '\n'.join(item['text'] for item in output['content'] if item.get('type') == 'text')
            return {'error': text or 'Browse tool failed'}
        return output['content']

    async def tools(self, user_id, session_id, binding_id, default_tab):
        binding, current = await self.ready(user_id, session_id, binding_id)
        try:
            specs = await self.json_request(binding, 'GET', '/tools')
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise HTTPException(503, 'Browse tools are unavailable') from exc
        if not self.socket_live(binding, current):
            raise HTTPException(409, 'Browse extension is not connected')

        def callable_for(name, properties):
            async def call(**kwargs):
                try:
                    return await self.tool_call(user_id, session_id, binding_id, name, default_tab, properties, kwargs)
                except HTTPException as exc:
                    return {'error': exc.detail}
            return call

        tools = {}
        for spec in specs:
            name = spec['name']
            if name not in BROWSE_TOOLS:
                continue
            schema = spec['inputSchema']
            properties = schema.get('properties', {})
            if name != 'tabs' and default_tab is not None and 'tab' in properties:
                schema['required'] = [key for key in schema.get('required', []) if key != 'tab']
            if name in HANDOFF_TOOLS:
                properties['timeoutSeconds']['maximum'] = MAX_HANDOFF_SECONDS
            tool_name = f'browse_{name}'
            tools[tool_name] = {
                'spec': {'name': tool_name, 'description': spec['description'], 'parameters': schema},
                'callable': callable_for(name, frozenset(properties)),
                'type': 'browse',
            }
        if not tools:
            raise HTTPException(503, 'Browse tools are unavailable')
        return tools
