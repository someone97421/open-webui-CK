"""终端请求的会话归属验证和工作区签名。"""

import base64
import hashlib
import hmac
import json
import time

from fastapi import HTTPException
from open_webui.models.chats import Chats
from open_webui.models.folders import Folders
from open_webui.utils.chat_id import is_saved_chat_id, is_temporary_chat_id
from open_webui.utils.headers import normalize_bearer_token
from open_webui.utils.projects import (
    PROJECT_PROTOCOL, get_project_for_folder, project_config, require_project_access, validate_project_terminal,
)

_WORKSPACE_HEADERS = {'x-user-id', 'x-session-id', 'x-workspace-context', 'x-workspace-signature'}


async def verify_terminal_chat_access(request, user, chat_id: str):
    if not isinstance(chat_id, str) or not chat_id.strip() or len(chat_id.encode('utf-8')) > 1024:
        raise HTTPException(status_code=400, detail='A valid terminal chat is required')
    if chat_id.startswith('project:'):
        project_id = chat_id.removeprefix('project:')
        if getattr(request.state, 'project_settings_id', None) != project_id:
            raise HTTPException(status_code=404, detail='项目设置上下文不可用')
        project = await Folders.get_folder_by_id(project_id)
        await require_project_access(user, project, allow_archived=True)
        return project
    if is_temporary_chat_id(chat_id):
        from open_webui.utils.chat import get_temporary_chat

        owner = await get_temporary_chat(request.app.state.redis, chat_id)
        if owner and owner.get('user_id') == user.id:
            return None
    elif is_saved_chat_id(chat_id):
        chat = await Chats.get_accessible_chat_by_id(chat_id, user, permission='write')
        if not chat and await Chats.is_chat_owner(chat_id, user.id):
            chat = await Chats.get_chat_by_id(chat_id)
        if chat:
            project = await get_project_for_folder(chat.folder_id)
            if project:
                await require_project_access(user, project)
            return project
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
            return None
    raise HTTPException(status_code=404, detail='Chat expired or unavailable')


async def terminal_identity_headers(request, connection: dict, user, chat_id: str | None, headers: dict) -> dict:
    result = {key: value for key, value in headers.items() if key.lower() not in _WORKSPACE_HEADERS}
    result['X-User-Id'] = user.id
    if not chat_id:
        return result
    project = await verify_terminal_chat_access(request, user, chat_id)
    result['X-Session-Id'] = chat_id
    if project:
        config = project_config(project)
        if connection.get('id') != config['terminal_id']:
            raise HTTPException(status_code=409, detail='该会话只能使用项目绑定的 Terminal')
        connection = await validate_project_terminal(request, user, config['terminal_id'])
    if connection.get('server_type') == 'orchestrator' or connection.get('policy_id'):
        return result
    if connection.get('auth_type', 'bearer') != 'bearer':
        return result
    key = normalize_bearer_token(connection.get('key', ''))
    if not key:
        return result
    payload = {'v': 1, 'user': user.id, 'chat': chat_id, 'exp': int(time.time()) + 300}
    protocol = 'open-terminal/workspace/v1'
    if project:
        payload.update(v=2, scope_type='project', scope_id=project.id, owner=project.user_id)
        protocol = PROJECT_PROTOCOL
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    context = base64.urlsafe_b64encode(encoded).decode('ascii').rstrip('=')
    result['X-Workspace-Context'] = context
    result['X-Workspace-Signature'] = hmac.new(
        key.encode('utf-8'), protocol.encode() + b'\0' + context.encode('ascii'), hashlib.sha256
    ).hexdigest()
    return result
