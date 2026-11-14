import time

from open_webui.env import REDIS_KEY_PREFIX
from open_webui.utils.json_codec import JSONCodec


_INPUT_TTL = 86400
_inputs: dict[str, dict] = {}


def _key(task_id: str) -> str:
    return f'{REDIS_KEY_PREFIX}:task-input:{task_id}'


def _decode(value):
    return value.decode() if isinstance(value, bytes) else value


async def open_task_input(redis, task_id: str, chat_id: str, message_id: str, user_id: str):
    state = {'state': 'open', 'chat_id': chat_id, 'message_id': message_id, 'user_id': user_id, 'seq': 0}
    if redis:
        key = _key(task_id)
        await redis.hset(key, mapping=state)
        await redis.expire(key, _INPUT_TTL)
    else:
        _inputs[task_id] = {**state, 'pending': [], 'receipts': {}, 'updated': time.monotonic()}


async def queue_task_input(redis, task_id: str, chat_id: str, message_id: str, user_id: str, item: dict):
    if redis:
        result = await redis.eval(
            """
            if redis.call('HGET', KEYS[1], 'chat_id') ~= ARGV[1]
                or redis.call('HGET', KEYS[1], 'message_id') ~= ARGV[2]
                or redis.call('HGET', KEYS[1], 'user_id') ~= ARGV[3] then return 'closed' end
            local receipt = redis.call('HGET', KEYS[1], 'receipt:' .. ARGV[4])
            if receipt then return receipt end
            if redis.call('HGET', KEYS[1], 'state') ~= 'open' then return 'closed' end
            local seq = redis.call('HINCRBY', KEYS[1], 'seq', 1)
            redis.call('HSET', KEYS[1], 'pending:' .. seq, ARGV[5], 'receipt:' .. ARGV[4], 'pending')
            redis.call('EXPIRE', KEYS[1], ARGV[6])
            return 'pending'
            """,
            1, _key(task_id), chat_id, message_id, user_id, item['id'], JSONCodec.dumps(item), _INPUT_TTL,
        )
        return _decode(result)
    state = _inputs.get(task_id)
    if not state or any(state[key] != value for key, value in
                        (('chat_id', chat_id), ('message_id', message_id), ('user_id', user_id))):
        return 'closed'
    receipt = state['receipts'].get(item['id'])
    if receipt:
        return receipt
    if state['state'] != 'open':
        return 'closed'
    state['pending'].append(item)
    state['receipts'][item['id']] = 'pending'
    return 'pending'


async def take_task_inputs(redis, task_id: str, close_if_empty: bool = False) -> list[dict]:
    if redis:
        result = await redis.eval(
            """
            if redis.call('HGET', KEYS[1], 'state') ~= 'open' then return {} end
            local fields = redis.call('HGETALL', KEYS[1])
            local entries = {}
            for i = 1, #fields, 2 do
                local seq = string.match(fields[i], '^pending:(%d+)$')
                if seq then table.insert(entries, {tonumber(seq), fields[i], fields[i+1]}) end
            end
            table.sort(entries, function(a,b) return a[1] < b[1] end)
            local result = {}
            for _, entry in ipairs(entries) do
                local item = cjson.decode(entry[3])
                redis.call('HDEL', KEYS[1], entry[2])
                redis.call('HSET', KEYS[1], 'receipt:' .. item.id, 'claimed')
                table.insert(result, entry[3])
            end
            if #result == 0 and ARGV[1] == '1' then redis.call('HSET', KEYS[1], 'state', 'closed') end
            return result
            """,
            1, _key(task_id), '1' if close_if_empty else '0',
        )
        return [JSONCodec.loads(entry) for entry in result]
    state = _inputs.get(task_id)
    if not state or state['state'] != 'open':
        return []
    result, state['pending'] = state['pending'], []
    for item in result:
        state['receipts'][item['id']] = 'claimed'
    if not result and close_if_empty:
        state['state'] = 'closed'
    return result


async def finish_task_inputs(redis, task_id: str, items: list[dict], delivered: bool):
    if not items:
        return
    value = 'delivered' if delivered else 'failed'
    if redis:
        await redis.hset(_key(task_id), mapping={f'receipt:{item["id"]}': value for item in items})
    elif task_id in _inputs:
        _inputs[task_id]['receipts'].update({item['id']: value for item in items})


async def get_task_input_status(redis, task_id: str, input_id: str, chat_id: str, message_id: str, user_id: str):
    if redis:
        values = await redis.hmget(_key(task_id), 'chat_id', 'message_id', 'user_id', f'receipt:{input_id}')
        owner_chat, owner_message, owner_user, receipt = map(_decode, values)
        return receipt if (owner_chat, owner_message, owner_user) == (chat_id, message_id, user_id) else None
    state = _inputs.get(task_id)
    if not state or (state['chat_id'], state['message_id'], state['user_id']) != (chat_id, message_id, user_id):
        return None
    return state['receipts'].get(input_id)


async def close_task_input(redis, task_id: str):
    if redis:
        await redis.eval(
            """
            if redis.call('EXISTS', KEYS[1]) == 0 then return end
            local fields = redis.call('HGETALL', KEYS[1])
            for i = 1, #fields, 2 do
                local field, value = fields[i], fields[i+1]
                if string.sub(field, 1, 8) == 'receipt:' and (value == 'pending' or value == 'claimed') then
                    redis.call('HSET', KEYS[1], field, 'closed')
                elseif string.sub(field, 1, 8) == 'pending:' then
                    redis.call('HDEL', KEYS[1], field)
                end
            end
            redis.call('HSET', KEYS[1], 'state', 'closed')
            redis.call('EXPIRE', KEYS[1], ARGV[1])
            """, 1, _key(task_id), _INPUT_TTL,
        )
    else:
        state = _inputs.get(task_id)
        if state:
            state['state'] = 'closed'
            state['pending'] = []
            state['receipts'] = {key: 'closed' if value in {'pending', 'claimed'} else value
                                 for key, value in state['receipts'].items()}
            state['updated'] = time.monotonic()
        cutoff = time.monotonic() - _INPUT_TTL
        for key in [key for key, item in _inputs.items() if item['state'] == 'closed' and item['updated'] < cutoff]:
            _inputs.pop(key, None)
