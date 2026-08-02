"""The ``User`` aggregate against a real database, through its port.

The mapping is imperative and composite: preferences are three columns
assembled positionally, the name is two more, and the accounts are a separate
table loaded eagerly because the linking rules are checked against all of them.
None of that fails loudly when it is wrong — a composite assembled in the wrong
order round-trips as a user whose locale is their notification target — so it is
checked end to end here.
"""

from typing import Final

import pytest
from dishka import AsyncContainer, FromDishka, Scope

from goldy.application.common.ports.transaction_manager import TransactionManager
from goldy.application.common.ports.users import UserCommandGateway
from goldy.application.error import UserAlreadyExistsError
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.block_reason import BlockReason
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.full_name import FullName
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus
from tests.integration.arrange import UserSeeder
from tests.integration.inject import inject
from tests.unit.factories.domain_factories import (
    CUSTOMER_PHONE,
    MANAGER_PHONE,
    MAX_ACCOUNT_ID,
    TELEGRAM_ACCOUNT_ID,
    make_account,
    make_registered_user,
    make_user_id,
)

CLASHING_USER_ID: Final[str] = "44444444-4444-4444-4444-444444444444"

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]


@inject
async def test_a_registered_person_reads_back_whole(
    seed_user: UserSeeder,
    gateway: FromDishka[UserCommandGateway],
) -> None:
    seeded = await seed_user()

    loaded = await gateway.by_id(seeded.id)

    assert loaded is not None
    assert loaded.phone_number == PhoneNumber(value=CUSTOMER_PHONE)
    assert loaded.full_name == FullName(first_name="Данил", last_name="Ковалев")
    assert loaded.role is UserRole.CUSTOMER
    assert loaded.status is UserStatus.ACTIVE


@inject
async def test_preferences_survive_the_composite(
    seed_user: UserSeeder,
    gateway: FromDishka[UserCommandGateway],
) -> None:
    """Three columns assembled positionally, and silent when they are swapped."""
    seeded = await seed_user()

    loaded = await gateway.by_id(seeded.id)

    assert loaded is not None
    assert loaded.preferences.notify_via is MessengerPlatform.TELEGRAM
    assert loaded.preferences.locale.value == "ru"
    assert loaded.preferences.marketing_consent is False


@inject
async def test_the_accounts_come_back_with_the_person(
    seed_user: UserSeeder,
    gateway: FromDishka[UserCommandGateway],
) -> None:
    """A partially loaded user would pass a linking check it should have failed."""
    seeded = await seed_user()

    loaded = await gateway.by_id(seeded.id)

    assert loaded is not None
    assert len(loaded.accounts) == 1
    assert loaded.accounts[0].platform is MessengerPlatform.TELEGRAM
    assert loaded.accounts[0].external_id == ExternalAccountId(
        value=TELEGRAM_ACCOUNT_ID,
    )


@inject
async def test_a_person_is_found_by_their_number(
    seed_user: UserSeeder,
    gateway: FromDishka[UserCommandGateway],
) -> None:
    """The number is the identity — this is the lookup that links a second platform."""
    seeded = await seed_user()

    loaded = await gateway.by_phone_number(PhoneNumber(value=CUSTOMER_PHONE))

    assert loaded is not None
    assert loaded.id == seeded.id


@inject
async def test_a_person_is_found_by_the_account_they_wrote_from(
    seed_user: UserSeeder,
    gateway: FromDishka[UserCommandGateway],
) -> None:
    """The lookup behind every single update — the join is worth checking once."""
    seeded = await seed_user()

    loaded = await gateway.by_messenger_account(
        MessengerPlatform.TELEGRAM,
        ExternalAccountId(value=TELEGRAM_ACCOUNT_ID),
    )

    assert loaded is not None
    assert loaded.id == seeded.id


@inject
async def test_an_account_id_from_another_platform_matches_nobody(
    seed_user: UserSeeder,
    gateway: FromDishka[UserCommandGateway],
) -> None:
    """External ids are unique only within their platform, never across them."""
    await seed_user()

    loaded = await gateway.by_messenger_account(
        MessengerPlatform.MAX,
        ExternalAccountId(value=TELEGRAM_ACCOUNT_ID),
    )

    assert loaded is None


async def test_a_second_registration_of_one_number_is_refused(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """The unique index is what stops one person becoming two.

    Refused as ``UserAlreadyExistsError`` rather than as a generic repository
    failure, because the caller has to be able to tell "somebody registered a
    millisecond ago", which is retryable, from a broken database, which is not.
    """
    await seed_user()

    async with worker_container(scope=Scope.REQUEST) as scope:
        gateway = await scope.get(UserCommandGateway)

        with pytest.raises(UserAlreadyExistsError):
            await gateway.add(_a_clashing_registration(CUSTOMER_PHONE, "777777"))


async def test_a_second_registration_of_one_account_is_refused(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """Two people sharing a Telegram account would each be the other's login."""
    await seed_user()

    async with worker_container(scope=Scope.REQUEST) as scope:
        gateway = await scope.get(UserCommandGateway)
        clash = _a_clashing_registration(MANAGER_PHONE, TELEGRAM_ACCOUNT_ID)

        with pytest.raises(UserAlreadyExistsError):
            await gateway.add(clash)


async def test_a_loaded_person_can_be_changed_and_saved(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """A loaded aggregate needs its events collection injected, or this raises.

    SQLAlchemy leaves the attribute unset on a loaded instance because it is not
    a column, so the first method that records an event would fail — long after
    the load that actually caused it.
    """
    seeded = await seed_user()

    async with worker_container(scope=Scope.REQUEST) as writer:
        loaded = await (await writer.get(UserCommandGateway)).by_id(seeded.id)
        assert loaded is not None
        loaded.block(BlockReason(value="Оскорблял поддержку"))
        await (await writer.get(TransactionManager)).commit()

    async with worker_container(scope=Scope.REQUEST) as reader:
        reloaded = await (await reader.get(UserCommandGateway)).by_id(seeded.id)

    assert reloaded is not None
    assert reloaded.status is UserStatus.BLOCKED
    assert reloaded.block_reason == BlockReason(value="Оскорблял поддержку")


async def test_a_linked_second_platform_is_persisted(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """Linking writes a child row, and the child table is where mappings go wrong."""
    seeded = await seed_user()

    async with worker_container(scope=Scope.REQUEST) as writer:
        loaded = await (await writer.get(UserCommandGateway)).by_id(seeded.id)
        assert loaded is not None
        loaded.link_account(make_account(MessengerPlatform.MAX, MAX_ACCOUNT_ID))
        await (await writer.get(TransactionManager)).commit()

    async with worker_container(scope=Scope.REQUEST) as reader:
        found = await (await reader.get(UserCommandGateway)).by_messenger_account(
            MessengerPlatform.MAX,
            ExternalAccountId(value=MAX_ACCOUNT_ID),
        )

    assert found is not None
    assert found.id == seeded.id
    assert len(found.accounts) == 2


def _a_clashing_registration(phone_number: str, external_id: str) -> User:
    """Somebody new, built to collide with whoever is already stored.

    Not through ``seed_user``: that one commits, and this one is meant to be
    rejected at flush. Its id is fixed and unlike any the generator produces, so
    the collision that happens is the one the test named.
    """
    user, _ = make_registered_user(
        user_id=make_user_id(CLASHING_USER_ID),
        phone_number=phone_number,
        account=make_account(external_id=external_id),
    )
    return user
