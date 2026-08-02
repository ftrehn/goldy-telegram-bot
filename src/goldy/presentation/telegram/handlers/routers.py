from typing import Final

from aiogram import Dispatcher, Router

from goldy.presentation.telegram.handlers.common.fallback import (
    router as fallback_router,
)
from goldy.presentation.telegram.handlers.common.help import router as help_router
from goldy.presentation.telegram.handlers.common.me import router as me_router
from goldy.presentation.telegram.handlers.errors import router as errors_router
from goldy.presentation.telegram.handlers.start.handler import router as start_router

ROUTERS: Final[tuple[Router, ...]] = (
    start_router,
    help_router,
    me_router,
    fallback_router,
    errors_router,
)
"""Every router, in the order aiogram tries them.

Order is load-bearing at the end. ``fallback_router`` matches everything, so
anything below it would never run; ``errors_router`` observes failures rather
than messages, and sits last to say so.
"""


def setup_all_handlers(dp: Dispatcher) -> None:
    """Attaches every router to the dispatcher, in matching order."""
    for router in ROUTERS:
        dp.include_router(router)


def setup_all_dialogs(dp: Dispatcher) -> None:
    """Attaches every aiogram-dialog window.

    Empty until the profile and admin screens land — those are the ones with
    state worth a dialog. Commands without state stay ordinary handlers.
    """
