from dataclasses import dataclass
from typing import Final, override

from goldy.domain.users.entities.user import User
from goldy.domain.users.services.authorization.base import (
    Permission,
    PermissionContext,
)
from goldy.domain.users.services.authorization.permission import IsStaff, StaffContext
from goldy.domain.users.values.user_id import UserId


@dataclass(frozen=True, kw_only=True)
class OrderAccessContext(PermissionContext):
    """One person proposing to act upon one order.

    Carries ``order_customer_id`` and not the ``Order`` itself, which is the
    whole reason these rules can exist here at all: the context lives in
    ``domain/orders``, so ``domain/users`` still knows nothing about orders and
    the ``domain_package_layers`` contract has no cycle to refuse. The earlier
    ``Order.ensure_belongs_to`` argued the opposite and was wrong — do not
    "fix" it back.

    One context for both rules on purpose, so a query that is open to the buyer
    and to staff alike can say ``AnyOf(IsOrderOwner(), CanManageOrders())``
    instead of branching on who is asking.
    """

    subject: User
    order_customer_id: UserId


class IsOrderOwner(Permission[OrderAccessContext]):
    """The buyer reaching their own order.

    The only thing standing between a guessed identifier and a stranger's
    delivery address.
    """

    @override
    def is_satisfied_by(self, context: OrderAccessContext) -> bool:
        return context.subject.id == context.order_customer_id


class CanManageOrders(Permission[OrderAccessContext]):
    """Staff open any order, whoever placed it.

    Does not restate the staff check: it delegates to an ``IsStaff``, which
    takes a ``StaffContext`` this context has the field for. Restating it here
    would give "who counts as staff" a second definition, and the two would
    part company at the first change to roles.
    """

    def __init__(self) -> None:
        self._is_staff: Final[Permission[StaffContext]] = IsStaff()

    @override
    def is_satisfied_by(self, context: OrderAccessContext) -> bool:
        return self._is_staff.is_satisfied_by(StaffContext(subject=context.subject))
