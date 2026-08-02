"""What the entry points do before they serve anything.

Both processes build a container and one of them seeds administrators. Neither
is covered by the tests above, because both happen once at startup — and a
startup that fails takes everything with it, so it is worth its own file.
"""

import pytest
from dishka import AsyncContainer, Scope
from dishka.exceptions import NoFactoryError

from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.outbox import OutboxPublisher
from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.query_params.user_filters import UserFilters
from goldy.domain.users.values.user_role import UserRole
from goldy.setup.bootstrap.setups.admin_setup import seed_admins
from tests.integration.arrange import UserSeeder
from tests.unit.factories.domain_factories import ADMIN_PHONE, CUSTOMER_PHONE

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
]


@pytest.mark.usefixtures("clean_tables")
async def test_seeding_promotes_a_configured_number_that_has_registered(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """The only way the first administrator can exist.

    ``ADMIN`` sits above every role, so no command in the bot may grant it —
    which leaves configuration as the only route in.
    """
    await seed_user(phone_number=ADMIN_PHONE, external_id="700001")

    await seed_admins(worker_container)

    async with worker_container(scope=Scope.REQUEST) as scope:
        gateway = await scope.get(UserQueryGateway)
        [view] = await gateway.read_all(
            Pagination(),
            SortingOrder.ASC,
            UserFilters(role=UserRole.ADMIN),
        )

    assert view.phone_number == ADMIN_PHONE


@pytest.mark.usefixtures("clean_tables")
async def test_seeding_leaves_everybody_else_alone(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    await seed_user(phone_number=CUSTOMER_PHONE, external_id="700002")

    await seed_admins(worker_container)

    async with worker_container(scope=Scope.REQUEST) as scope:
        gateway = await scope.get(UserQueryGateway)
        admins = await gateway.total(UserFilters(role=UserRole.ADMIN))

    assert admins == 0


@pytest.mark.usefixtures("clean_tables")
async def test_seeding_an_empty_database_is_not_an_error(
    worker_container: AsyncContainer,
) -> None:
    """Normal on a fresh deployment: the administrator has not written yet."""
    await seed_admins(worker_container)


@pytest.mark.usefixtures("clean_tables")
async def test_seeding_twice_grants_nothing_the_second_time(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """Every restart runs it, so it has to be idempotent or the log lies."""
    await seed_user(phone_number=ADMIN_PHONE, external_id="700003")

    await seed_admins(worker_container)
    await seed_admins(worker_container)

    async with worker_container(scope=Scope.REQUEST) as scope:
        gateway = await scope.get(UserQueryGateway)
        admins = await gateway.total(UserFilters(role=UserRole.ADMIN))

    assert admins == 1


async def test_the_worker_cannot_resolve_an_identity(
    worker_container: AsyncContainer,
) -> None:
    """A background task is nobody's request.

    The containers are assembled separately so that a handler needing an
    identity cannot be built in the worker at all — the failure belongs at
    startup, not halfway through a task.
    """
    async with worker_container(scope=Scope.REQUEST) as scope:
        with pytest.raises(NoFactoryError):
            await scope.get(IdentityProvider)


async def test_the_bot_cannot_reach_the_broker(
    telegram_container: AsyncContainer,
) -> None:
    """The bot writes events to the outbox and never publishes them itself.

    That is the outbox pattern: the process making the state change does not
    talk to RabbitMQ, so an event cannot be published for a transaction that
    then rolled back.
    """
    async with telegram_container(scope=Scope.REQUEST) as scope:
        with pytest.raises(NoFactoryError):
            await scope.get(OutboxPublisher)
