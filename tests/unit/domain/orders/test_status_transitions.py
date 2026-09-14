from goldy.domain.orders.status_transitions import (
    ALLOWED_ORDER_TRANSITIONS,
    CUSTOMER_CANCELLABLE_STATUSES,
    EDITABLE_ORDER_STATUSES,
    TERMINAL_ORDER_STATUSES,
)
from goldy.domain.orders.values.order_status import OrderStatus


def test_every_status_can_be_asked_what_it_may_become() -> None:
    """A status missing from the table would fail as a ``KeyError``.

    ``Order._transition_to`` indexes the table by the status it is in, so a
    status added without a row would surface as a lookup failure in the middle
    of a command rather than as a refused transition.
    """
    assert set(ALLOWED_ORDER_TRANSITIONS) == set(OrderStatus)


def test_the_terminal_statuses_are_exactly_the_ones_with_nowhere_to_go() -> None:
    """Terminality is derived, not restated.

    The empty sets in the table already refuse every move out; this set only
    names them, and the two disagreeing is how a "finished" order becomes
    editable again.
    """
    dead_ends = {
        status for status, allowed in ALLOWED_ORDER_TRANSITIONS.items() if not allowed
    }

    assert dead_ends == TERMINAL_ORDER_STATUSES


def test_nothing_terminal_is_editable_or_cancellable_by_a_customer() -> None:
    assert not TERMINAL_ORDER_STATUSES & EDITABLE_ORDER_STATUSES
    assert not TERMINAL_ORDER_STATUSES & CUSTOMER_CANCELLABLE_STATUSES


def test_a_customer_may_only_withdraw_an_order_that_has_not_left_the_shop() -> None:
    """A manager may stop anything unfinished; a customer only an undispatched order.

    Confirmation does not take the right to change their mind away — it means
    the order was accepted for picking. After ``SHIPPED`` cancelling would be a
    return, and returns do not live in the bot.
    """
    assert set(CUSTOMER_CANCELLABLE_STATUSES) == {
        OrderStatus.NEW,
        OrderStatus.CONFIRMED,
    }
