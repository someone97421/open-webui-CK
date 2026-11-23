import aiohttp

from open_webui.models.config import Config


class RelayInterrupted(ConnectionError):
    """Kept for upstream call sites; this build has no Tether relay, so it is never raised."""


class RelayClient:
    """Placeholder for upstream call sites; unreachable because no Tether connections are listed."""

    def __init__(self, *args, **kwargs):
        raise RelayInterrupted('Tether is not available in this build')


async def get_tether_connections(user_id, type):
    return []


async def get_terminal_connections(user, include_templates=True):
    connections = list(await Config.get('terminal_server.connections', []) or [])
    if include_templates:
        from open_webui.utils.terminals import list_template_connections

        managed = [c for c in connections if c.get('server_type') == 'orchestrator']
        connections = [c for c in connections if c.get('server_type') != 'orchestrator']
        connections.extend(await list_template_connections(user, managed))
    return connections


def get_terminal_client(url, user_id=None, service='open_terminal', **kwargs):
    return aiohttp.ClientSession(**kwargs)
