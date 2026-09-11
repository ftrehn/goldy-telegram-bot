from dataclasses import dataclass
from decimal import Decimal

from goldy.application.common.views.money import MoneyView


@dataclass(frozen=True, slots=True)
class CartLineView:
    """One product in the cart, priced at the moment the cart is drawn.

    The cart stores no price of its own, so everything but the quantity here
    comes from the catalog projection through a ``LEFT JOIN`` taken **without**
    an ``is_active`` filter. Filtering inside the join would make a line vanish
    from the screen and the cart total shrink quietly, which is worse than an
    error the customer can see: nobody notices something that is not there.

    That is what :attr:`is_available` is for. A product withdrawn from the
    catalog between being added and being ordered still appears, marked, and
    the cart screen offers "remove unavailable" and hides "checkout" while any
    such line remains. The name is optional for the same reason the join is
    outer — nothing guarantees the projection still holds a row at all.
    """

    product_id: str
    sku: str | None
    name: str | None
    unit_name: str | None
    quantity: int
    unit_price: MoneyView | None
    line_total: MoneyView | None
    stock: Decimal | None
    is_available: bool

    @property
    def is_priced(self) -> bool:
        """Whether this customer's price type prices this product at all."""
        return self.unit_price is not None

    @property
    def is_in_stock(self) -> bool:
        """Shown as a badge, never used to hide a button."""
        return self.stock is not None and self.stock > 0


@dataclass(frozen=True, slots=True)
class CartView:
    """The cart screen, whether or not the customer has a cart row yet.

    ``GetCartQuery`` never fails with "no cart": a cart is created lazily on
    the first addition, so a freshly registered person has no row at all and an
    error here would greet every new customer on their first ``/cart``. An
    empty view carries empty lines and a zero total, and the screen draws
    "your cart is empty" from that.
    """

    lines: tuple[CartLineView, ...]
    total: MoneyView

    @property
    def is_empty(self) -> bool:
        return not self.lines

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def total_quantity(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def has_unavailable_lines(self) -> bool:
        """Whether "checkout" has to stay hidden until the cart is tidied."""
        return any(not line.is_available for line in self.lines)

    @property
    def has_unpriced_lines(self) -> bool:
        """A product still listed but with no price under this price type."""
        return any(not line.is_priced for line in self.lines)


@dataclass(frozen=True, slots=True)
class CartSummaryView:
    """What a cart command hands back — counts, not contents.

    A full :class:`CartView` needs a join against the catalog and the prices,
    and doing that inside the writing transaction would pay for a second query
    to produce an answer presentation throws away: the cart screen re-reads
    itself through ``GetCartQuery`` on every render. The "add" button only ever
    needs "added, and there are now this many lines".

    ``changed_product_id`` is the product the command touched, so the screen
    can confirm which one without guessing. ``clear_cart`` leaves it unset —
    it touched all of them.
    """

    line_count: int
    total_quantity: int
    changed_product_id: str | None

    @property
    def is_empty(self) -> bool:
        return self.line_count == 0
