from dataclasses import dataclass
from uuid import UUID

from goldy.domain.common.event import Event


@dataclass(frozen=True, slots=True, kw_only=True)
class CartCreated(Event):
    """A person got a cart of their own, on their first addition."""

    cart_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class CartItemAdded(Event):
    """A product went into the cart, or more of it did.

    ``quantity`` is what the line holds *after* the addition, not what was
    added: a consumer reacting to the cart wants to know its state, and the
    delta is recoverable from the previous event where the state is not.
    """

    cart_id: UUID
    user_id: UUID
    product_id: str
    quantity: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CartItemQuantityChanged(Event):
    """A line was set to a different number of pieces, up or down."""

    cart_id: UUID
    user_id: UUID
    product_id: str
    quantity: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CartItemRemoved(Event):
    """A product left the cart entirely, by a tap or by the last ``-``."""

    cart_id: UUID
    user_id: UUID
    product_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CartCleared(Event):
    """Everything left the cart at once — by the customer or by a checkout."""

    cart_id: UUID
    user_id: UUID
    line_count: int
