from collections.abc import Sequence
from decimal import Decimal
from typing import final, override

from sqlalchemy import RowMapping

from goldy.application.common.views.cart import CartLineView, CartView
from goldy.application.common.views.money import MoneyView
from goldy.infrastructure.mappers.cart_row_view_mapper import CartRowViewMapper


@final
class SqlAlchemyCartRowViewMapper(CartRowViewMapper):
    """Flattens the joined cart rows into the view the cart screen renders.

    By hand rather than with adaptix, for the reason every row mapper here is:
    a ``RowMapping`` carries no field types for a converter to introspect, and
    most of what a line holds is not a column of the cart at all — the name and
    the price come from outer joins, the stock from a sum over warehouses.

    Only two columns need unwrapping, and which two is not obvious: the cart's
    own ``product_id`` and ``quantity`` carry type decorators and arrive as
    value objects, while everything joined in comes from the projection, which
    is Core-only and hands back plain text and numbers.

    ``amount`` being NULL is an ordinary state and not a defect: this
    customer's price type simply prices no such product. The line keeps its
    quantity and loses its price, the screen prints "price on request", and
    the total counts what it can — printing a zero would read as "free".
    """

    @override
    def to_cart_view(self, rows: Sequence[RowMapping]) -> CartView:
        lines = tuple(self._to_line_view(row) for row in rows)
        totals = [line.line_total for line in lines if line.line_total is not None]

        if not totals:
            return CartView(lines=lines, total=MoneyView.zero())

        return CartView(
            lines=lines,
            total=MoneyView(
                amount=sum((total.amount for total in totals), start=Decimal("0.00")),
                currency=totals[0].currency,
            ),
        )

    def _to_line_view(self, row: RowMapping) -> CartLineView:
        """Every price in a cart comes from one price type, hence one currency.

        A price type is denominated in exactly one currency, so taking the
        currency off the first priced line for the total cannot mix two. An
        unpriced line contributes nothing and is counted by
        ``CartView.has_unpriced_lines`` instead, which is what keeps "checkout"
        from being offered on a total that is short.
        """
        quantity: int = row["quantity"].value
        amount: Decimal | None = row["amount"]
        currency: str | None = row["currency"]
        unit_price: MoneyView | None = None
        line_total: MoneyView | None = None

        if amount is not None and currency is not None:
            unit_price = MoneyView(amount=amount, currency=currency)
            line_total = MoneyView(amount=amount * quantity, currency=currency)

        return CartLineView(
            product_id=row["product_id"].value,
            sku=row["sku"],
            name=row["name"],
            unit_name=row["unit_name"],
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            stock=row["stock"],
            is_available=bool(row["is_active"]),
        )
