from typing import Final

from dishka import Provider, Scope

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

    registry.add_request_handler(GetCurrentUserQuery, GetCurrentUserHandler)
    registry.add_request_handler(GetUserByIdQuery, GetUserByIdHandler)
    registry.add_request_handler(ListUsersQuery, ListUsersHandler)

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
