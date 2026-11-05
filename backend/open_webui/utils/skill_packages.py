"""统一 Skill 包身份、Terminal 传输与模型工具的发现策略。"""

import hashlib
import io
import json
import zipfile
from urllib.parse import quote, unquote, urlencode

import aiohttp
from fastapi import HTTPException

from open_webui.config import BYPASS_ADMIN_ACCESS_CONTROL
from open_webui.models.access_grants import AccessGrants
from open_webui.models.skills import SkillMeta
from open_webui.utils.skill_files import file_bytes, validate_files, zip_export

POLICY_FILE = '.openwebui-skill.json'
SCOPES = {'global', 'chat', 'project'}


def terminal_package_id(terminal_id, scope, scope_id, package_id):
    return 'terminal:' + ':'.join(quote(str(part), safe='') for part in (terminal_id, scope, scope_id, package_id))


def parse_terminal_package_id(id):
    parts = id.split(':')
    if len(parts) != 5 or parts[0] != 'terminal':
        raise HTTPException(400, '管理操作需要包含 Terminal、scope 和包路径的完整 Skill ID')
    terminal_id, scope, scope_id, package_id = map(unquote, parts[1:])
    if not terminal_id or scope not in SCOPES or not package_id or (scope != 'global' and not scope_id):
        raise HTTPException(400, 'Terminal Skill ID 无效')
    if scope == 'global' and scope_id:
        raise HTTPException(400, '全局 Skill 不应包含 scope_id')
    return terminal_id, scope, scope_id, package_id


async def terminal_package_request(request, user, terminal_id, *, project_id=None, chat_id=None, path='/skills/packages', method='GET', payload=None):
    from open_webui.env import AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL, AIOHTTP_CLIENT_TIMEOUT_TERMINAL, ENABLE_TOOL_SERVERS
    from open_webui.models.config import Config
    from open_webui.models.groups import Groups
    from open_webui.utils.access_control import has_connection_access
    from open_webui.utils.terminal_identity import terminal_identity_headers
    from open_webui.utils.terminals import (
        TERMINAL_CONTEXT_HEADER, get_terminal_server_url, terminal_context_available,
        terminal_context_config, terminal_context_id,
    )
    from open_webui.utils.tools import build_tool_server_headers

    if not ENABLE_TOOL_SERVERS:
        raise HTTPException(503, 'Terminal 服务未启用')
    if project_id:
        from open_webui.routers.terminals import _project_agents_context
        connection, headers, cookies = await _project_agents_context(request, user, project_id)
        if terminal_id and connection.get('id') != terminal_id:
            raise HTTPException(409, '项目只能使用绑定的 Terminal')
    else:
        connections = await Config.get('terminal_server.connections', []) or []
        connection = next((item for item in connections if item.get('id') == terminal_id), None)
        if not connection or not connection.get('enabled', True) or not terminal_context_available(connection, 'chat'):
            raise HTTPException(503, 'Terminal 不可用或尚未配置')
        groups = {group.id for group in await Groups.get_groups_by_member_id(user.id, include_inherited=True)}
        if not await has_connection_access(user, connection, groups):
            raise HTTPException(403, '无权访问该 Terminal')
        metadata = {'chat_id': chat_id, 'terminal_id': terminal_id}
        context_id = terminal_context_id(connection, metadata)
        config = terminal_context_config(connection, 'chat')
        if isinstance(config, dict) and config.get('context_id') == 'chat_id' and not context_id:
            raise HTTPException(400, '该 Terminal 需要有效聊天上下文')
        headers, cookies = await build_tool_server_headers(connection, request, user, metadata=metadata)
        headers = await terminal_identity_headers(request, connection, user, chat_id, headers)
        if context_id:
            headers[TERMINAL_CONTEXT_HEADER] = context_id
    headers = {key: value for key, value in headers.items() if key.lower() != 'content-type'}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_TERMINAL), trust_env=True) as session:
            async with session.request(
                method, get_terminal_server_url(connection) + path, json=payload, headers=headers,
                cookies=cookies, ssl=AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL, allow_redirects=False,
            ) as response:
                if not 200 <= response.status < 300:
                    detail = 'Terminal Skill 包请求失败'
                    try:
                        error = await response.json()
                        if isinstance(error, dict) and isinstance(error.get('detail'), str):
                            detail += '：' + error['detail'][:1000]
                    except (ValueError, aiohttp.ClientError):
                        pass
                    raise HTTPException(response.status if response.status in (400, 401, 403, 404, 409, 410, 413, 422, 503) else 502, detail)
                return await response.json()
    except (aiohttp.ClientError, TimeoutError) as error:
        raise HTTPException(503, 'Terminal 暂时不可用，请稍后重试') from error
    except ValueError as error:
        raise HTTPException(502, 'Terminal 返回了无效的 Skill 包') from error


def terminal_item(item, terminal_id, *, expected_scope=None, expected_scope_id=None):
    if not isinstance(item, dict) or item.get('scope') not in SCOPES:
        raise HTTPException(502, 'Terminal 未提供可信的 Skill scope')
    scope, scope_id = item['scope'], item.get('scope_id') or ''
    if expected_scope and (scope != expected_scope or scope_id != (expected_scope_id or '')):
        raise HTTPException(409, 'Skill 包不属于当前 Terminal 工作区')
    return {
        **item, 'id': terminal_package_id(terminal_id, scope, scope_id, item['package_id']),
        'terminal_id': terminal_id, 'source': 'terminal', 'meta': SkillMeta.model_validate(item.get('meta') or {}).model_dump(),
    }


async def workspace_item(skill, user, db=None, *, detail=False, version_id=None):
    from open_webui.models.skills import get_skill_snapshot
    writable = (
        (user.role == 'admin' and BYPASS_ADMIN_ACCESS_CONTROL) or user.id == skill.user_id
        or await AccessGrants.has_access(user_id=user.id, resource_type='skill', resource_id=skill.id, permission='write', db=db)
    )
    result = {
        **skill.model_dump(exclude={'content', 'data'}), 'source': 'workspace', 'scope': 'workspace',
        'scope_id': '', 'location': f'workspace:{skill.id}', 'write_access': writable,
    }
    if detail:
        snapshot = await get_skill_snapshot(skill, version_id, db)
        result.update(snapshot)
        result.update(files=snapshot['data']['files'], version_id=version_id or skill.version_id)
    return result


def restore_portable_policy(package):
    package = dict(package)
    files = package['files']
    manifest = next((file for file in files if file['path'] == POLICY_FILE), None)
    if manifest:
        if len(file_bytes(manifest)) > 65536:
            raise ValueError('Skill 元数据超过 64 KiB')
        policy = json.loads(file_bytes(manifest))
        if not isinstance(policy, dict):
            raise ValueError('Skill 元数据无效')
        package.update({key: policy[key] for key in ('name', 'description', 'meta', 'is_active') if key in policy})
        package['files'] = [file for file in files if file['path'] != POLICY_FILE]
    package['files'] = validate_files(package['files'])
    package['meta'] = SkillMeta.model_validate(package.get('meta') or {}).model_dump()
    return package


def portable_package(package):
    result = {key: package[key] for key in ('name', 'description', 'meta', 'is_active')}
    # 包 ID 是管理引用，导出使用稳定且合法的文件夹名。
    import re
    result['id'] = re.sub(r'[^a-z0-9_-]+', '-', str(package.get('name') or '').lower()).strip('-') or 'skill'
    result['files'] = package['files']
    return result


def portable_archive(package):
    portable = portable_package(package)
    output = io.BytesIO(zip_export([portable]))
    policy = {key: portable[key] for key in ('name', 'description', 'meta', 'is_active')}
    comment = b'openwebui-skill-package-v1\n' + json.dumps([policy], ensure_ascii=False).encode()
    if len(comment) > 65535:
        raise ValueError('Skill 导出元数据超过 ZIP 注释容量')
    with zipfile.ZipFile(output, 'a') as archive:
        archive.comment = comment
    return portable['id'], output.getvalue()


def archive_policies(raw, filename):
    if not filename.lower().endswith(('.zip', '.skill')):
        return None
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        comment = archive.comment
    prefix = b'openwebui-skill-package-v1\n'
    if not comment.startswith(prefix):
        return None
    policies = json.loads(comment[len(prefix):])
    if not isinstance(policies, list) or any(not isinstance(policy, dict) for policy in policies):
        raise ValueError('Skill 导出元数据无效')
    return policies


def resolved_skill_id(id, metadata):
    return ((metadata or {}).get('skill_aliases') or {}).get(id, id)


def check_skill_policy(skill, id, metadata, *, terminal_available=True, require_discovery=True):
    from open_webui.utils.skill_policy import skill_available
    metadata = metadata or {}
    id = resolved_skill_id(id, metadata)
    if require_discovery and id not in (metadata.get('skill_ids') or []):
        raise ValueError('Skill 不在当前可发现列表内')
    if not skill_available(
        skill, metadata.get('skill_mode', 'chat'), metadata.get('skill_capabilities'),
        terminal_available=terminal_available,
    ):
        raise ValueError('Skill 在当前模式或能力配置下不可用')


async def load_terminal_tool_package(request, user, metadata, id, extra_params=None, *, refresh=True, require_discovery=True):
    from open_webui.utils.terminals import get_terminal_json
    metadata = metadata if metadata is not None else {}
    id = resolved_skill_id(id, metadata)
    if require_discovery and id not in (metadata.get('skill_ids') or []):
        raise ValueError('Skill 不在当前可发现列表内')
    if len(id.split(':')) == 5:
        terminal_id, scope, scope_id, package_id = parse_terminal_package_id(id)
        if terminal_id != metadata.get('terminal_id'):
            raise ValueError('Skill 不属于当前 Terminal')
        data = await get_terminal_json(request, user, metadata, '/skills/packages/detail?' + urlencode({'id': package_id}), extra_params)
        if data is not None:
            data = terminal_item(data, terminal_id, expected_scope=scope, expected_scope_id=scope_id)
    else:
        name = unquote(id.removeprefix('terminal:'))
        listing = await get_terminal_json(request, user, metadata, '/skills/packages', extra_params)
        matches = [item for item in (listing or {}).get('items', []) if item.get('name') == name]
        if matches:
            data = await get_terminal_json(request, user, metadata, '/skills/packages/detail?' + urlencode({'id': matches[0]['package_id']}), extra_params)
        else:
            # 旧服务器仍支持只含 SKILL.md 的 Skill；所有完整包操作要求新接口。
            data = await get_terminal_json(request, user, metadata, '/skills/read?' + urlencode({'name': name}), extra_params)
        if data is not None:
            data.setdefault('files', [{'path': 'SKILL.md', 'content': data['content']}])
    if not isinstance(data, dict) or not isinstance(data.get('content'), str):
        return None
    check_skill_policy(data, id, metadata, require_discovery=require_discovery)
    files = validate_files(data.get('files') or [{'path': 'SKILL.md', 'content': data['content']}])
    data['files'] = files
    digest = hashlib.sha256(json.dumps({'files': files, 'meta': data.get('meta'), 'is_active': data.get('is_active', True)}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    context = metadata.get('chat_context') or {}
    metadata['chat_context'] = context
    fingerprints = context.setdefault('terminal_skill_fingerprints', {}).setdefault(metadata['terminal_id'], {})
    if not refresh and id in fingerprints and fingerprints[id] != digest:
        raise ValueError('Skill 已变化，请重新调用 view_skill 后再读取')
    fingerprints[id] = digest
    return data


async def get_package(request, user, id, db=None):
    from open_webui.routers.skills import get_skill_package
    return await get_skill_package(request, id, None, None, None, None, user, db)


def scope_terminal_skill(skill, metadata):
    """将 Terminal 列表项转换为当前工作区内稳定且可管理的引用。"""
    item = dict(skill)
    if item.get('package_id'):
        scope = item.get('scope')
        scope_id = item.get('scope_id') or ''
        if scope not in SCOPES:
            scope = 'project' if metadata.get('skill_project_id') else 'chat' if metadata.get('chat_id') else 'global'
            scope_id = metadata.get('skill_project_id') or metadata.get('chat_id') or ''
        item.update(scope=scope, scope_id=scope_id)
        item['id'] = terminal_package_id(metadata['terminal_id'], scope, scope_id, item['package_id'])
        item['terminal_id'] = metadata['terminal_id']
    return item


def terminal_skill_aliases(skill, metadata):
    item = scope_terminal_skill(skill, metadata)
    aliases = {item['id'], skill['id']}
    if item.get('name'):
        aliases.add('terminal:' + quote(item['name'], safe=''))
    return aliases


def terminal_skill_name(id, metadata, skills):
    """仅从当前已发现列表解析名称；完整引用不能切换 Terminal 或工作区。"""
    if len(id.split(':')) == 5:
        terminal_id, scope, scope_id, _ = parse_terminal_package_id(id)
        if terminal_id != metadata.get('terminal_id'):
            raise ValueError('Skill 不属于当前 Terminal')
        if scope == 'project' and scope_id != metadata.get('skill_project_id'):
            raise ValueError('Skill 不属于当前项目')
        if scope == 'chat' and (metadata.get('skill_project_id') or scope_id != metadata.get('chat_id')):
            raise ValueError('Skill 不属于当前聊天')
    for skill in skills:
        if id in terminal_skill_aliases(skill, metadata):
            return skill['name']
    raise ValueError('Skill 不在当前工作区的可发现列表内')
