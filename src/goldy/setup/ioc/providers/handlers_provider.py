"""Handler providers, grouped by what a handler needs rather than who calls it.

Everything past the bootstrap group wants to know who is acting, and a process
with no concept of "who" — a taskiq worker — must not be able to build it.
dishka validates the whole graph when a container is made, so the split turns
"this handler cannot run here" into a refusal at startup instead of a failure
halfway through a background task.
"""

from typing import Final

from dishka import Provider, Scope

from goldy.application.commands.carts.add_to_cart.handler import AddToCartHandler
from goldy.application.commands.carts.clear_cart.handler import ClearCartHandler
from goldy.application.commands.carts.decrease_cart_line.handler import (
    DecreaseCartLineHandler,
)
from goldy.application.commands.carts.remove_cart_line.handler import (
    RemoveCartLineHandler,
)
from goldy.application.commands.carts.remove_unavailable_cart_lines.handler import (
    RemoveUnavailableCartLinesHandler,
)
from goldy.application.commands.carts.repeat_order.handler import RepeatOrderHandler
from goldy.application.commands.carts.set_cart_line_quantity.handler import (
    SetCartLineQuantityHandler,
)
from goldy.application.commands.catalog.finalize_catalog_import.handler import (
    FinalizeCatalogImportHandler,
)
from goldy.application.commands.catalog.import_catalog.handler import (
    ImportCatalogHandler,
)
from goldy.application.commands.notifications.notify_order_address.handler import (
    NotifyDeliveryAddressChangedHandler,
)
from goldy.application.commands.notifications.notify_order_placed.handler import (
    NotifyOrderPlacedHandler,
)
from goldy.application.commands.notifications.notify_order_status.handler import (
    NotifyOrderStatusChangedHandler,
)
from goldy.application.commands.orders.cancel_order.handler import CancelOrderHandler
from goldy.application.commands.orders.change_delivery_address.handler import (
    ChangeDeliveryAddressHandler,
)
from goldy.application.commands.orders.change_order_status.handler import (
    ChangeOrderStatusHandler,
)
from goldy.application.commands.orders.place_order.handler import PlaceOrderHandler
from goldy.application.commands.outbox.relay_outbox.handler import RelayOutboxHandler
from goldy.application.commands.users.block_user.handler import BlockUserHandler
from goldy.application.commands.users.change_notification_preferences.handler import (
    ChangeNotificationPreferencesHandler,
)
from goldy.application.commands.users.change_user_locale.handler import (
    ChangeUserLocaleHandler,
)
from goldy.application.commands.users.change_user_role.handler import (
    ChangeUserRoleHandler,
)
from goldy.application.commands.users.register_user.handler import RegisterUserHandler
from goldy.application.commands.users.rename_user.handler import RenameUserHandler
from goldy.application.commands.users.seed_admins.handler import SeedAdminsHandler
from goldy.application.commands.users.unblock_user.handler import UnblockUserHandler
from goldy.application.commands.users.unlink_messenger_account.handler import (
    UnlinkMessengerAccountHandler,
)
from goldy.application.queries.carts.get_cart.handler import GetCartHandler
from goldy.application.queries.catalog.get_product.handler import GetProductHandler
from goldy.application.queries.catalog.list_categories.handler import (
    ListCategoriesHandler,
)
from goldy.application.queries.catalog.list_products.handler import ListProductsHandler
from goldy.application.queries.catalog.search_products.handler import (
    SearchProductsHandler,
)
from goldy.application.queries.orders.get_last_delivery_address.handler import (
    GetLastDeliveryAddressHandler,
)
from goldy.application.queries.orders.get_order.handler import GetOrderHandler
from goldy.application.queries.orders.list_my_orders.handler import ListMyOrdersHandler
from goldy.application.queries.orders.list_orders.handler import ListOrdersHandler
from goldy.application.queries.users.get_current_user.handler import (
    GetCurrentUserHandler,
)
from goldy.application.queries.users.get_user_by_id.handler import GetUserByIdHandler
from goldy.application.queries.users.list_users.handler import ListUsersHandler


def bootstrap_handlers_provider() -> Provider:
    """Handlers any process can run, because nobody is issuing them.

    Seeding administrators happens at startup on the authority of the
    configuration, not of a person, so it needs no identity. Catalog import is
    here for the same reason and one more: the data arrives from 1C over a
    queue the worker serves and from a file the seeder reads, and neither of
    those processes has a customer to speak for.

    ``ImportCatalogHandler`` takes the snapshot as part of the command and not
    ``CatalogSource`` as a collaborator, which is what keeps this group
    resolvable everywhere. Make the port a dependency and every container
    inherits it, including the two where no source is bound.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(source=SeedAdminsHandler)
    provider.provide_all(
        ImportCatalogHandler,
        FinalizeCatalogImportHandler,
    )
    return provider


def user_handlers_provider() -> Provider:
    """Handlers serving a person, and therefore needing to know which one.

    Resolved per request because their collaborators are: the mediator asks for
    a fresh handler on each dispatch, so a longer-lived one would hold a session
    belonging to an update that has already finished.

    ``RegisterUserHandler`` needs no identity — the whole point is that there
    is not one yet — but it is only ever reached from a messenger, so it lives
    with the rest.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide_all(
        RegisterUserHandler,
        RenameUserHandler,
        ChangeNotificationPreferencesHandler,
        ChangeUserLocaleHandler,
        UnlinkMessengerAccountHandler,
        BlockUserHandler,
        UnblockUserHandler,
        ChangeUserRoleHandler,
        GetCurrentUserHandler,
        GetUserByIdHandler,
        ListUsersHandler,
    )
    return provider


def shop_handlers_provider() -> Provider:
    """Everything the storefront runs: catalog, cart and orders.

    One group rather than three, because the line that matters is not which
    part of the shop a handler belongs to but whether it can answer "who is
    buying". Every handler here reaches ``IdentityProvider`` sooner or later -
    the cart and order ones directly or through ``UserProvider``, the catalog
    ones through ``PriceTypeProvider``, because a price without a customer is
    not a price.

    ``ListCategoriesHandler`` is the one that genuinely needs nobody: a group
    has no price and there is no rule about who may see which. It stays here
    anyway. Splitting one query into a group of its own would buy a resolution
    in the worker that nothing in the worker wants, at the cost of a second
    place to look when a storefront handler fails to resolve.

    Import and finalization are deliberately *not* here: they act on the
    authority of a configured exchange, not of a person, and the catalog seeder
    has no identity to offer them.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide_all(
        AddToCartHandler,
        DecreaseCartLineHandler,
        SetCartLineQuantityHandler,
        RemoveCartLineHandler,
        RemoveUnavailableCartLinesHandler,
        ClearCartHandler,
        RepeatOrderHandler,
        PlaceOrderHandler,
        CancelOrderHandler,
        ChangeOrderStatusHandler,
        ChangeDeliveryAddressHandler,
        ListCategoriesHandler,
        ListProductsHandler,
        GetProductHandler,
        SearchProductsHandler,
        GetCartHandler,
        ListMyOrdersHandler,
        GetOrderHandler,
        ListOrdersHandler,
        GetLastDeliveryAddressHandler,
    )
    return provider


def outbox_handlers_provider() -> Provider:
    """Handlers only the worker can run.

    ``RelayOutboxHandler`` needs an ``OutboxPublisher``, and that needs a broker
    connection the bot process does not open.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(source=RelayOutboxHandler)
    return provider


def notification_handlers_provider() -> Provider:
    """Handlers only the worker can run, and for a stricter reason than the relay.

    Each of them needs an ``InboxGateway`` and a ``NotificationDispatcher``, and
    those lead to the Bot API client and the bot token — which
    ``configs_provider`` deliberately hands to nobody. A bot process that
    somehow reached one of these would be answering an update by writing to
    somebody else, which is not a thing any screen should be able to do.

    Separate from ``outbox_handlers_provider`` even though both are the
    worker's. The relay needs a broker; these need a messenger. Merging them
    would mean the first process that wanted to drain the outbox had to carry a
    bot token to build its container.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide_all(
        NotifyOrderPlacedHandler,
        NotifyOrderStatusChangedHandler,
        NotifyDeliveryAddressChangedHandler,
    )
    return provider
