from collections.abc import Sequence
from decimal import Decimal
from typing import final, override

from sqlalchemy import RowMapping

from goldy.application.common.views.money import MoneyView
from goldy.application.common.views.order import (
    OrderLineView,
    OrderListItemView,
    OrderView,
)
from goldy.domain.orders.status_transitions import (
    CUSTOMER_CANCELLABLE_STATUSES,
    EDITABLE_ORDER_STATUSES,
    TERMINAL_ORDER_STATUSES,
)
from goldy.domain.users.values.user_status import UserStatus
from goldy.infrastructure.mappers.order_row_view_mapper import OrderRowViewMapper


@final
class SqlAlchemyOrderRowViewMapper(OrderRowViewMapper):
    """Flattens order rows into the views the card and the lists render.

    Written by hand rather than with adaptix, for the reason the user row
    mapper is: a ``RowMapping`` carries no field types for a converter to
    introspect, and the lines are not columns of the order row at all — they
    come from a second query and are grafted on here.

    The values arrive as value objects rather than as text, because the columns
    carry type decorators; unwrapping them is the same job the aggregate mapper
    does in the other direction.

    This is the one row mapper allowed to import a domain constant, and the
    three it imports are the reason. ``is_cancellable``, ``is_editable`` and
    ``is_terminal`` are the cancellation and editing rules the aggregate
    enforces, and the view is built from a row rather than from the aggregate —
    so the alternative is a second statement of those rules spelled
    ``status == "new"``, which drifts away from ``Order`` on the first edit and
    drifts silently.
    """

    @override
    def to_view(self, row: RowMapping, lines: Sequence[OrderLineView]) -> OrderView:
        status = row["status"]
        comment = row["comment"]
        cancelled_by = row["cancelled_by"]
        cancellation_reason = row["cancellation_reason"]

        return OrderView(
            id=row["id"],
            number=row["number"].value,
            customer_id=row["customer_id"],
            customer_is_blocked=row["customer_status"] is UserStatus.BLOCKED,
            status=status.value,
            price_type_id=row["price_type_id"].value,
            delivery_address=row["delivery_address"].value,
            recipient_first_name=row["recipient_first_name"],
            recipient_last_name=row["recipient_last_name"],
            recipient_phone_number=row["recipient_phone"].value,
            comment=comment.value if comment is not None else None,
            cancelled_by=cancelled_by.value if cancelled_by is not None else None,
            cancellation_reason=(
                cancellation_reason.value if cancellation_reason is not None else None
            ),
            lines=tuple(lines),
            total=_total_of(lines),
            is_cancellable=status in CUSTOMER_CANCELLABLE_STATUSES,
            is_editable=status in EDITABLE_ORDER_STATUSES,
            is_terminal=status in TERMINAL_ORDER_STATUSES,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @override
    def to_line_view(self, row: RowMapping) -> OrderLineView:
        """One snapshot line, with the current stock beside what was ordered.

        ``stock`` is the only figure here that is not part of the order. It is
        today's number from the catalog projection, joined so that a manager
        deciding whether to confirm can see what is on the shelf; everything
        else is what was agreed at checkout and is never looked up through
        ``product_id``.
        """
        sku = row["sku"]
        quantity = row["quantity"].value
        amount = row["unit_price_amount"]
        currency = row["unit_price_currency"].value

        return OrderLineView(
            position=row["position"],
            product_id=row["product_id"].value,
            sku=sku.value if sku is not None else None,
            name=row["name"].value,
            unit_name=row["unit_name"],
            quantity=quantity,
            unit_price=MoneyView(amount=amount, currency=currency),
            line_total=MoneyView(amount=amount * quantity, currency=currency),
            stock=row["stock"],
        )

    @override
    def to_list_item_view(self, row: RowMapping) -> OrderListItemView:
        """One row of a history or of the queue, totalled in SQL.

        The total arrives already summed and may be missing altogether: the
        lines are joined outer, so an order that somehow has none is still
        listed rather than silently dropped out of the queue.
        """
        amount = row["total_amount"]
        currency = row["total_currency"]

        return OrderListItemView(
            id=row["id"],
            number=row["number"].value,
            customer_id=row["customer_id"],
            customer_name=_customer_name(row),
            customer_is_blocked=row["customer_status"] is UserStatus.BLOCKED,
            status=row["status"].value,
            total=(
                MoneyView(amount=amount, currency=currency)
                if amount is not None and currency is not None
                else MoneyView.zero()
            ),
            line_count=row["line_count"],
            created_at=row["created_at"],
        )


def _total_of(lines: Sequence[OrderLineView]) -> MoneyView:
    """Adds the lines up, in the currency they are all priced in.

    Safe to take the currency from the first line because ``Order.place``
    refused a mixed-currency order once and the lines of a placed order never
    change afterwards — which is the same reasoning ``Order.total`` relies on.
    """
    if not lines:
        return MoneyView.zero()

    total = sum((line.line_total.amount for line in lines), Decimal("0.00"))

    return MoneyView(amount=total, currency=lines[0].line_total.currency)


def _customer_name(row: RowMapping) -> str | None:
    """The buyer's name for the queue, absent when there is nothing to print."""
    parts = [row["customer_first_name"], row["customer_last_name"]]
    name = " ".join(part for part in parts if part)

    return name or None
