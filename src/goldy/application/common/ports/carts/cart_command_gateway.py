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

    Two lookups, and which one a use case calls is a decision about what
    happens when there is no cart. "One cart per person" spans aggregates and
    cannot be held in the domain: two simultaneous additions both find nothing
    and both insert. A unique index holds it and :meth:`ensure_for` removes the
    race without an error and without a retry — which matters, because after an
    ``IntegrityError`` the session is rollback-only and a retry inside the
    handler would hit ``PendingRollbackError``.
    """

    @abstractmethod
    async def ensure_for(self, user_id: UserId) -> Cart:
        """This person's cart, created on the spot if they have none.

        Implemented as ``INSERT ... ON CONFLICT (user_id) DO NOTHING RETURNING
        id`` followed by a read when the insert returned nothing, so two
        concurrent first additions both end up on the same row.

        Called where an absent cart is not a failure: adding to the cart, and
        placing an order — which then meets an empty cart and refuses with
        ``EmptyCartError``, and that is the real backstop against a double tap
        on "confirm".
        """
        raise NotImplementedError

    @abstractmethod
    async def by_user_id(self, user_id: UserId) -> Cart | None:
        """This person's cart, or nothing.

        Called where the cart has to exist already — removing a line, changing
        a quantity, emptying it — so that ``None`` becomes
        ``CartNotFoundError`` rather than a cart conjured up to be emptied.
        """
        raise NotImplementedError
