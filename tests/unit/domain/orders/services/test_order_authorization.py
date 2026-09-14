from dataclasses import fields

import pytest

from goldy.domain.orders.services.authorization.permission import (
    CanManageOrders,
    IsOrderOwner,
    OrderAccessContext,
)
from goldy.domain.users.errors import AuthorizationError
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.services.authorization.composite import AnyOf
from goldy.domain.users.values.user_role import UserRole
from tests.unit.factories.domain_factories import make_customer, make_user_id
from tests.unit.factories.shop_factories import make_order_access_context
from tests.unit.support import People

OTHER_USER_ID: str = "99999999-9999-9999-9999-999999999999"


def test_the_buyer_may_reach_their_own_order() -> None:
    customer = make_customer()

    assert (
        IsOrderOwner().is_satisfied_by(make_order_access_context(customer, customer))
        is True
    )


def test_somebody_else_is_turned_away_from_the_order() -> None:
    """The only thing standing between a guessed id and a stranger's address."""
    stranger = make_customer(user_id=OTHER_USER_ID)
    customer = make_customer()

    assert (
        IsOrderOwner().is_satisfied_by(make_order_access_context(stranger, customer))
        is False
    )


@pytest.mark.parametrize(
    ("role", "allowed"),
    (
        (UserRole.CUSTOMER, False),
        (UserRole.MANAGER, True),
        (UserRole.ADMIN, True),
    ),
)
def test_staff_open_anybody_s_order(
    people: People,
    role: UserRole,
    *,
    allowed: bool,
) -> None:
    """Delegated to ``IsStaff`` rather than restated, so there is one definition."""
    context = make_order_access_context(
        people[role], make_customer(user_id=OTHER_USER_ID)
    )

    assert CanManageOrders().is_satisfied_by(context) is allowed


def test_a_card_open_to_both_is_one_rule_made_of_two_halves(
    access: AccessService,
    people: People,
) -> None:
    """Why both rules share a context: ``GetOrderQuery`` needs ``AnyOf``.

    The customer opens their own order and a manager opens anybody's, and that
    is a single authorization question with two ways of answering yes.
    """
    permission = AnyOf(IsOrderOwner(), CanManageOrders())
    customer = make_customer()

    access.authorize(permission, context=make_order_access_context(customer, customer))
    access.authorize(
        permission, context=make_order_access_context(people[UserRole.MANAGER], customer)
    )


def test_a_stranger_who_is_not_staff_is_refused(
    access: AccessService,
) -> None:
    permission = AnyOf(IsOrderOwner(), CanManageOrders())
    context = make_order_access_context(
        make_customer(user_id=OTHER_USER_ID), make_customer()
    )

    with pytest.raises(AuthorizationError):
        access.authorize(permission, context=context)


def test_the_context_carries_the_customer_id_and_not_the_order() -> None:
    """Which is what keeps ``domain/users`` ignorant of orders.

    A context holding an ``Order`` would make the user package import the order
    package, and the ``domain_package_layers`` contract refuses that cycle. The
    old ``Order.ensure_belongs_to`` argued the reverse and was wrong.

    The field set is what the test pins down, not the id: import-linter only
    fails once somebody actually imports ``Order`` into ``users``, which is one
    step later than adding ``order: Order`` here. ``PermissionContext`` is an
    empty frozen dataclass, so this set is the whole context.
    """
    context = make_order_access_context(make_customer(), make_customer())

    announced = {attribute.name for attribute in fields(OrderAccessContext)}
    assert announced == {"subject", "order_customer_id"}
    assert context.order_customer_id == make_user_id()
