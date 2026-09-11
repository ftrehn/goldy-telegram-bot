from decimal import Decimal

from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.values.user_status import UserStatus
from goldy.infrastructure.mappers.sqlalchemy_order_row_view_mapper import (
    SqlAlchemyOrderRowViewMapper,
)
from tests.unit.factories.order_row_factories import (
    make_order_line_row,
    make_order_list_row,
    make_order_row,
)

MAPPER = SqlAlchemyOrderRowViewMapper()


def test_every_value_object_is_unwrapped_to_a_primitive() -> None:
    """The view crosses out of the domain, so nothing domain-shaped may ride along."""
    row = make_order_row(comment="Позвонить за час до доставки")

    view = MAPPER.to_view(row, [MAPPER.to_line_view(make_order_line_row())])

    assert view.number == "1001"
    assert view.status == "new"
    assert view.price_type_id == "1c-price-type-wholesale"
    assert view.delivery_address == "Москва, Тверская 1, кв. 5"
    assert view.recipient_phone_number == "+79991234567"
    assert view.comment == "Позвонить за час до доставки"
    assert view.cancelled_by is None
    assert view.cancellation_reason is None


def test_a_cancelled_order_names_who_stopped_it_and_why() -> None:
    row = make_order_row(
        status=OrderStatus.CANCELLED,
        cancelled_by=CancellationInitiator.MANAGER,
        cancellation_reason="Товара не оказалось на складе",
    )

    view = MAPPER.to_view(row, [])

    assert view.cancelled_by == "manager"
    assert view.cancellation_reason == "Товара не оказалось на складе"


def test_the_card_reports_the_rules_the_aggregate_enforces() -> None:
    """The flags are the cancellation rule, not a second spelling of it.

    A card is built from a row rather than from the aggregate, so if these came
    from a literal status comparison here they would drift away from
    ``Order.cancel`` the first time the transition table changed, and drift
    without anything failing.
    """
    new = MAPPER.to_view(make_order_row(status=OrderStatus.NEW), [])
    shipped = MAPPER.to_view(make_order_row(status=OrderStatus.SHIPPED), [])
    completed = MAPPER.to_view(make_order_row(status=OrderStatus.COMPLETED), [])

    assert (new.is_cancellable, new.is_editable, new.is_terminal) == (True, True, False)
    assert (shipped.is_cancellable, shipped.is_editable) == (False, False)
    assert completed.is_terminal is True


def test_a_blocked_buyer_is_flagged_on_the_card_and_in_the_queue() -> None:
    """A badge for the manager to weigh, never a rule: the order still runs."""
    card = MAPPER.to_view(make_order_row(customer_status=UserStatus.BLOCKED), [])
    queued = MAPPER.to_list_item_view(
        make_order_list_row(customer_status=UserStatus.BLOCKED),
    )

    assert card.customer_is_blocked is True
    assert queued.customer_is_blocked is True


def test_a_line_multiplies_its_own_snapshot_price() -> None:
    row = make_order_line_row(quantity=3, price="19.99")

    line = MAPPER.to_line_view(row)

    assert line.quantity == 3
    assert line.unit_price.amount == Decimal("19.99")
    assert line.line_total.amount == Decimal("59.97")
    assert line.line_total.currency == "rub"


def test_a_line_without_an_article_keeps_none() -> None:
    """``None`` must not become the string ``"None"`` on the way out."""
    line = MAPPER.to_line_view(make_order_line_row(with_sku=False))

    assert line.sku is None


def test_stock_is_shown_when_the_catalog_still_has_the_product() -> None:
    """Today's figure beside what was ordered, and nothing when it is gone."""
    stocked = MAPPER.to_line_view(make_order_line_row(stock="12.500"))
    withdrawn = MAPPER.to_line_view(make_order_line_row(stock=None))

    assert stocked.stock == Decimal("12.500")
    assert withdrawn.stock is None


def test_the_card_total_adds_the_lines_up() -> None:
    lines = [
        MAPPER.to_line_view(make_order_line_row(position=1, quantity=2, price="19.99")),
        MAPPER.to_line_view(
            make_order_line_row(position=2, index=2, quantity=1, price="5.01"),
        ),
    ]

    view = MAPPER.to_view(make_order_row(), lines)

    assert view.total.amount == Decimal("44.99")
    assert view.total.currency == "rub"
    assert view.line_count == 2
    assert view.total_quantity == 3


def test_a_list_row_takes_the_total_summed_in_sql() -> None:
    row = make_order_list_row(total="59.97", line_count=2)

    item = MAPPER.to_list_item_view(row)

    assert item.total.amount == Decimal("59.97")
    assert item.total.currency == "rub"
    assert item.line_count == 2
    assert item.customer_name == "Данил Ковалев"


def test_an_order_the_join_found_no_lines_for_is_still_listed() -> None:
    """Worth a zero in the queue rather than a row that silently disappears."""
    item = MAPPER.to_list_item_view(make_order_list_row(total=None, line_count=0))

    assert item.total.amount == Decimal("0.00")
    assert item.line_count == 0


def test_a_buyer_with_no_surname_is_named_by_their_first_name() -> None:
    item = MAPPER.to_list_item_view(make_order_list_row(customer_last_name=None))

    assert item.customer_name == "Данил"
