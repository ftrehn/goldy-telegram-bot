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

FEATURE_ROUTERS: Final[Iterable[Router]] = (
    start_router,
    help_router,
    profile_router,
    admin_router,
)
"""The routers that claim an update because they recognise it."""

DIALOGS: Final[Iterable[Dialog]] = (PROFILE_DIALOG, ADMIN_DIALOG)
"""Dialogs, which are routers too — aiogram-dialog builds them as such.

They must be attached before ``fallback_router``, and that is not a style
preference. A window waiting on typed input — a new name, a reason for a block
— matches through the dialog's own ``MessageInput``, and the fallback matches
*everything*. Below it, every such window silently receives "unknown command"
instead of what the person typed.
"""

LAST_ROUTERS: Final[Iterable[Router]] = (fallback_router, errors_router)
"""What has to come after everything else.

``fallback_router`` matches any message, so anything below it would never run;
``errors_router`` observes failures rather than messages, and sits last to say
so.
"""


def setup_all_handlers(dp: Dispatcher) -> None:
    """Attaches every router, in the order aiogram will try them.

    One function rather than one per kind, because the ordering constraint runs
    *across* the kinds: dialogs sit between the feature routers and the
    catch-all, and splitting the attachment in two is how they ended up on the
    wrong side of it.
    """
    for router in (*FEATURE_ROUTERS, *DIALOGS, *LAST_ROUTERS):
        dp.include_router(router)
