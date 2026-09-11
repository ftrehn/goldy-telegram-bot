"""The ``Order`` aggregate against a real database, through its port.

Three composites live on this aggregate — ``Recipient`` over three columns,
``UnitOfMeasure`` over two and ``Money`` over two — and SQLAlchemy rebuilds all
of them positionally. A column pair swapped in the mapping therefore swaps two
values with nothing raising: the order simply comes back with the recipient's
surname where their given name was, and nobody finds out until a delivery note
is printed.

Every value used below is distinguishable from its neighbours for that reason.
Two names that are both "Иван" and a unit whose reference and label are both
"шт" would round-trip through a broken mapping looking perfect.

Distinct values are not enough on their own, and that is the point of the three
tests that read raw columns. A composite is decomposed positionally on the way
in and rebuilt positionally on the way out, so a swapped pair is swapped twice
and a round trip through the port comes back correct — the mistake is invisible
to the aggregate and visible only in the table. Those tests bypass the port for
exactly that reason, and read SQL text rather than the mapped columns so that
no type decorator can quietly undo the swap on the way back.
"""

from decimal import Decimal

import pytest
from dishka import AsyncContainer, Scope
from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncEngine

from goldy.application.common.ports.orders import OrderCommandGateway
from goldy.application.common.ports.transaction_manager import TransactionManager
from goldy.domain.catalog.values.product_name import ProductName
from goldy.domain.common.values.currency import Currency
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.entities.order_line import OrderLine
from goldy.domain.orders.placement import Placement
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.cancellation_reason import CancellationReason
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.infrastructure.errors import RepoError
from tests.integration.arrange import UserSeeder
from tests.unit.factories.domain_factories import make_events_collection
from tests.unit.factories.shop_factories import (
    make_delivery_address,
    make_order_comment,
    make_order_id,
    make_order_number,
    make_price_type_id,
    make_priced_product,
    make_product_id,
    make_quantity,
    make_recipient,
    make_unit,
)

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

OTHER_ORDER_ID: str = "bbbbbbbb-2222-2222-2222-222222222222"
RECIPIENT_PHONE: str = "+79995550101"
"""Not the customer's own number, because a recipient need not be the buyer."""

ORDER_COMMENT: str = "Позвонить за час до доставки"
PRODUCT_NAME: str = "Уголок оцинкованный"


async def test_a_placed_order_reads_back_whole(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    seeded = await seed_user()

    await _store(worker_container, _an_order(seeded))

    loaded = await _load(worker_container, make_order_id())

    assert loaded is not None
    assert loaded.number == make_order_number()
    assert loaded.customer_id == seeded.id
    assert loaded.status is OrderStatus.NEW
    assert loaded.price_type_id == make_price_type_id()
    assert loaded.delivery_address == make_delivery_address()
    assert loaded.comment == make_order_comment(ORDER_COMMENT)


async def test_the_recipient_survives_its_three_columns(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """Given name, surname and phone, all three different and all three checked.

    The first two are plain text in adjacent columns, so swapping them in the
    mapping is silent — which is the only reason this assertion is spelled out
    field by field instead of comparing the whole value.
    """
    seeded = await seed_user()

    await _store(worker_container, _an_order(seeded))

    loaded = await _load(worker_container, make_order_id())

    assert loaded is not None
    assert loaded.recipient.first_name == "Пётр"
    assert loaded.recipient.last_name == "Одинцов"
    assert loaded.recipient.phone_number == PhoneNumber(value=RECIPIENT_PHONE)


async def test_a_recipient_without_a_surname_reads_back_without_one(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """One name is all Telegram gives for many people, and the column is nullable."""
    seeded = await seed_user()
    order = _an_order(seeded, recipient_last_name=None)

    await _store(worker_container, order)

    loaded = await _load(worker_container, make_order_id())

    assert loaded is not None
    assert loaded.recipient.first_name == "Пётр"
    assert loaded.recipient.last_name is None


async def test_the_line_snapshot_survives_its_composites(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """The unit's reference and label, and the price's amount and currency.

    ``UnitOfMeasure`` is the dangerous one: two adjacent text columns, and a
    unit called "1c-unit-778" would look like data rather than like a defect.
    """
    seeded = await seed_user()

    await _store(worker_container, _an_order(seeded))

    loaded = await _load(worker_container, make_order_id())

    assert loaded is not None
    [line] = loaded.lines
    assert line.position == 1
    assert line.product_id == make_product_id(4)
    assert line.name.value == PRODUCT_NAME
    assert line.unit.source_id == "1c-unit-778"
    assert line.unit.name == "упак"
    assert line.unit_price.amount == Decimal("12.34")
    assert line.unit_price.currency is Currency.RUB
    assert line.quantity == make_quantity(6)


async def test_the_recipient_is_written_to_the_columns_it_names(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """The only check that catches a swapped pair in the composite.

    A round trip cannot: the same order that writes the columns reads them, so
    two columns exchanged in the mapping are exchanged twice and the aggregate
    comes back looking right. What is wrong is the row, and the row is what a
    delivery note, a manager's screen and the future export to 1C read.
    """
    seeded = await seed_user()
    await _store(worker_container, _an_order(seeded))

    row = await _row_of(
        engine,
        "SELECT recipient_first_name, recipient_last_name, recipient_phone FROM orders",
    )

    assert row.recipient_first_name == "Пётр"
    assert row.recipient_last_name == "Одинцов"
    assert row.recipient_phone == RECIPIENT_PHONE


async def test_the_unit_is_written_to_the_columns_it_names(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """Two adjacent text columns, and the reference is the one nobody reads."""
    seeded = await seed_user()
    await _store(worker_container, _an_order(seeded))

    row = await _row_of(engine, "SELECT unit_id, unit_name FROM order_items")

    assert row.unit_id == "1c-unit-778"
    assert row.unit_name == "упак"


async def test_the_price_is_written_to_the_columns_it_names(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    seeded = await seed_user()
    await _store(worker_container, _an_order(seeded))

    row = await _row_of(
        engine,
        "SELECT unit_price_amount, unit_price_currency FROM order_items",
    )

    assert row.unit_price_amount == Decimal("12.34")
    assert row.unit_price_currency == Currency.RUB.value


async def test_the_total_is_recomputed_from_the_lines_that_came_back(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """No total column exists, so this is the only thing that proves it adds up."""
    seeded = await seed_user()

    await _store(worker_container, _an_order(seeded))

    loaded = await _load(worker_container, make_order_id())

    assert loaded is not None
    assert loaded.total.amount == Decimal("74.04")
    assert loaded.total.currency is Currency.RUB


async def test_a_cancelled_order_keeps_who_cancelled_it_and_why(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """Both halves of the cancellation land, and an event is recorded on the way.

    A loaded aggregate can only record one because the gateway injects the
    request-scoped collection: it is not a column, so SQLAlchemy leaves the
    attribute unset and the first ``cancel`` would fail without it.
    """
    seeded = await seed_user()
    await _store(worker_container, _an_order(seeded))

    async with worker_container(scope=Scope.REQUEST) as editor:
        gateway: OrderCommandGateway = await editor.get(OrderCommandGateway)
        transaction: TransactionManager = await editor.get(TransactionManager)
        loaded = await gateway.by_id(make_order_id())
        assert loaded is not None
        loaded.cancel(
            initiated_by=CancellationInitiator.MANAGER,
            reason=CancellationReason(value="Товара не оказалось на складе"),
        )
        await transaction.commit()

    reloaded = await _load(worker_container, make_order_id())

    assert reloaded is not None
    assert reloaded.status is OrderStatus.CANCELLED
    assert reloaded.cancelled_by is CancellationInitiator.MANAGER
    assert reloaded.cancellation_reason == CancellationReason(
        value="Товара не оказалось на складе",
    )


async def test_a_second_order_on_one_number_is_refused_as_ours(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
) -> None:
    """The number comes from a sequence, so a clash means a hand-written insert.

    It is refused all the same, and refused as an ``InfrastructureError`` — the
    gateway flushes so that no ``IntegrityError`` from the driver escapes past
    the adapter and surfaces later as a commit that silently did not happen.
    """
    seeded = await seed_user()
    await _store(worker_container, _an_order(seeded))

    clash = _an_order(seeded, order_id=make_order_id(OTHER_ORDER_ID))

    async with worker_container(scope=Scope.REQUEST) as scope:
        gateway: OrderCommandGateway = await scope.get(OrderCommandGateway)

        with pytest.raises(RepoError):
            await gateway.add(clash)


def _an_order(
    customer: User,
    order_id: OrderId | None = None,
    recipient_last_name: str | None = "Одинцов",
) -> Order:
    """One order whose every field differs from every field beside it.

    Product 4 rather than product 1, six pieces rather than one, twelve roubles
    and thirty-four kopecks rather than a round number: a mapping that reads the
    wrong column has to come back with a value the assertions can name.
    """
    priced = make_priced_product(index=4, price="12.34")
    line = OrderLine(
        position=1,
        product_id=priced.product_id,
        sku=priced.sku,
        name=ProductName(value=PRODUCT_NAME),
        unit=make_unit("1c-unit-778", "упак"),
        unit_price=priced.unit_price,
        quantity=make_quantity(6),
    )

    return Order.place(
        order_id=order_id if order_id is not None else make_order_id(),
        order_number=make_order_number(),
        events_collection=make_events_collection(),
        placement=Placement(
            customer_id=customer.id,
            lines=(line,),
            delivery_address=make_delivery_address(),
            recipient=make_recipient("Пётр", recipient_last_name, RECIPIENT_PHONE),
            comment=make_order_comment(ORDER_COMMENT),
            price_type_id=make_price_type_id(),
        ),
    )


async def _store(container: AsyncContainer, order: Order) -> None:
    async with container(scope=Scope.REQUEST) as scope:
        gateway: OrderCommandGateway = await scope.get(OrderCommandGateway)
        transaction: TransactionManager = await scope.get(TransactionManager)
        await gateway.add(order)
        await transaction.commit()


async def _load(container: AsyncContainer, order_id: OrderId) -> Order | None:
    async with container(scope=Scope.REQUEST) as scope:
        gateway: OrderCommandGateway = await scope.get(OrderCommandGateway)
        return await gateway.by_id(order_id)


async def _row_of(engine: AsyncEngine, statement: str) -> Row[tuple[object, ...]]:
    """The one row the statement selects, read as the database holds it.

    SQL text rather than the mapped table, because the columns under test carry
    type decorators that would rebuild the very values the assertion is trying
    to look past.
    """
    async with engine.connect() as connection:
        return (await connection.execute(text(statement))).one()
