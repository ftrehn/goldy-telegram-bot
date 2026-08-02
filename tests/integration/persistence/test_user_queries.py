"""The read side behind the admin list, against a real database.

Everything here is SQL that no stub can stand in for: an ``ilike`` over a column
whose type decorator expects a ``PhoneNumber``, a count that has to agree with a
page, and a second query that pulls the accounts back in one ``IN`` and regroups
them. Each of those is silently wrong in a way that only Postgres reveals.
"""

from uuid import uuid4

import pytest
from dishka import FromDishka

from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.query_params.user_filters import UserFilters
from goldy.domain.users.values.user_id import UserId
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus
from tests.integration.arrange import UserBlocker, UserSeeder
from tests.integration.inject import inject
from tests.unit.factories.domain_factories import CUSTOMER_PHONE

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

EVERYONE = UserFilters()
UNPAGED = Pagination()


async def seed_three(seed_user: UserSeeder) -> None:
    """Three people, each with their own number and Telegram account."""
    for index in range(3):
        await seed_user(
            phone_number=f"+7999000000{index}",
            external_id=f"90000{index}",
        )


@inject
async def test_a_stored_person_reads_back_as_a_view(
    seed_user: UserSeeder,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    """Primitives, not value objects — presentation must not see domain internals."""
    seeded = await seed_user()

    view = await gateway.read_by_id(seeded.id)

    assert view is not None
    assert view.phone_number == CUSTOMER_PHONE
    assert view.first_name == "Данил"
    assert view.role == UserRole.CUSTOMER.value
    assert view.is_blocked is False


@inject
async def test_a_view_carries_the_accounts(
    seed_user: UserSeeder,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    """They arrive from a second query and are regrouped by user id in Python."""
    seeded = await seed_user()

    view = await gateway.read_by_id(seeded.id)

    assert view is not None
    assert [account.platform for account in view.accounts] == ["telegram"]


@inject
async def test_an_unknown_id_reads_back_as_nothing(
    gateway: FromDishka[UserQueryGateway],
) -> None:
    """Nothing rather than an error: the admin screens treat it as "not found"."""
    assert await gateway.read_by_id(UserId(uuid4())) is None


@inject
async def test_a_page_is_capped_by_its_limit(
    seed_user: UserSeeder,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    await seed_three(seed_user)

    page = await gateway.read_all(Pagination(limit=2), SortingOrder.ASC, EVERYONE)

    assert len(page) == 2


@inject
async def test_pages_do_not_overlap_and_cover_everyone(
    seed_user: UserSeeder,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    """The property the admin pager depends on, and the one an off-by-one breaks."""
    await seed_three(seed_user)

    first = await gateway.read_all(
        Pagination(limit=2, offset=0),
        SortingOrder.ASC,
        EVERYONE,
    )
    second = await gateway.read_all(
        Pagination(limit=2, offset=2),
        SortingOrder.ASC,
        EVERYONE,
    )

    seen = {view.id for view in first} | {view.id for view in second}
    assert not {view.id for view in first} & {view.id for view in second}
    assert len(seen) == 3


@inject
async def test_the_total_ignores_pagination(
    seed_user: UserSeeder,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    """It is what the pager divides by — counting a page would give one page."""
    await seed_three(seed_user)

    assert await gateway.total(EVERYONE) == 3


@inject
async def test_the_role_filter_narrows_both_the_page_and_the_count(
    seed_user: UserSeeder,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    """A filter applied to one and not the other paginates over a phantom total."""
    await seed_three(seed_user)
    await seed_user(
        phone_number="+79991111111",
        external_id="911111",
        role=UserRole.MANAGER,
    )

    managers = UserFilters(role=UserRole.MANAGER)
    page = await gateway.read_all(UNPAGED, SortingOrder.ASC, managers)

    assert [view.role for view in page] == [UserRole.MANAGER.value]
    assert await gateway.total(managers) == 1


@inject
async def test_the_status_filter_finds_the_blocked(
    seed_user: UserSeeder,
    block_user: UserBlocker,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    await seed_three(seed_user)
    troublemaker = await seed_user(phone_number="+79992222222", external_id="922222")
    await block_user(troublemaker.id, "Оскорблял поддержку")

    blocked = UserFilters(status=UserStatus.BLOCKED)
    page = await gateway.read_all(UNPAGED, SortingOrder.ASC, blocked)

    assert [view.id for view in page] == [troublemaker.id]
    assert page[0].is_blocked is True


@inject
async def test_the_search_matches_a_phone_number(
    seed_user: UserSeeder,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    """The column carries a ``PhoneNumber``, so the search string has to be cast.

    Without the cast the type decorator is handed a fragment and either refuses
    it or turns it into something that matches nobody.
    """
    await seed_three(seed_user)
    await seed_user(phone_number="+79993333333", external_id="933333")

    found = await gateway.read_all(
        UNPAGED,
        SortingOrder.ASC,
        UserFilters(search="333333"),
    )

    assert [view.phone_number for view in found] == ["+79993333333"]


@inject
async def test_the_search_matches_a_name_case_insensitively(
    seed_user: UserSeeder,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    """Nobody types a name with the right capitalisation into an admin search."""
    await seed_user()

    found = await gateway.read_all(
        UNPAGED,
        SortingOrder.ASC,
        UserFilters(search="данил"),
    )

    assert len(found) == 1


@inject
async def test_a_search_matching_nobody_is_empty_rather_than_everybody(
    seed_user: UserSeeder,
    gateway: FromDishka[UserQueryGateway],
) -> None:
    """A filter that silently drops out shows the whole table to a typo."""
    await seed_three(seed_user)

    found = await gateway.read_all(
        UNPAGED,
        SortingOrder.ASC,
        UserFilters(search="никогонет"),
    )

    assert found == []
    assert await gateway.total(UserFilters(search="никогонет")) == 0
