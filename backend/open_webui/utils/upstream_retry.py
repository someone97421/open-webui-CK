import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import aiohttp
from fastapi import HTTPException
from starlette.responses import Response

from open_webui.env import UPSTREAM_MAX_ATTEMPTS, UPSTREAM_RETRY_BASE_DELAY, UPSTREAM_RETRY_MAX_DELAY

log = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 529})
RETRY_AFTER_MAX_SECONDS = 60.0


class StreamInterruptedError(ConnectionError):
    """The upstream stream ended before its protocol completion marker."""


def is_retryable_status(status: Any) -> bool:
    return status in RETRYABLE_STATUS_CODES


def is_retryable_error(error: BaseException) -> bool:
    if isinstance(error, HTTPException):
        return is_retryable_status(error.status_code)
    return isinstance(error, (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError))


def get_retry_after_seconds(response: Any) -> Optional[float]:
    headers = getattr(response, 'headers', None) or {}
    for name, scale in (('retry-after-ms', 0.001), ('retry-after', 1.0)):
        value = headers.get(name)
        if value is None:
            continue
        try:
            seconds = float(value) * scale
        except (TypeError, ValueError):
            continue
        if seconds >= 0:
            return min(seconds, RETRY_AFTER_MAX_SECONDS)
    return None


def describe_error(error: BaseException) -> str:
    if isinstance(error, HTTPException):
        return f'HTTP {error.status_code}: {error.detail}'
    return f'{type(error).__name__}: {error}' if str(error) else type(error).__name__


class RetryBudget:
    """Attempt budget for one model round, shared by request failures, broken streams and empty replies."""

    def __init__(self, max_attempts: Optional[int] = None):
        self.max_attempts = max(1, max_attempts if max_attempts is not None else UPSTREAM_MAX_ATTEMPTS)
        self.attempt = 1

    def can_retry(self) -> bool:
        return self.attempt < self.max_attempts

    async def wait(self, label: str, reason: str, retry_after: Optional[float] = None) -> None:
        delay = min(UPSTREAM_RETRY_MAX_DELAY, UPSTREAM_RETRY_BASE_DELAY * 2 ** (self.attempt - 1))
        delay *= random.uniform(0.8, 1.2)
        if retry_after is not None:
            delay = max(delay, retry_after)
        log.warning(
            '%s failed (%s); retrying %d/%d in %.1fs',
            label,
            reason,
            self.attempt,
            self.max_attempts - 1,
            delay,
        )
        await asyncio.sleep(delay)
        self.attempt += 1


async def request_with_retry(generate: Callable[[], Awaitable[Any]], budget: RetryBudget, label: str) -> Any:
    """Retry transient request failures; the last result or error is returned once the budget is spent."""
    while True:
        try:
            response = await generate()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not is_retryable_error(error) or not budget.can_retry():
                raise
            await budget.wait(label, describe_error(error))
            continue

        status = response.status_code if isinstance(response, Response) else 200
        if not is_retryable_status(status) or not budget.can_retry():
            return response
        await budget.wait(label, f'HTTP {status}', get_retry_after_seconds(response))
