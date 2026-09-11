from typing import Final

from dishka import Provider, Scope

from goldy.application.commands.carts.add_to_cart.command import AddToCartCommand
from goldy.application.commands.carts.add_to_cart.handler import AddToCartHandler
from goldy.application.commands.carts.clear_cart.command import ClearCartCommand
from goldy.application.commands.carts.clear_cart.handler import ClearCartHandler
from goldy.application.commands.carts.decrease_cart_line.command import (
    DecreaseCartLineCommand,
)
from goldy.application.commands.carts.decrease_cart_line.handler import (
    DecreaseCartLineHandler,
)
from goldy.application.commands.carts.remove_cart_line.command import (
    RemoveCartLineCommand,
)
from goldy.application.commands.carts.remove_cart_line.handler import (
    RemoveCartLineHandler,
)
from goldy.application.commands.carts.remove_unavailable_cart_lines.command import (
    RemoveUnavailableCartLinesCommand,
)
from goldy.application.commands.carts.remove_unavailable_cart_lines.handler import (
    RemoveUnavailableCartLinesHandler,
)
from goldy.application.commands.carts.set_cart_line_quantity.command import (
    SetCartLineQuantityCommand,
)
from goldy.application.commands.carts.set_cart_line_quantity.handler import (
    SetCartLineQuantityHandler,
)
from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.finalize_catalog_import.handler import (
    FinalizeCatalogImportHandler,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.commands.catalog.import_catalog.handler import (
    ImportCatalogHandler,
)
from goldy.application.commands.notifications.notify_order_address.command import (
    NotifyDeliveryAddressChangedCommand,
)
from goldy.application.commands.notifications.notify_order_address.handler import (
    NotifyDeliveryAddressChangedHandler,
)
from goldy.application.commands.notifications.notify_order_placed.command import (
    NotifyOrderPlacedCommand,
)
from goldy.application.commands.notifications.notify_order_placed.handler import (
    NotifyOrderPlacedHandler,
)
from goldy.application.commands.notifications.notify_order_status.command import (
    NotifyOrderStatusChangedCommand,
)
from goldy.application.commands.notifications.notify_order_status.handler import (
    NotifyOrderStatusChangedHandler,
)
from goldy.application.commands.orders.cancel_order.command import CancelOrderCommand
from goldy.application.commands.orders.cancel_order.handler import CancelOrderHandler
from goldy.application.commands.orders.change_delivery_address.command import (
    ChangeDeliveryAddressCommand,
)
from goldy.application.commands.orders.change_delivery_address.handler import (
    ChangeDeliveryAddressHandler,
)
from goldy.application.commands.orders.change_order_status.command import (
    ChangeOrderStatusCommand,
)
from goldy.application.commands.orders.change_order_status.handler import (
    ChangeOrderStatusHandler,
)
from goldy.application.commands.orders.place_order.command import PlaceOrderCommand
from goldy.application.commands.orders.place_order.handler import PlaceOrderHandler
from goldy.application.commands.outbox.relay_outbox.command import RelayOutboxCommand
from goldy.application.commands.outbox.relay_outbox.handler import RelayOutboxHandler
from goldy.application.commands.users.block_user.command import BlockUserCommand
from goldy.application.commands.users.block_user.handler import BlockUserHandler
from goldy.application.commands.users.change_notification_preferences.command import (
    ChangeNotificationPreferencesCommand,
)
from goldy.application.commands.users.change_notification_preferences.handler import (
    ChangeNotificationPreferencesHandler,
)
from goldy.application.commands.users.change_user_locale.command import (
    ChangeUserLocaleCommand,
)
from goldy.application.commands.users.change_user_locale.handler import (
    ChangeUserLocaleHandler,
)
from goldy.application.commands.users.change_user_role.command import (
    ChangeUserRoleCommand,
)
from goldy.application.commands.users.change_user_role.handler import (
    ChangeUserRoleHandler,
)
from goldy.application.commands.users.register_user.command import RegisterUserCommand
from goldy.application.commands.users.register_user.handler import RegisterUserHandler
from goldy.application.commands.users.rename_user.command import RenameUserCommand
from goldy.application.commands.users.rename_user.handler import RenameUserHandler
from goldy.application.commands.users.seed_admins.command import SeedAdminsCommand
from goldy.application.commands.users.seed_admins.handler import SeedAdminsHandler
from goldy.application.commands.users.unblock_user.command import UnblockUserCommand
from goldy.application.commands.users.unblock_user.handler import UnblockUserHandler
from goldy.application.commands.users.unlink_messenger_account.command import (
    UnlinkMessengerAccountCommand,
)
from goldy.application.commands.users.unlink_messenger_account.handler import (
    UnlinkMessengerAccountHandler,
)
from goldy.application.common.mediator.markers import Command
from goldy.application.common.mediator.sender import Sender
from goldy.application.pipelines.events_pipeline import EventsPipeline
from goldy.application.pipelines.transaction_pipeline import TransactionPipeline
from goldy.application.queries.carts.get_cart.handler import GetCartHandler
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.application.queries.catalog.get_product.handler import GetProductHandler
from goldy.application.queries.catalog.get_product.query import GetProductQuery
from goldy.application.queries.catalog.list_categories.handler import (
    ListCategoriesHandler,
)
from goldy.application.queries.catalog.list_categories.query import ListCategoriesQuery
from goldy.application.queries.catalog.list_products.handler import ListProductsHandler
from goldy.application.queries.catalog.list_products.query import ListProductsQuery
from goldy.application.queries.catalog.search_products.handler import (
    SearchProductsHandler,
)
from goldy.application.queries.catalog.search_products.query import SearchProductsQuery
from goldy.application.queries.orders.get_last_delivery_address.handler import (
    GetLastDeliveryAddressHandler,
)
from goldy.application.queries.orders.get_last_delivery_address.query import (
    GetLastDeliveryAddressQuery,
)
from goldy.application.queries.orders.get_order.handler import GetOrderHandler
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.application.queries.orders.list_my_orders.handler import ListMyOrdersHandler
from goldy.application.queries.orders.list_my_orders.query import ListMyOrdersQuery
from goldy.application.queries.orders.list_orders.handler import ListOrdersHandler
from goldy.application.queries.orders.list_orders.query import ListOrdersQuery
from goldy.application.queries.users.get_current_user.handler import (
    GetCurrentUserHandler,
)
from goldy.application.queries.users.get_current_user.query import GetCurrentUserQuery
from goldy.application.queries.users.get_user_by_id.handler import GetUserByIdHandler
from goldy.application.queries.users.get_user_by_id.query import GetUserByIdQuery
from goldy.application.queries.users.list_users.handler import ListUsersHandler
from goldy.application.queries.users.list_users.query import ListUsersQuery
from goldy.infrastructure.mediator.chain import ChainImpl
from goldy.infrastructure.mediator.interfaces import Chain, Resolver
from goldy.infrastructure.mediator.mediator import MediatorImpl
from goldy.infrastructure.mediator.registry import Registry
from goldy.infrastructure.mediator.resolvers.dishka import DishkaResolver


def make_registry() -> Registry:
    """Binds every request to its handler, and every command to its pipelines.

    Pipelines are registered against the ``Command`` marker rather than one
    command at a time. That is the whole point: a command added later is covered
    automatically, and cannot quietly run outside a transaction because somebody
    forgot a line here.

    Queries get no transaction — they mutate nothing, so opening one would only
    hold a connection for the length of a report.

    The order below is the order of execution: the transaction opens first and
    commits last, with the events drained inside it. Reversed, events would be
    written to the outbox after the commit and would stop being atomic with the
    state change they describe.
    """
    registry: Final[Registry] = Registry()

    registry.add_pipeline_handlers(Command, TransactionPipeline, EventsPipeline)

    registry.add_request_handler(RegisterUserCommand, RegisterUserHandler)
    registry.add_request_handler(RenameUserCommand, RenameUserHandler)
    registry.add_request_handler(
        ChangeNotificationPreferencesCommand,
        ChangeNotificationPreferencesHandler,
    )
    registry.add_request_handler(ChangeUserLocaleCommand, ChangeUserLocaleHandler)
    registry.add_request_handler(
        UnlinkMessengerAccountCommand,
        UnlinkMessengerAccountHandler,
    )
    registry.add_request_handler(BlockUserCommand, BlockUserHandler)
    registry.add_request_handler(UnblockUserCommand, UnblockUserHandler)
    registry.add_request_handler(ChangeUserRoleCommand, ChangeUserRoleHandler)
    registry.add_request_handler(SeedAdminsCommand, SeedAdminsHandler)
    registry.add_request_handler(RelayOutboxCommand, RelayOutboxHandler)

    registry.add_request_handler(NotifyOrderPlacedCommand, NotifyOrderPlacedHandler)
    registry.add_request_handler(
        NotifyOrderStatusChangedCommand,
        NotifyOrderStatusChangedHandler,
    )
    registry.add_request_handler(
        NotifyDeliveryAddressChangedCommand,
        NotifyDeliveryAddressChangedHandler,
    )

    registry.add_request_handler(ImportCatalogCommand, ImportCatalogHandler)
    registry.add_request_handler(
        FinalizeCatalogImportCommand,
        FinalizeCatalogImportHandler,
    )

    registry.add_request_handler(AddToCartCommand, AddToCartHandler)
    registry.add_request_handler(DecreaseCartLineCommand, DecreaseCartLineHandler)
    registry.add_request_handler(SetCartLineQuantityCommand, SetCartLineQuantityHandler)
    registry.add_request_handler(RemoveCartLineCommand, RemoveCartLineHandler)
    registry.add_request_handler(
        RemoveUnavailableCartLinesCommand,
        RemoveUnavailableCartLinesHandler,
    )
    registry.add_request_handler(ClearCartCommand, ClearCartHandler)

    registry.add_request_handler(PlaceOrderCommand, PlaceOrderHandler)
    registry.add_request_handler(CancelOrderCommand, CancelOrderHandler)
    registry.add_request_handler(ChangeOrderStatusCommand, ChangeOrderStatusHandler)
    registry.add_request_handler(
        ChangeDeliveryAddressCommand,
        ChangeDeliveryAddressHandler,
    )

    registry.add_request_handler(GetCurrentUserQuery, GetCurrentUserHandler)
    registry.add_request_handler(GetUserByIdQuery, GetUserByIdHandler)
    registry.add_request_handler(ListUsersQuery, ListUsersHandler)

    registry.add_request_handler(ListCategoriesQuery, ListCategoriesHandler)
    registry.add_request_handler(ListProductsQuery, ListProductsHandler)
    registry.add_request_handler(GetProductQuery, GetProductHandler)
    registry.add_request_handler(SearchProductsQuery, SearchProductsHandler)

    registry.add_request_handler(GetCartQuery, GetCartHandler)

    registry.add_request_handler(ListMyOrdersQuery, ListMyOrdersHandler)
    registry.add_request_handler(GetOrderQuery, GetOrderHandler)
    registry.add_request_handler(ListOrdersQuery, ListOrdersHandler)
    registry.add_request_handler(
        GetLastDeliveryAddressQuery,
        GetLastDeliveryAddressHandler,
    )

    return registry


def mediator_provider() -> Provider:
    """The registry is process-wide; resolver and mediator are per request.

    The resolver wraps the *request-scoped* container, which is what makes every
    handler and pipeline it builds share that request's session and events
    collection.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(make_registry, provides=Registry, scope=Scope.APP)
    provider.provide(source=ChainImpl, provides=Chain, scope=Scope.APP)
    provider.provide(source=DishkaResolver, provides=Resolver)
    provider.provide(source=MediatorImpl, provides=Sender)
    return provider
