from collections.abc import Iterable
from typing import Final

from aiogram import Dispatcher, Router
from aiogram_dialog import Dialog

from goldy.presentation.telegram.handlers.admin import (
    ADMIN_DIALOG,
    router as admin_router,
)
from goldy.presentation.telegram.handlers.common.fallback import (
    router as fallback_router,
)
from goldy.presentation.telegram.handlers.common.help import router as help_router
from goldy.presentation.telegram.handlers.errors import router as errors_router
from goldy.presentation.telegram.handlers.profile import (
    PROFILE_DIALOG,
    router as profile_router,
)
from goldy.presentation.telegram.handlers.start.handler import router as start_router

ROUTERS: Final[Iterable[Router]] = (
    start_router,
    help_router,
    profile_router,
    admin_router,
    fallback_router,
    errors_router,
)
"""Every router, in the order aiogram tries them.

Order is load-bearing at the end. ``fallback_router`` matches everything, so
anything below it would never run; ``errors_router`` observes failures rather
than messages, and sits last to say so.
"""

DIALOGS: Final[Iterable[Dialog]] = (PROFILE_DIALOG, ADMIN_DIALOG)
"""Dialogs, which are routers too — aiogram-dialog builds them as such."""


def setup_all_handlers(dp: Dispatcher) -> None:
    """Attaches every router to the dispatcher, in matching order."""
    for router in ROUTERS:
        dp.include_router(router)


def setup_all_dialogs(dp: Dispatcher) -> None:
    """Attaches every aiogram-dialog window.

    Separate from the handlers because ``setup_dialogs`` has to run after them
    — it registers the machinery the dialogs need, and it needs to see them
    first.
    """
    for dialog in DIALOGS:
        dp.include_router(dialog)
