from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, Self, final

from goldy.domain.carts.entities.cart_line import CartLine
from goldy.domain.carts.errors import (
    CartLineLimitExceededError,
    CartLineNotFoundError,
    EmptyCartError,
)
from goldy.domain.carts.values.cart_id import CartId
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.aggregate import Aggregate
from goldy.domain.common.values.quantity import Quantity
from goldy.domain.users.values.user_id import UserId

if TYPE_CHECKING:
    from goldy.domain.common.events_collection import EventsCollection

MAX_CART_LINES: Final[int] = 100


@final
@dataclass(eq=False, kw_only=True)
class Cart(Aggregate[CartId]):
    """A draft order belonging to a person, shared by all their platforms.

    The key is a surrogate ``CartId`` with ``user_id`` beside it rather than
    the user id itself: keying one aggregate by another welds their lifecycles
    together. "One cart per person" therefore spans aggregates, and rules that
    span aggregates are held in this project by a unique index — here on
    ``user_id`` — never by reading before writing, because the read loses to a
    concurrent request. Because the cart belongs to the human and not to an
    account, starting in Telegram and finishing in MAX needs no code at all.

    There is no cart status. A cart that has been checked out is simply empty
    again, so no "ordered cart" state exists for somebody to render one day as
    though it were still a draft.

    **This aggregate records no events, and deliberately has no ``_record``.**
    Everything an aggregate puts into its ``EventsCollection`` is drained into
    the outbox inside the same transaction and published to RabbitMQ by the
    relay. Somebody pressing ``+`` three times and ``-`` once would produce four
    outbox rows and four messages nobody consumes. An event is a fact someone
    reacts to; editing a draft is not one, and the single business fact here is
    called ``OrderPlaced``. ``events_collection`` is inherited from
    ``Aggregate`` because the command gateway contract hands back whole
    aggregates — it is simply left unused.
    """

    user_id: UserId
    lines: list[CartLine] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        cart_id: CartId,
        events_collection: EventsCollection,
        user_id: UserId,
    ) -> Self:
        return cls(
            id=cart_id,
            events_collection=events_collection,
            user_id=user_id,
        )

    def add_item(self, product_id: ProductId, quantity: Quantity) -> None:
        """Puts a product in, or adds to what is already there.

        There is no ceiling check on the resulting quantity here: ``Quantity``
        refuses anything above its own maximum when the two are added, so the
        rule is stated once and holds for every caller.

        Raises:
            CartLineLimitExceededError: the cart already holds
                ``MAX_CART_LINES`` different products. Raising the quantity of
                a product already in a full cart stays allowed.
            QuantityLimitExceededError: the resulting quantity is over the
                per-line ceiling.
        """
        line = self.line_for(product_id)

        if line is not None:
            line.quantity += quantity
            self._touch()
            return

        if len(self.lines) >= MAX_CART_LINES:
            msg = (
                f"Cart '{self.id}' cannot hold more than "
                f"{MAX_CART_LINES} different products."
            )
            raise CartLineLimitExceededError(msg)

        self.lines.append(CartLine(product_id=product_id, quantity=quantity))
        self._touch()

    def decrease_item(self, product_id: ProductId) -> None:
        """Takes one piece off a line, and the whole line off the last piece.

        The ``-`` button is therefore not obliged to know that at a quantity of
        one it means "remove", nor to guess the current quantity from a
        keyboard that was drawn two seconds ago. ``Quantity`` has no zero by
        construction, so "one less than one" can only be expressed as the line
        going away.

        Raises:
            CartLineNotFoundError: that product is not in the cart.
        """
        line = self._require_line(product_id)

        if line.quantity.value > 1:
            line.quantity = Quantity(value=line.quantity.value - 1)
        else:
            self.lines.remove(line)

        self._touch()

    def set_item_quantity(self, product_id: ProductId, quantity: Quantity) -> None:
        """Sets a line to an absolute quantity, as the keypad screen does.

        Raises:
            CartLineNotFoundError: that product is not in the cart.
        """
        line = self._require_line(product_id)
        line.quantity = quantity
        self._touch()

    def remove_item(self, product_id: ProductId) -> None:
        """Takes a product out entirely.

        Raises:
            CartLineNotFoundError: that product is not in the cart.
        """
        line = self._require_line(product_id)
        self.lines.remove(line)
        self._touch()

    def clear(self) -> None:
        """Empties the cart, idempotently.

        Clearing an already empty cart does nothing rather than failing.
        Checkout calls this, and a cart that is already in the state asked for
        is not a reason to fail an order that otherwise went through.
        """
        if not self.lines:
            return

        self.lines.clear()
        self._touch()

    def ensure_not_empty(self) -> None:
        """Guards checkout.

        Raises:
            EmptyCartError: there is nothing in the cart to order.
        """
        if not self.lines:
            msg = f"Cart '{self.id}' is empty and cannot be ordered."
            raise EmptyCartError(msg)

    def line_for(self, product_id: ProductId) -> CartLine | None:
        return next(
            (line for line in self.lines if line.product_id == product_id),
            None,
        )

    @property
    def is_empty(self) -> bool:
        return not self.lines

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def total_quantity(self) -> int:
        return sum(line.quantity.value for line in self.lines)

    def _require_line(self, product_id: ProductId) -> CartLine:
        line = self.line_for(product_id)

        if line is None:
            msg = f"Cart '{self.id}' has no line for product '{product_id}'."
            raise CartLineNotFoundError(msg)

        return line

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
