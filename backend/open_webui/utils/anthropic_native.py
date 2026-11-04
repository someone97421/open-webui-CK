"""网页 Chat Completions 与 Anthropic Messages 的原生格式转换。

未指定输出上限时使用 4096，避免依赖模型名称推断额度或思考参数。
"""

import codecs
import re
import time
from copy import deepcopy
from uuid import uuid4

from open_webui.utils.json_codec import JSONCodec


_REASONING_FORMAT = 'anthropic-claude-v1'
_LINE_END = re.compile(r'\r\n|\r|\n')
_STOP_REASONS = {
    'end_turn': 'stop',
    'stop_sequence': 'stop',
    'max_tokens': 'length',
    'model_context_window_exceeded': 'length',
    'tool_use': 'tool_calls',
    'pause_turn': 'stop',
    'refusal': 'content_filter',
}


def _cache_control(source: dict, target: dict) -> dict:
    if 'cache_control' in source:
        target['cache_control'] = deepcopy(source['cache_control'])
    return target


def _image_source(url: str) -> dict:
    if not isinstance(url, str):
        raise ValueError('图片 URL 必须是字符串')
    if url.startswith('data:'):
        header, separator, data = url.partition(',')
        if not separator or not header.endswith(';base64'):
            raise ValueError('Anthropic 图片 data URL 必须使用 base64')
        media_type = header[5:-7]
        if not media_type.startswith('image/') or not data:
            raise ValueError('图片 data URL 缺少媒体类型或数据')
        return {'type': 'base64', 'media_type': media_type, 'data': data}
    if url.startswith(('https://', 'http://')):
        return {'type': 'url', 'url': url}
    raise ValueError('Anthropic 图片必须使用 HTTP URL 或 base64 data URL')


def _content_blocks(content) -> list:
    if content is None:
        return []
    if isinstance(content, str):
        return [{'type': 'text', 'text': content}] if content else []
    if not isinstance(content, list):
        raise ValueError('消息 content 必须是字符串或内容块列表')
    result = []
    for block in content:
        if isinstance(block, str):
            if block:
                result.append({'type': 'text', 'text': block})
            continue
        if not isinstance(block, dict):
            raise ValueError('消息内容块必须是对象')
        kind = block.get('type')
        if kind in ('text', 'input_text', 'output_text'):
            if block.get('text'):
                result.append(_cache_control(block, {'type': 'text', 'text': block['text']}))
        elif kind in ('image_url', 'input_image'):
            image = block.get('image_url', {})
            url = image.get('url') if isinstance(image, dict) else image
            result.append(_cache_control(block, {'type': 'image', 'source': _image_source(url)}))
        elif kind in ('image', 'tool_use', 'tool_result', 'redacted_thinking'):
            result.append(deepcopy(block))
        elif kind == 'thinking':
            if block.get('signature'):
                result.append(deepcopy(block))
        else:
            raise ValueError(f'不支持的 Anthropic 消息内容类型: {kind}')
    return result


def _reasoning_blocks(message: dict) -> list:
    details = message.get('reasoning_details')
    if details is None:
        provider_fields = message.get('provider_specific_fields')
        if isinstance(provider_fields, dict):
            details = provider_fields.get('reasoning_details')
    if isinstance(details, dict):
        details = [details]
    result = []
    ordered = [detail for detail in (details or []) if isinstance(detail, dict)]
    ordered.sort(key=lambda detail: detail.get('index') if isinstance(detail.get('index'), int) else 0)
    for detail in ordered:
        if not isinstance(detail, dict) or detail.get('format') != _REASONING_FORMAT:
            continue
        if detail.get('type') == 'reasoning.text' and detail.get('signature'):
            result.append(
                {
                    'type': 'thinking',
                    'thinking': detail.get('text', ''),
                    'signature': detail['signature'],
                }
            )
        elif detail.get('type') == 'reasoning.encrypted' and detail.get('data'):
            result.append({'type': 'redacted_thinking', 'data': detail['data']})
    return result


def _tool_input(arguments) -> dict:
    if isinstance(arguments, str):
        arguments = JSONCodec.loads(arguments) if arguments.strip() else {}
    if not isinstance(arguments, dict):
        raise ValueError('工具参数必须是 JSON 对象')
    return deepcopy(arguments)


def _convert_tool_choice(choice):
    if choice is None:
        return None
    if isinstance(choice, str):
        kinds = {'auto': 'auto', 'none': 'none', 'required': 'any'}
        if choice not in kinds:
            raise ValueError(f'不支持的 tool_choice: {choice}')
        return {'type': kinds[choice]}
    if isinstance(choice, dict):
        if choice.get('type') == 'function':
            name = choice.get('function', {}).get('name')
            if not name:
                raise ValueError('指定工具时必须提供工具名称')
            return {'type': 'tool', 'name': name}
        if choice.get('type') in ('auto', 'none', 'any', 'tool'):
            converted = {'type': choice['type']}
            if choice['type'] == 'tool':
                if not choice.get('name'):
                    raise ValueError('指定工具时必须提供工具名称')
                converted['name'] = choice['name']
            if 'disable_parallel_tool_use' in choice:
                converted['disable_parallel_tool_use'] = choice['disable_parallel_tool_use']
            return converted
    raise ValueError('不支持的 tool_choice 格式')


def convert_chat_completions_to_anthropic(payload: dict) -> dict:
    """转换请求且不修改输入；max_completion_tokens 优先，默认额度为 4096。"""
    result = {
        key: deepcopy(payload[key])
        for key in ('model', 'temperature', 'top_p', 'top_k', 'stream', 'thinking', 'output_config', 'service_tier', 'cache_control')
        if key in payload and payload[key] is not None
    }
    limit = payload.get('max_completion_tokens')
    if limit is None:
        limit = payload.get('max_tokens')
    result['max_tokens'] = 4096 if limit is None else limit
    stop = payload.get('stop', payload.get('stop_sequences'))
    if stop is not None:
        result['stop_sequences'] = [stop] if isinstance(stop, str) else deepcopy(stop)

    metadata = payload.get('metadata')
    user_id = metadata.get('user_id') if isinstance(metadata, dict) else None
    if user_id is None:
        user_id = payload.get('user')
    if user_id is not None:
        if not isinstance(user_id, str) or len(user_id) > 256:
            raise ValueError('Anthropic metadata.user_id 必须是不超过 256 个字符的字符串')
        result['metadata'] = {'user_id': user_id}

    system = _content_blocks(payload.get('system'))
    messages = []
    for message in payload.get('messages', []):
        role = message.get('role')
        if role in ('system', 'developer'):
            system.extend(_content_blocks(message.get('content')))
            continue
        if role == 'tool':
            if not message.get('tool_call_id'):
                raise ValueError('工具结果缺少 tool_call_id')
            tool_result = {
                'type': 'tool_result',
                'tool_use_id': message['tool_call_id'],
                'content': _content_blocks(message.get('content')),
            }
            if 'is_error' in message:
                tool_result['is_error'] = message['is_error']
            blocks = [_cache_control(message, tool_result)]
            role = 'user'
        elif role in ('user', 'assistant'):
            blocks = _content_blocks(message.get('content'))
            if role == 'assistant':
                thinking = [block for block in blocks if block['type'] in ('thinking', 'redacted_thinking')]
                blocks = [block for block in blocks if block['type'] not in ('thinking', 'redacted_thinking')]
                blocks = (_reasoning_blocks(message) or thinking) + blocks
                for call in message.get('tool_calls') or []:
                    if call.get('type', 'function') != 'function':
                        raise ValueError('Anthropic 仅支持 function 工具调用')
                    function = call['function']
                    blocks.append(
                        {
                            'type': 'tool_use',
                            'id': call['id'],
                            'name': function['name'],
                            'input': _tool_input(function.get('arguments', '{}')),
                        }
                    )
        else:
            raise ValueError(f'不支持的消息角色: {role}')
        if not blocks:
            continue
        if messages and messages[-1]['role'] == role:
            messages[-1]['content'].extend(blocks)
        else:
            messages.append({'role': role, 'content': blocks})
    for message in messages:
        if message['role'] == 'assistant':
            message['content'].sort(key=lambda block: block['type'] not in ('thinking', 'redacted_thinking'))
        else:
            message['content'].sort(key=lambda block: block['type'] != 'tool_result')
    if messages and messages[-1]['role'] == 'assistant':
        blocks = messages[-1]['content']
        while blocks and blocks[-1]['type'] == 'text':
            blocks[-1]['text'] = blocks[-1]['text'].rstrip()
            if blocks[-1]['text']:
                break
            blocks.pop()
        if not blocks:
            messages.pop()
    if any(block['type'] != 'text' for block in system):
        raise ValueError('Anthropic system 仅支持文本内容')
    if system:
        result['system'] = system
    result['messages'] = messages

    if payload.get('tools'):
        tools = []
        for tool in payload['tools']:
            if tool.get('type', 'function') != 'function':
                raise ValueError('Anthropic 仅支持 function 工具定义')
            function = tool['function']
            converted = {
                'name': function['name'],
                'input_schema': deepcopy(function.get('parameters') or {'type': 'object', 'properties': {}}),
            }
            if function.get('description') is not None:
                converted['description'] = function['description']
            tools.append(_cache_control(tool, _cache_control(function, converted)))
        result['tools'] = tools
    choice = _convert_tool_choice(payload.get('tool_choice')) if result.get('tools') else None
    if payload.get('parallel_tool_calls') is not None and result.get('tools'):
        choice = choice or {'type': 'auto'}
        if choice['type'] != 'none':
            choice['disable_parallel_tool_use'] = not payload['parallel_tool_calls']
    if choice is not None:
        result['tool_choice'] = choice

    effort = payload.get('reasoning_effort')
    if isinstance(effort, str):
        effort = effort.strip().lower() or None
    thinking = result.get('thinking') or {}
    output_config = result.get('output_config') or {}
    if effort is not None and thinking.get('type') in (None, 'adaptive'):
        if 'effort' not in output_config:
            levels = {'minimal': 'low', 'low': 'low', 'medium': 'medium', 'high': 'high', 'xhigh': 'xhigh', 'max': 'max'}
            if effort in ('none', 'disabled'):
                if 'thinking' not in result:
                    result['thinking'] = {'type': 'disabled'}
            elif effort in levels:
                output_config['effort'] = levels[effort]
                result['output_config'] = output_config
                result.setdefault('thinking', {'type': 'adaptive'})
            else:
                raise ValueError(
                    f'不支持的 Anthropic reasoning_effort: {effort!r}，'
                    '可用值为 none、disabled、minimal、low、medium、high、xhigh、max'
                )
    thinking = result.get('thinking') or {}
    if thinking.get('type') in ('enabled', 'adaptive'):
        last_assistant = next((message for message in reversed(messages) if message['role'] == 'assistant'), None)
        continuing_tools = messages and messages[-1]['role'] == 'user' and any(
            block['type'] == 'tool_result' for block in messages[-1]['content']
        )
        unsigned_tools = continuing_tools and last_assistant and (
            any(block['type'] == 'tool_use' for block in last_assistant['content'])
            and not any(block['type'] in ('thinking', 'redacted_thinking') for block in last_assistant['content'])
        )
        if (choice or {}).get('type') in ('any', 'tool') or unsigned_tools:
            result.pop('thinking', None)
        else:
            for key in ('temperature', 'top_p', 'top_k'):
                result.pop(key, None)
            budget = thinking.get('budget_tokens')
            if thinking.get('type') == 'enabled' and isinstance(budget, int) and result['max_tokens'] <= budget:
                if limit is not None:
                    raise ValueError('max_tokens 必须大于 thinking.budget_tokens，请提高输出上限')
                result['max_tokens'] = budget + 4096
    return result


def _usage(usage: dict) -> dict:
    cached = usage.get('cache_read_input_tokens') or 0
    cache_creation = usage.get('cache_creation_input_tokens') or 0
    prompt = (usage.get('input_tokens') or 0) + cached + cache_creation
    completion = usage.get('output_tokens') or 0
    return {
        'prompt_tokens': prompt,
        'completion_tokens': completion,
        'total_tokens': prompt + completion,
        'cache_read_input_tokens': cached,
        'cache_creation_input_tokens': cache_creation,
        'prompt_tokens_details': {'cached_tokens': cached, 'cache_creation_tokens': cache_creation},
    }


def _finish_reason(reason):
    return _STOP_REASONS.get(reason, reason)


def _reasoning_detail(index: int, text: str = '', signature: str = '') -> dict:
    return {
        'type': 'reasoning.text',
        'format': _REASONING_FORMAT,
        'index': index,
        'text': text,
        'signature': signature,
    }


def _encrypted_detail(index: int, data: str) -> dict:
    return {'type': 'reasoning.encrypted', 'format': _REASONING_FORMAT, 'index': index, 'data': data}


def convert_anthropic_to_chat_completion(response: dict) -> dict:
    """将完整 Messages 响应转换为网页使用的 Chat Completions 响应。"""
    if response.get('type') == 'error' or 'error' in response:
        return {'error': deepcopy(response.get('error', response))}
    text = []
    reasoning = []
    details = []
    calls = []
    for index, block in enumerate(response.get('content', [])):
        kind = block.get('type')
        if kind == 'text':
            text.append(block.get('text', ''))
        elif kind == 'tool_use':
            calls.append(
                {
                    'id': block['id'],
                    'type': 'function',
                    'function': {'name': block['name'], 'arguments': JSONCodec.dumps(block.get('input', {}))},
                }
            )
        elif kind == 'thinking':
            thinking = block.get('thinking', '')
            reasoning.append(thinking)
            details.append(_reasoning_detail(index, thinking, block.get('signature', '')))
        elif kind == 'redacted_thinking':
            details.append(_encrypted_detail(index, block['data']))
        else:
            raise ValueError(f'不支持的 Anthropic 响应内容类型: {kind}')
    message = {'role': 'assistant', 'content': ''.join(text) if text else None}
    if calls:
        message['tool_calls'] = calls
    if reasoning:
        message['reasoning_content'] = ''.join(reasoning)
    if details:
        message['reasoning_details'] = details
    return {
        'id': response.get('id') or f'chatcmpl-{uuid4()}',
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': response.get('model', ''),
        'choices': [{'index': 0, 'message': message, 'finish_reason': _finish_reason(response.get('stop_reason'))}],
        'usage': _usage(response.get('usage') or {}),
    }


async def _sse_events(body_iterator):
    decoder = codecs.getincrementaldecoder('utf-8')()
    buffer = ''
    at_start = True
    event_name = ''
    data_lines = []

    def consume(line):
        nonlocal event_name, data_lines
        if line == '':
            if not data_lines:
                event_name = ''
                return None
            data = '\n'.join(data_lines)
            event = event_name
            event_name, data_lines = '', []
            if data == '[DONE]':
                return event, data
            parsed = JSONCodec.loads(data)
            if not isinstance(parsed, dict):
                raise ValueError('Anthropic SSE data 必须是 JSON 对象')
            return event, parsed
        if line.startswith(':'):
            return None
        field, separator, value = line.partition(':')
        if separator and value.startswith(' '):
            value = value[1:]
        if field == 'event':
            event_name = value
        elif field == 'data':
            data_lines.append(value)
        return None

    async for chunk in body_iterator:
        if isinstance(chunk, str):
            if decoder.getstate()[0]:
                raise UnicodeDecodeError('utf-8', decoder.getstate()[0], 0, 1, '字节片段尚未完成')
            text = chunk
        elif isinstance(chunk, (bytes, bytearray, memoryview)):
            text = decoder.decode(bytes(chunk))
        else:
            raise TypeError('SSE 片段必须是字符串或字节')
        if at_start and text:
            text = text.removeprefix('\ufeff')
            at_start = False
        buffer += text
        while match := _LINE_END.search(buffer):
            if match.group() == '\r' and match.end() == len(buffer):
                break
            line, buffer = buffer[:match.start()], buffer[match.end():]
            event = consume(line)
            if event is not None:
                yield event
    buffer += decoder.decode(b'', final=True)
    while match := _LINE_END.search(buffer):
        line, buffer = buffer[:match.start()], buffer[match.end():]
        event = consume(line)
        if event is not None:
            yield event
    if buffer:
        event = consume(buffer)
        if event is not None:
            yield event
    event = consume('')
    if event is not None:
        yield event


async def convert_anthropic_stream_to_chat_completions(body_iterator):
    """转换任意分片的 SSE；解析异常和提前断流直接向调用方传播。"""
    completion_id = f'chatcmpl-{uuid4()}'
    created = int(time.time())
    model = ''
    started = False
    stopped = False
    blocks = {}
    tool_count = 0
    usage = {}
    finish_reason = None

    def chunk(delta, finish=None, final_usage=False):
        result = {
            'id': completion_id,
            'object': 'chat.completion.chunk',
            'created': created,
            'model': model,
            'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}],
        }
        if final_usage:
            result['usage'] = _usage(usage)
        return f'data: {JSONCodec.dumps(result)}\n\n'

    async for event_name, event in _sse_events(body_iterator):
        if event == '[DONE]':
            if not stopped:
                raise ValueError('Anthropic SSE 缺少 message_stop')
            continue
        kind = event.get('type') or event_name
        if kind == 'ping':
            continue
        if kind == 'error':
            yield f'data: {JSONCodec.dumps({"error": event.get("error", event)})}\n\n'
            return
        if stopped:
            raise ValueError('Anthropic message_stop 后收到额外事件')
        if kind == 'message_start':
            if started:
                raise ValueError('Anthropic SSE 重复 message_start')
            message = event['message']
            completion_id = message.get('id') or completion_id
            model = message.get('model', '')
            usage.update(message.get('usage') or {})
            started = True
            yield chunk({'role': 'assistant', 'content': ''})
            continue
        if not started:
            raise ValueError('Anthropic SSE 缺少 message_start')
        if kind == 'content_block_start':
            index = event['index']
            if index in blocks:
                raise ValueError('Anthropic SSE 重复内容块索引')
            block = event['content_block']
            block_type = block['type']
            state = {'type': block_type, 'closed': False}
            blocks[index] = state
            if block_type == 'text':
                if block.get('text'):
                    yield chunk({'content': block['text']})
            elif block_type == 'thinking':
                state['signature'] = block.get('signature', '')
                thinking = block.get('thinking', '')
                state['thinking'] = [thinking]
                if thinking:
                    yield chunk({'reasoning_content': thinking})
            elif block_type == 'redacted_thinking':
                state['data'] = block['data']
            elif block_type == 'tool_use':
                state.update(tool_index=tool_count, initial_input=block.get('input', {}), fragments=[])
                tool_count += 1
                yield chunk(
                    {
                        'tool_calls': [
                            {
                                'index': state['tool_index'],
                                'id': block['id'],
                                'type': 'function',
                                'function': {'name': block['name'], 'arguments': ''},
                            }
                        ]
                    }
                )
            else:
                raise ValueError(f'不支持的 Anthropic 流内容类型: {block_type}')
        elif kind in ('content_block_delta', 'content_block_stop'):
            index = event['index']
            state = blocks[index]
            if state['closed']:
                raise ValueError('Anthropic SSE 内容块已结束')
            if kind == 'content_block_stop':
                if state['type'] == 'tool_use':
                    arguments_text = ''.join(state['fragments'])
                    if arguments_text.strip():
                        _tool_input(arguments_text)
                    else:
                        arguments = JSONCodec.dumps(_tool_input(state['initial_input']))
                        yield chunk(
                            {'tool_calls': [{'index': state['tool_index'], 'function': {'arguments': arguments}}]}
                        )
                elif state['type'] == 'thinking':
                    detail = _reasoning_detail(index, ''.join(state['thinking']), state['signature'])
                    yield chunk({'reasoning_details': [detail]})
                elif state['type'] == 'redacted_thinking':
                    yield chunk({'reasoning_details': [_encrypted_detail(index, state['data'])]})
                state['closed'] = True
                continue
            delta = event['delta']
            delta_type = delta['type']
            if delta_type == 'text_delta' and state['type'] == 'text':
                yield chunk({'content': delta['text']})
            elif delta_type == 'thinking_delta' and state['type'] == 'thinking':
                thinking = delta['thinking']
                state['thinking'].append(thinking)
                yield chunk({'reasoning_content': thinking})
            elif delta_type == 'signature_delta' and state['type'] == 'thinking':
                state['signature'] += delta['signature']
            elif delta_type == 'input_json_delta' and state['type'] == 'tool_use':
                if state['initial_input']:
                    raise ValueError('Anthropic 工具参数同时包含初始对象和 JSON 增量')
                fragment = delta['partial_json']
                state['fragments'].append(fragment)
                yield chunk({'tool_calls': [{'index': state['tool_index'], 'function': {'arguments': fragment}}]})
            else:
                if delta_type in ('text_delta', 'thinking_delta', 'signature_delta', 'input_json_delta'):
                    raise ValueError(f'不匹配的 Anthropic 流增量类型: {delta_type}')
        elif kind == 'message_delta':
            usage.update(event.get('usage') or {})
            reason = event.get('delta', {}).get('stop_reason')
            if reason is not None:
                finish_reason = _finish_reason(reason)
        elif kind == 'message_stop':
            if any(not state['closed'] for state in blocks.values()):
                raise ValueError('Anthropic SSE 存在未结束的内容块')
            if finish_reason is None:
                finish_reason = 'tool_calls' if tool_count else 'stop'
            stopped = True
        else:
            continue
    if not stopped:
        raise ValueError('Anthropic SSE 在 message_stop 前中断')
    yield chunk({}, finish=finish_reason, final_usage=True)
    yield 'data: [DONE]\n\n'
