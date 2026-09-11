"""The cart screen: quantities of ours, everything else joined from the catalog.

The cart stores no price at all, so the name, the unit, the stock figure and the
price are read from the projection on every render. That is what makes a new
price list reprice a standing cart instead of leaving numbers in it the shop no
longer offers — and it is only true of the SQL, so only a database can show it.

The join against the products is a ``LEFT JOIN`` taken **without** an
``is_active`` filter, and the test for that is the one worth reading twice. With
the filter, a product withdrawn between being added and being ordered would drop
off the screen and the total would quietly shrink; nobody notices what is not
there. The line has to come back marked instead.
"""

from decimal import Decimal

import pytest
from dishka import AsyncContainer, FromDishka, Scope

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.common.ports.carts import (
    CartCommandGateway,
    CartQueryGateway,
)
from goldy.application.common.ports.catalog import CatalogScopeKind, CatalogSnapshot
from goldy.application.common.ports.transaction_manager import TransactionManager
from goldy.application.common.views.cart import CartLineView
from goldy.application.common.views.money import MoneyView
from goldy.domain.common.values.currency import Currency
from goldy.domain.users.values.user_id import UserId
from tests.integration.arrange import CommandSender, UserSeeder
from tests.integration.inject import inject
from tests.unit.factories.catalog_factories import (
    BATCH_ID,
    make_price_row,
    make_price_type_row,
    make_product_row,
    make_scope,
    make_snapshot,
    make_stock_row,
)
from tests.unit.factories.shop_factories import (
    PRICE_TYPE_ID,
    make_price_type_id,
    make_product_id,
    make_quantity,
)

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

SECOND_BATCH_ID: str = "batch-0002"
FIRST_AMOUNT: str = "100.00"
SECOND_AMOUNT: str = "12.50"


@inject
async def test_a_cart_is_priced_from_the_catalog_on_every_render(
    seed_user: UserSeeder,
    send_worker_command: CommandSender,
    worker_container: AsyncContainer,
    carts: FromDishka[CartQueryGateway],
) -> None:
    """Different prices and different quantities, so a crossed line is visible."""
    seeded = await seed_user()
    await send_worker_command(ImportCatalogCommand(snapshot=_a_shop()))
    await _fill_cart(worker_container, seeded.id, {1: 2, 2: 4})

    view = await carts.read_for(seeded.id, make_price_type_id(PRICE_TYPE_ID))

    assert view is not None
    lines = _by_product(view.lines)
    assert lines[make_product_id(1).value].quantity == 2
    assert lines[make_product_id(1).value].line_total == _money("200.00")
    assert lines[make_product_id(2).value].quantity == 4
    assert lines[make_product_id(2).value].line_total == _money("50.00")
    assert view.total == _money("250.00")


@inject
async def test_a_withdrawn_product_stays_on_the_screen_and_is_marked(
    seed_user: UserSeeder,
    send_worker_command: CommandSender,
    worker_container: AsyncContainer,
    carts: FromDishka[CartQueryGateway],
) -> None:
    """The filter that looks natural and would hide the problem instead.

    A line that vanished would shrink the total with nothing to explain it.
    Marked, the screen can offer "remove unavailable" and keep "checkout"
    hidden until the customer has dealt with it.
    """
    seeded = await seed_user()
    await send_worker_command(ImportCatalogCommand(snapshot=_a_shop()))
    await _fill_cart(worker_container, seeded.id, {1: 2, 2: 4})

    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                batch_id=SECOND_BATCH_ID,
                products=(make_product_row(1),),
            ),
        ),
    )
    await send_worker_command(
        FinalizeCatalogImportCommand(
            batch_id=SECOND_BATCH_ID,
            scope=make_scope(CatalogScopeKind.PRODUCTS),
        ),
    )

    view = await carts.read_for(seeded.id, make_price_type_id(PRICE_TYPE_ID))

    assert view is not None
    assert view.line_count == 2
    lines = _by_product(view.lines)
    assert lines[make_product_id(1).value].is_available
    assert not lines[make_product_id(2).value].is_available
    assert view.has_unavailable_lines


@inject
async def test_a_product_this_price_list_does_not_price_keeps_its_line(
    seed_user: UserSeeder,
    send_worker_command: CommandSender,
    worker_container: AsyncContainer,
    carts: FromDishka[CartQueryGateway],
) -> None:
    """A line with no price says so, instead of printing a zero read as "free"."""
    seeded = await seed_user()
    await send_worker_command(ImportCatalogCommand(snapshot=_a_shop()))
    await _fill_cart(worker_container, seeded.id, {1: 2, 3: 1})

    view = await carts.read_for(seeded.id, make_price_type_id(PRICE_TYPE_ID))

    assert view is not None
    assert view.has_unpriced_lines
    assert _by_product(view.lines)[make_product_id(3).value].unit_price is None
    assert view.total == _money("200.00")


@inject
async def test_somebody_with_no_cart_row_is_not_an_error(
    seed_user: UserSeeder,
    carts: FromDishka[CartQueryGateway],
) -> None:
    """The ordinary state of a person who has just registered."""
    seeded = await seed_user()

    view = await carts.read_for(seeded.id, make_price_type_id(PRICE_TYPE_ID))

    assert view is None


def _a_shop() -> CatalogSnapshot:
    """Three products, one of which this price list prices at nothing at all."""
    return make_snapshot(
        batch_id=BATCH_ID,
        products=(make_product_row(1), make_product_row(2), make_product_row(3)),
        price_types=(make_price_type_row(),),
        prices=(
            make_price_row(1, amount=FIRST_AMOUNT),
            make_price_row(2, amount=SECOND_AMOUNT),
        ),
        stock=(make_stock_row(1, quantity="4"),),
    )


async def _fill_cart(
    container: AsyncContainer,
    user_id: UserId,
    items: dict[int, int],
) -> None:
    """Puts ``{product number: quantity}`` in this person's cart, committed."""
    async with container(scope=Scope.REQUEST) as scope:
        gateway: CartCommandGateway = await scope.get(CartCommandGateway)
        transaction: TransactionManager = await scope.get(TransactionManager)
        cart = await gateway.ensure_for(user_id)

        for index, quantity in items.items():
            cart.add_item(make_product_id(index), make_quantity(quantity))

        await transaction.commit()


def _by_product(lines: tuple[CartLineView, ...]) -> dict[str, CartLineView]:
    """The lines of a view, addressed by the product each one is about.

    Keyed rather than indexed: the screen orders by when a line was added, and
    two lines added inside one transaction are a tie this test has no business
    depending on.
    """
    return {line.product_id: line for line in lines}


def _money(amount: str) -> MoneyView:
    """The view's own money, built the way the gateway builds it."""
    return MoneyView(amount=Decimal(amount), currency=Currency.RUB.value)
