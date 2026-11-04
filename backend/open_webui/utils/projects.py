"""项目归属解析与 Terminal 能力校验。"""

import asyncio
import hashlib
import json
import time

import aiohttp
from fastapi import HTTPException
from open_webui.env import AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL, ENABLE_TOOL_SERVERS
from open_webui.models.config import Config
from open_webui.models.folders import Folders
from open_webui.models.groups import Groups
from open_webui.utils.access_control import has_connection_access
from open_webui.utils.headers import normalize_bearer_token

PROJECT_PROTOCOL = 'open-terminal/workspace/v2'


def project_config(folder) -> dict | None:
    data = folder.get('data') if isinstance(folder, dict) else folder.data if folder else None
    value = (data or {}).get('project')
    if value is None:
        return None
    if (
        not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1
        or not isinstance(value.get('terminal_id'), str) or not value['terminal_id'].strip()
        or type(value.get('archived', False)) is not bool
    ):
        raise HTTPException(status_code=409, detail='项目配置无效，请检查 Terminal 绑定')
    return {
        'version': 1, 'terminal_id': value['terminal_id'], 'archived': value.get('archived', False),
        **({'deleting': True} if value.get('deleting') is True else {}),
    }


async def get_project_for_folder(folder_id: str | None):
    seen = set()
    while folder_id:
        if folder_id in seen:
            raise HTTPException(status_code=409, detail='项目目录存在循环归属')
        seen.add(folder_id)
        folder = await Folders.get_folder_by_id(folder_id)
        if not folder:
            return None
        if project_config(folder):
            return folder
        folder_id = folder.parent_id
    return None


async def require_project_access(user, project, *, writable=True, allow_archived=False):
    config = project_config(project)
    if not config or (project.user_id != user.id and user.role != 'admin'):
        raise HTTPException(status_code=404, detail='项目不存在或不可访问')
    if config.get('deleting'):
        raise HTTPException(status_code=409, detail='项目正在删除；清理失败时请重试删除')
    if config['archived'] and not allow_archived:
        raise HTTPException(status_code=409, detail='项目已归档，请先恢复项目')
    return config


async def validate_project_terminal(request, user, terminal_id: str) -> dict:
    from open_webui.utils.tools import build_tool_server_headers
    from open_webui.utils.terminals import get_terminal_server_url, is_terminal_orchestrator, terminal_context_available

    connections = await Config.get('terminal_server.connections', []) or []
    connection = next((item for item in connections if item.get('id') == terminal_id), None)
    if not ENABLE_TOOL_SERVERS or not connection or not connection.get('enabled', True):
        raise HTTPException(status_code=409, detail='项目绑定的 Terminal 不可用')
    group_ids = {group.id for group in await Groups.get_groups_by_member_id(user.id, include_inherited=True)}
    if not await has_connection_access(user, connection, group_ids):
        raise HTTPException(status_code=403, detail='无权使用项目绑定的 Terminal')
    if (
        is_terminal_orchestrator(connection) or connection.get('policy_id') or not terminal_context_available(connection, 'chat')
        or connection.get('auth_type', 'bearer') != 'bearer'
        or not normalize_bearer_token(connection.get('key', ''))
    ):
        raise HTTPException(status_code=409, detail='项目需要使用 Bearer 密钥的直连 Open Terminal')
    fingerprint = hashlib.sha256(json.dumps(connection, sort_keys=True, default=str).encode()).hexdigest()
    cache = getattr(request.app.state, 'PROJECT_TERMINAL_CAPABILITIES', None)
    if cache is None:
        cache = request.app.state.PROJECT_TERMINAL_CAPABILITIES = {}
    cached = cache.get(terminal_id)
    if cached and cached[0] == fingerprint and cached[1] > time.monotonic():
        return connection
    headers, cookies = await build_tool_server_headers(connection, request, user)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5), trust_env=True) as session:
            async with session.get(
                f'{get_terminal_server_url(connection)}/api/config', headers=headers, cookies=cookies,
                ssl=AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL, allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise HTTPException(status_code=409, detail='无法读取项目 Terminal 的工作区能力')
                data = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        raise HTTPException(status_code=409, detail='项目 Terminal 连接失败') from exc
    features, context = data.get('features') or {}, data.get('workspace_context') or {}
    if (
        not features.get('workspace_isolation') or not features.get('project_workspaces')
        or PROJECT_PROTOCOL not in (context.get('protocols') or [])
        or 'project' not in (context.get('scopes') or [])
    ):
        raise HTTPException(status_code=409, detail='请升级并启用 Terminal 的项目工作区隔离（v2）')
    cache[terminal_id] = (fingerprint, time.monotonic() + 30)
    return connection
