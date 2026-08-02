import pytest

from goldy.application.commands.users.register_user.handler import RegisterUserHandler
from goldy.application.commands.users.seed_admins.command import SeedAdminsCommand
from goldy.application.commands.users.seed_admins.handler import SeedAdminsHandler
from goldy.application.common.ports.mappers import UserViewMapper
from goldy.domain.users.factories.user_factory import UserFactory
from goldy.domain.users.values.user_role import UserRole
from tests.unit.application.conftest import UserSeeder
from tests.unit.factories.command_factories import (
    DEFAULT_PHONE,
    make_register_user_command,
)
from tests.unit.stubs.admin import StubAdminRegistry
from tests.unit.stubs.gateways import InMemoryUserCommandGateway

OTHER_PHONE: str = "+79995554433"


@pytest.fixture()
def admin_registry() -> StubAdminRegistry:
    """Overrides the empty default: these tests are about the list being used."""
    return StubAdminRegistry(DEFAULT_PHONE)


async def test_a_configured_number_is_promoted_on_startup(
    seed_user: UserSeeder,
    seed_admins_handler: SeedAdminsHandler,
) -> None:
    user = await seed_user(phone_number=DEFAULT_PHONE, external_id="111")

    response = await seed_admins_handler.handle(SeedAdminsCommand())

    assert user.role is UserRole.ADMIN
    assert response.granted == 1


async def test_seeding_twice_grants_nothing_the_second_time(
    seed_user: UserSeeder,
    seed_admins_handler: SeedAdminsHandler,
) -> None:
    """Startup runs on every deploy; it must not churn the audit trail."""
    await seed_user(phone_number=DEFAULT_PHONE, external_id="111")
    await seed_admins_handler.handle(SeedAdminsCommand())

    response = await seed_admins_handler.handle(SeedAdminsCommand())

    assert response.granted == 0
    assert response.already == 1


async def test_a_number_nobody_registered_is_reported_as_pending(
    seed_admins_handler: SeedAdminsHandler,
) -> None:
    """Normal on a fresh deployment, worth noticing if it stays that way."""
    response = await seed_admins_handler.handle(SeedAdminsCommand())

    assert response.granted == 0
    assert response.pending == 1


async def test_someone_not_on_the_list_stays_a_customer(
    seed_user: UserSeeder,
    seed_admins_handler: SeedAdminsHandler,
) -> None:
    other = await seed_user(phone_number=OTHER_PHONE, external_id="222")

    await seed_admins_handler.handle(SeedAdminsCommand())

    assert other.role is UserRole.CUSTOMER


async def test_a_configured_number_registering_later_is_promoted_at_once(
    register_user_handler: RegisterUserHandler,
) -> None:
    """Otherwise the administrator waits for a restart, which reads as a bug."""
    view = await register_user_handler.handle(make_register_user_command())

    assert view.role == UserRole.ADMIN.value


async def test_an_ordinary_registration_is_untouched(
    user_gateway: InMemoryUserCommandGateway,
    user_factory: UserFactory,
    user_view_mapper: UserViewMapper,
) -> None:
    handler = RegisterUserHandler(
        user_gateway,
        user_factory,
        user_view_mapper,
        StubAdminRegistry(),
    )

    view = await handler.handle(make_register_user_command())

    assert view.role == UserRole.CUSTOMER.value
