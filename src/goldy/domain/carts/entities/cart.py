from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, Self, final

from goldy.domain.carts.entities.cart_line import CartLine
from goldy.domain.carts.errors import (
    CartLineLimitExceededError,
    CartLineNotFoundError,
    EmptyCartError,
)
from goldy.domain.carts.events import (
    CartCleared,
    CartCreated,
    CartItemAdded,
    CartItemQuantityChanged,
    CartItemRemoved,
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

    Every change records an event, the way ``User`` and ``Order`` do. They are
    facts about a draft rather than about a sale, and today nothing consumes
    them — but an aggregate that takes an ``EventsCollection`` and writes
    nothing into it is a promise the command gateway keeps for nobody, and the
    day somebody wants to know which products are abandoned in carts, the
    facts are already in the outbox. The one business fact of the whole flow
    stays ``OrderPlaced``; these describe the draft it came from.
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
        cart = cls(
            id=cart_id,
            events_collection=events_collection,
            user_id=user_id,
        )
        cart.events_collection.add_event(CartCreated(cart_id=cart_id, user_id=user_id))
        return cart

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

        if line is None:
            if len(self.lines) >= MAX_CART_LINES:
                msg = (
                    f"Cart '{self.id}' cannot hold more than "
                    f"{MAX_CART_LINES} different products."
                )
                raise CartLineLimitExceededError(msg)

            line = CartLine(product_id=product_id, quantity=quantity)
            self.lines.append(line)
        else:
            line.quantity += quantity

        self.updated_at = datetime.now(UTC)
        self.events_collection.add_event(
            CartItemAdded(
                cart_id=self.id,
                user_id=self.user_id,
                product_id=product_id.value,
                quantity=line.quantity.value,
            ),
        )

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

        if line.quantity.value == 1:
            self.remove_item(product_id)
            return

        self.set_item_quantity(product_id, Quantity(value=line.quantity.value - 1))

    def set_item_quantity(self, product_id: ProductId, quantity: Quantity) -> None:
        """Sets a line to an absolute quantity, as the keypad screen does.

        Raises:
            CartLineNotFoundError: that product is not in the cart.
        """
        line = self._require_line(product_id)
        line.quantity = quantity
        self.updated_at = datetime.now(UTC)
        self.events_collection.add_event(
            CartItemQuantityChanged(
                cart_id=self.id,
                user_id=self.user_id,
                product_id=product_id.value,
                quantity=quantity.value,
            ),
        )

    def remove_item(self, product_id: ProductId) -> None:
        """Takes a product out entirely.

        Raises:
            CartLineNotFoundError: that product is not in the cart.
        """
        line = self._require_line(product_id)
        self.lines.remove(line)
        self.updated_at = datetime.now(UTC)
        self.events_collection.add_event(
            CartItemRemoved(
                cart_id=self.id,
                user_id=self.user_id,
                product_id=product_id.value,
            ),
        )

    def clear(self) -> None:
        """Empties the cart, idempotently.

        Clearing an already empty cart does nothing rather than failing, and
        records nothing either. Checkout calls this, and a cart that is already
        in the state asked for is not a reason to fail an order that otherwise
        went through — nor a fact worth announcing.
        """
        if not self.lines:
            return

        line_count = len(self.lines)
        self.lines.clear()
        self.updated_at = datetime.now(UTC)
        self.events_collection.add_event(
            CartCleared(cart_id=self.id, user_id=self.user_id, line_count=line_count),
        )

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
