from collections.abc import Iterable
from typing import Final

from aiogram import Dispatcher, Router
from aiogram_dialog import Dialog

from goldy.presentation.telegram.handlers.admin import (
    ADMIN_DIALOG,
    router as admin_router,
)
from goldy.presentation.telegram.handlers.cart import (
    CART_DIALOG,
    router as cart_router,
)
from goldy.presentation.telegram.handlers.catalog import (
    CATALOG_DIALOG,
    router as catalog_router,
)
from goldy.presentation.telegram.handlers.checkout import CHECKOUT_DIALOG
from goldy.presentation.telegram.handlers.common.fallback import (
    router as fallback_router,
)
from goldy.presentation.telegram.handlers.common.help import router as help_router
from goldy.presentation.telegram.handlers.errors import router as errors_router
from goldy.presentation.telegram.handlers.manage_orders import (
    MANAGE_ORDERS_DIALOG,
    router as manage_orders_router,
)
from goldy.presentation.telegram.handlers.orders import (
    ORDERS_DIALOG,
    router as orders_router,
)
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
    catalog_router,
    cart_router,
    orders_router,
    manage_orders_router,
)
"""The routers that claim an update because they recognise it.

The order *within* this tuple does not matter — no two of these claim the same
command — but the order of the tuple as a whole does, and it is the reason the
storefront works at all. Three catalog windows carry a ``MessageInput`` that
treats any typed text as a search term, and a dialog attached above these
routers would swallow ``/cart`` as a search for the word "/cart". A command is
most wanted exactly when somebody is in the middle of something else, so these
sit first and the dialogs come after.

``manage_orders_router`` carries its own ``IsStaffFilter``; nothing here adds
one, and nothing here should. A customer who types the command falls through to
the fallback and is told it is unknown, rather than being refused — a refusal
would confirm the command exists.
"""

DIALOGS: Final[Iterable[Dialog]] = (
    PROFILE_DIALOG,
    ADMIN_DIALOG,
    CATALOG_DIALOG,
    CART_DIALOG,
    CHECKOUT_DIALOG,
    ORDERS_DIALOG,
    MANAGE_ORDERS_DIALOG,
)
"""Dialogs, which are routers too — aiogram-dialog builds them as such.

They must be attached before ``fallback_router``, and that is not a style
preference. A window waiting on typed input — a new name, a reason for a block
— matches through the dialog's own ``MessageInput``, and the fallback matches
*everything*. Below it, every such window silently receives "unknown command"
instead of what the person typed.

Their order relative to each other is free: aiogram-dialog routes an update to
the dialog that owns the state group the person is standing in, not to the
first one that was attached. ``CHECKOUT_DIALOG`` has no router of its own and
appears only here, because it is reached by a button on the cart rather than by
a command.
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
