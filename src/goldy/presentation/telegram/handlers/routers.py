from typing import Final

from aiogram import Dispatcher, Router

from goldy.presentation.telegram.handlers import errors
from goldy.presentation.telegram.handlers.start import handler as start

ROUTERS: Final[tuple[Router, ...]] = (
    start.router,
    # Last on purpose: an error router included earlier would still work, but
    # keeping it at the end says plainly that it is the fallback and not a
    # participant in normal routing.
    errors.router,
)


def setup_all_handlers(dp: Dispatcher) -> None:
    """Attaches every router to the dispatcher, in matching order."""
    for router in ROUTERS:
        dp.include_router(router)


def setup_all_dialogs(dp: Dispatcher) -> None:
    """Attaches every aiogram-dialog window.

    Empty until the profile and admin screens land — those are the ones with
    state worth a dialog. Commands without state stay ordinary handlers.
    """
