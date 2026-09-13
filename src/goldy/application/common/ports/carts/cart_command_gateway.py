from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.domain.carts.entities.cart import Cart
    from goldy.domain.users.values.user_id import UserId


class CartCommandGateway(Protocol):
    """Write-side access to the :class:`Cart` aggregate.

    Hands back whole aggregates, lines included: the rules about what may go in
    are checked against the entire line list — one line per product, a ceiling
    on how many — so a partially loaded cart could pass a check it should have
    failed.

    A thin gateway, on purpose: one read and one add, the shape
    ``UserCommandGateway`` has. Whether a person who has no cart yet gets one
    is not a question about storage, so it is not answered here —
    ``CartProvider`` in the application layer takes that decision, and this
    port only reports when a concurrent request took it first.
    """

    @abstractmethod
    async def add(self, cart: Cart) -> None:
        """Inserts a new cart, flushing so a clash surfaces here.

        "One cart per person" spans aggregates and is held by a unique index on
        ``user_id``: two simultaneous first additions both find nothing and
        both insert, and the second insert is the only place the race can be
        seen. The clash is reported as an error the caller can act on, and
        the session stays usable afterwards — the caller's next move is to
        read the cart that won.

        Raises:
            CartAlreadyExistsError: this person already has a cart.
        """
        raise NotImplementedError

    @abstractmethod
    async def by_user_id(self, user_id: UserId) -> Cart | None:
        """This person's cart, or nothing."""
        raise NotImplementedError
