import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Final, final, override

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger: Final[logging.Logger] = logging.getLogger(__name__)

SLOW_UPDATE_SECONDS: Final[float] = 1.0


@final
class TimingMiddleware(BaseMiddleware):
    """Times every update, and says so out loud when one drags.

    A bot that feels slow rarely announces why: the update still succeeds, just
    late. Logging the outliers at ``warning`` is what makes the first slow query
    visible before anyone starts complaining.
    """

    @override
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        started = time.perf_counter()
        try:
            return await handler(event, data)
        finally:
            elapsed = time.perf_counter() - started
            log = logger.warning if elapsed > SLOW_UPDATE_SECONDS else logger.debug
            log("update handled in %.3fs", elapsed)
