import aiohttp

from open_webui.models.config import Config


async def get_terminal_connections(user):
    return await Config.get('terminal_server.connections', []) or []


def get_terminal_client(base_url, user_id=None, **kwargs):
    return aiohttp.ClientSession(**kwargs)
