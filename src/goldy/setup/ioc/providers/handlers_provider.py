"""Handler providers, grouped by what a handler needs rather than who calls it.

Everything past the bootstrap group wants to know who is acting, and a process
with no concept of "who" — a taskiq worker — must not be able to build it.
dishka validates the whole graph when a container is made, so the split turns
"this handler cannot run here" into a refusal at startup instead of a failure
halfway through a background task.
"""

from typing import Final

from dishka import Provider, Scope

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
from goldy.application.queries.users.get_current_user.handler import (
    GetCurrentUserHandler,
)
from goldy.application.queries.users.get_user_by_id.handler import GetUserByIdHandler
from goldy.application.queries.users.list_users.handler import ListUsersHandler


def bootstrap_handlers_provider() -> Provider:
    """Handlers any process can run, because nobody is issuing them.

    Seeding administrators happens at startup on the authority of the
    configuration, not of a person, so it needs no identity.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(source=SeedAdminsHandler)
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


def outbox_handlers_provider() -> Provider:
    """Handlers only the worker can run.

    ``RelayOutboxHandler`` needs an ``OutboxPublisher``, and that needs a broker
    connection the bot process does not open.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(source=RelayOutboxHandler)
    return provider
