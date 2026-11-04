"""按项目归属清理 Terminal 工作区及 WebUI 记录。"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time

import aiohttp
from fastapi import HTTPException
from sqlalchemy import delete, select, update

from open_webui.env import AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL, ENABLE_TOOL_SERVERS
from open_webui.events import EVENTS, publish_event
from open_webui.models.access_grants import AccessGrant
from open_webui.models.automations import Automation, AutomationRun
from open_webui.models.chat_messages import ChatMessage
from open_webui.models.chats import Chat, ChatFile
from open_webui.models.comments import delete_resource_comments
from open_webui.models.config import Config
from open_webui.models.folders import Folder
from open_webui.models.notifications import emit_changes
from open_webui.models.shared_chats import SharedChat
from open_webui.models.tags import Tag
from open_webui.tasks import stop_item_tasks
from open_webui.utils.headers import normalize_bearer_token
from open_webui.utils.projects import PROJECT_PROTOCOL, project_config
from open_webui.utils.terminals import get_terminal_server_url, is_terminal_orchestrator

log = logging.getLogger(__name__)


async def _project_chat_ids(project_id, db):
    chat_ids = set((await db.scalars(select(Chat.id).where(Chat.folder_id == project_id))).all())
    pending = chat_ids.copy()
    while pending:
        children = set((await db.scalars(
            select(Chat.id).where(
                Chat.meta['internal'].as_boolean().is_(True),
                Chat.meta['parent_chat_id'].as_string().in_(pending),
                (Chat.folder_id == project_id) | Chat.folder_id.is_(None),
            )
        )).all()) - chat_ids
        chat_ids.update(children)
        pending = children
    return chat_ids


def _deletion_headers(connection, user, project_id, owner_id):
    key = normalize_bearer_token(connection.get('key', ''))
    chat_id = f'project:{project_id}'
    payload = {
        'v': 2, 'user': user.id, 'chat': chat_id, 'owner': owner_id,
        'scope_type': 'project', 'scope_id': project_id,
        'operation': 'delete', 'exp': int(time.time()) + 300,
    }
    if user.role == 'admin':
        payload['admin'] = True
    context = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    ).decode('ascii').rstrip('=')
    signature = hmac.new(
        key.encode('utf-8'), PROJECT_PROTOCOL.encode() + b'\0' + context.encode('ascii'), hashlib.sha256
    ).hexdigest()
    return {
        'Authorization': f'Bearer {key}', 'X-User-Id': user.id, 'X-Session-Id': chat_id,
        'X-Workspace-Context': context, 'X-Workspace-Signature': signature,
    }


async def _terminal_for_deletion(project, user):
    config = project_config(project)
    connections = await Config.get('terminal_server.connections', []) or []
    connection = next((item for item in connections if item.get('id') == config['terminal_id']), None)
    if (
        not ENABLE_TOOL_SERVERS or not connection or is_terminal_orchestrator(connection)
        or connection.get('auth_type', 'bearer') != 'bearer'
        or not normalize_bearer_token(connection.get('key', ''))
    ):
        raise HTTPException(status_code=409, detail='请恢复项目原有的直连 Terminal 配置后重试删除')
    headers = _deletion_headers(connection, user, project.id, project.user_id)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10, connect=5), trust_env=True) as session:
            async with session.get(
                f'{get_terminal_server_url(connection)}/api/config', headers=headers,
                ssl=AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL, allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise HTTPException(status_code=503, detail='无法确认 Terminal 删除能力，项目记录已保留')
                capabilities = await response.json()
        if (
            not capabilities.get('features', {}).get('workspace_isolation')
            or 'delete' not in (capabilities.get('workspace_context', {}).get('operations') or [])
        ):
            raise HTTPException(status_code=409, detail='请先升级 Terminal，当前版本不支持删除项目工作区')
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, AttributeError) as error:
        raise HTTPException(status_code=503, detail='Terminal 连接失败，项目记录已保留') from error
    return connection


async def _delete_terminal_workspace(connection, user, project_id, owner_id):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120, connect=5), trust_env=True) as session:
            async with session.delete(
                f'{get_terminal_server_url(connection)}/api/workspace',
                headers=_deletion_headers(connection, user, project_id, owner_id),
                ssl=AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL, allow_redirects=False,
            ) as response:
                if response.status in (404, 405):
                    raise HTTPException(status_code=409, detail='请升级 Terminal 后重试删除项目')
                if response.status != 200:
                    raise HTTPException(status_code=503, detail='工作区清理未完成，项目记录已保留，请重试删除')
                result = await response.json()
                if not isinstance(result, dict) or result.get('deleted') is not True or result.get('project_id') != project_id:
                    raise HTTPException(status_code=502, detail='Terminal 未确认工作区删除，项目记录已保留')
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
        raise HTTPException(status_code=503, detail='工作区清理结果未确认，项目记录已保留，请重试删除') from error


async def delete_project(request, user, project, db):
    project_owner_id = project.user_id
    if project_owner_id != user.id and user.role != 'admin':
        raise HTTPException(status_code=404, detail='项目不存在或不属于当前账号')
    connection = await _terminal_for_deletion(project, user)
    locked = await db.scalar(
        select(Folder).where(Folder.id == project.id, Folder.user_id == project_owner_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if not locked or not project_config(locked):
        raise HTTPException(status_code=404, detail='项目不存在')
    if project_config(locked)['terminal_id'] != project_config(project)['terminal_id']:
        raise HTTPException(status_code=409, detail='项目 Terminal 配置已变化，请重试删除')
    chat_ids = await _project_chat_ids(project.id, db)
    locked.data = {**locked.data, 'project': {**locked.data['project'], 'deleting': True}}
    await db.commit()
    try:
        for chat_id in chat_ids:
            await stop_item_tasks(request.app.state.redis, chat_id)
        await _delete_terminal_workspace(connection, user, project.id, project_owner_id)
        locked = await db.scalar(
            select(Folder).where(Folder.id == project.id, Folder.user_id == project_owner_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if not locked:
            return True
        chat_ids = await _project_chat_ids(project.id, db)
        for chat_id in chat_ids:
            await stop_item_tasks(request.app.state.redis, chat_id)
        recipients = await delete_resource_comments('chat', list(chat_ids), db=db)
        await db.execute(update(AutomationRun).where(AutomationRun.chat_id.in_(chat_ids)).values(chat_id=None))
        await db.execute(delete(ChatMessage).where(ChatMessage.chat_id.in_(chat_ids)))
        await db.execute(delete(ChatFile).where(ChatFile.chat_id.in_(chat_ids)))
        await db.execute(delete(SharedChat).where(SharedChat.chat_id.in_(chat_ids)))
        await db.execute(delete(AccessGrant).where(AccessGrant.resource_type == 'chat', AccessGrant.resource_id.in_(chat_ids)))
        deleted_chats = (await db.execute(select(Chat.id, Chat.user_id).where(Chat.id.in_(chat_ids)))).all()
        tag_owners = (await db.execute(select(Chat.user_id, Chat.meta).where(Chat.id.in_(chat_ids)))).all()
        await db.execute(delete(Chat).where(Chat.id.in_(chat_ids)))
        for owner_id in {owner_id for owner_id, _ in tag_owners}:
            tag_ids = {
                tag for owner, meta in tag_owners if owner == owner_id
                for tag in (meta or {}).get('tags', []) if isinstance(tag, str)
            }
            if tag_ids:
                remaining = (await db.scalars(select(Chat.meta['tags']).where(Chat.user_id == owner_id))).all()
                used_tags = {tag for tags in remaining if isinstance(tags, list) for tag in tags if isinstance(tag, str)}
                await db.execute(delete(Tag).where(Tag.user_id == owner_id, Tag.id.in_(tag_ids - used_tags)))
        await db.execute(delete(AccessGrant).where(AccessGrant.resource_type == 'folder', AccessGrant.resource_id == project.id))
        await db.execute(update(Automation).where(Automation.folder_id == project.id).values(folder_id=None, updated_at=int(time.time_ns())))
        await db.execute(delete(Folder).where(Folder.id == project.id, Folder.user_id == project_owner_id))
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as error:
        await db.rollback()
        log.exception('项目删除尚未完成：%s', project.id)
        raise HTTPException(status_code=503, detail='项目清理未完成，请重试删除；已删除的工作区文件无法恢复') from error
    try:
        await emit_changes(recipients)
        await publish_event(
            request, EVENTS.FOLDER_DELETED, actor=user, subject_id=project.id,
            data={'folder_ids': [project.id], 'delete_contents': True},
        )
        for chat_id, owner_id in deleted_chats:
            await publish_event(
                request, EVENTS.CHAT_DELETED, actor=user, subject_id=chat_id,
                data={'owner_id': owner_id},
            )
    except Exception:
        log.exception('项目已删除，刷新事件发送失败：%s', project.id)
    return True
