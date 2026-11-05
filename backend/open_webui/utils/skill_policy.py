"""技能模式策略与会话挂载继承。"""

from fastapi import HTTPException
from open_webui.models.folders import Folders
from open_webui.utils.access_control.folders import has_folder_access
from open_webui.utils.projects import project_config

SKILL_MODES = ('chat', 'assistant', 'project')


def _mapping(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump()
    return value if isinstance(value, dict) else {}


def string_ids(value):
    return list(dict.fromkeys(item for item in value if isinstance(item, str) and item)) if isinstance(value, list) else []


def skill_available(skill, mode: str, capabilities: dict | None = None, terminal_available: bool = True) -> bool:
    skill = _mapping(skill)
    meta = _mapping(skill.get('meta'))
    modes = _mapping(meta.get('modes'))
    if skill.get('is_active', True) is False or modes.get(mode, True) is False:
        return False
    capabilities = capabilities or {}
    for requirement in string_ids(meta.get('requires')):
        if capabilities.get(requirement, True) is False:
            return False
        if requirement == 'terminal' and not terminal_available:
            return False
    return True


def attachment_overrides(value):
    if value is None:
        return None
    if not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1:
        raise HTTPException(400, '无效的会话挂载配置')
    result = {'version': 1}
    if 'defaults' in value:
        defaults = value['defaults']
        if not isinstance(defaults, dict):
            raise HTTPException(400, '会话初始挂载配置必须为对象')
        result['defaults'] = {}
        for kind in ('skills', 'tools'):
            items = defaults.get(kind)
            if not isinstance(items, list) or any(not isinstance(item, str) or not item for item in items):
                raise HTTPException(400, '会话初始挂载引用必须为非空字符串列表')
            result['defaults'][kind] = string_ids(items)
    for kind in ('skills', 'tools'):
        entry = value.get(kind, {})
        if not isinstance(entry, dict):
            raise HTTPException(400, '会话挂载增减项必须为对象')
        result[kind] = {}
        for key in ('added', 'removed'):
            ids = entry.get(key, [])
            if not isinstance(ids, list) or any(not isinstance(item, str) or not item for item in ids):
                raise HTTPException(400, '会话挂载引用必须为非空字符串列表')
            result[kind][key] = string_ids(ids)
    return result


def resolve_attachments(defaults, selected, overrides, kind):
    base = string_ids((overrides.get('defaults') or {}).get(kind, defaults) if overrides else defaults)
    if overrides is None:
        if kind == 'tools' and isinstance(selected, list):
            return string_ids(selected)
        return string_ids([*base, *string_ids(selected)])
    entry = overrides[kind]
    removed = set(entry['removed'])
    return [item for item in string_ids([*base, *entry['added']]) if item not in removed]


def validate_attachment_defaults(data):
    if data is None:
        return
    for key in ('skill_ids', 'tool_ids'):
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise HTTPException(400, f'{key} 必须为非空字符串列表或 null')
        data[key] = string_ids(value)


async def folder_attachments(folder_id, user, db=None):
    result = {
        'mode': 'chat', 'skill_ids': [], 'tool_ids': [],
        'skill_source_id': None, 'tool_source_id': None,
        'project_id': None, 'terminal_id': None,
    }
    if not folder_id:
        return result
    result['mode'] = 'assistant'
    seen = set()
    while folder_id:
        if folder_id in seen:
            raise HTTPException(409, '分组目录存在循环归属')
        seen.add(folder_id)
        folder = await Folders.get_folder_by_id(folder_id, db=db)
        if not folder:
            if len(seen) == 1:
                raise HTTPException(404, '分组不存在或不可访问')
            break
        if user.role != 'admin' and not await has_folder_access(user.id, folder, 'read', db):
            if len(seen) == 1:
                raise HTTPException(404, '分组不存在或不可访问')
            break
        data = folder.data or {}
        for kind in ('skill', 'tool'):
            key = f'{kind}_ids'
            source = f'{kind}_source_id'
            if result[source] is None and isinstance(data.get(key), list):
                result[key] = string_ids(data[key])
                result[source] = folder.id
        project = project_config(folder)
        if project:
            result.update(mode='project', project_id=folder.id, terminal_id=project['terminal_id'])
            break
        folder_id = folder.parent_id
    return result
