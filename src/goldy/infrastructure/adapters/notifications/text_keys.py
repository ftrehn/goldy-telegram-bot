"""Every Fluent message key the notifier renders, in one place.

The same registry the bot keeps for its screens, for the same reasons: a key is
a contract with the ``.ftl`` files, and two literals spelled slightly
differently is how one of them starts pointing at a message nobody wrote.

It lives beside the renderer rather than in the application layer because the
key is the renderer's business alone. A handler says *what* to say by building
a typed ``Notification``; which Fluent message spells that in a given language,
and with which placeholders, is knowledge of the files that ship with this
adapter and of nothing above it.

Reason and no reason are two keys rather than one message with a selector.
Fluent can branch, but a branch means every rendering carries every argument —
and the one thing this project has learned about Fluent is that a forgotten
argument does not degrade into visible text, it raises.
"""

from typing import Final

NOTIFICATION_ORDER_PLACED: Final[str] = "notification-order-placed"
"""To staff: a new order is in the queue. Args: number, customer, phone,
address, lines, total."""

NOTIFICATION_ORDER_STATUS_CHANGED: Final[str] = "notification-order-status-changed"
"""To the customer: the order moved on. Args: number, status."""

NOTIFICATION_ORDER_STATUS_CHANGED_REASON: Final[str] = (
    "notification-order-status-changed-reason"
)
"""To the customer, when the transition carried one. Args: number, status,
reason. In practice that is a cancellation, which is the one transition whose
explanation the person is owed."""

NOTIFICATION_ORDER_ADDRESS_CHANGED: Final[str] = "notification-order-address-changed"
"""To the customer: the order is going somewhere else. Args: number,
old_address, new_address."""

NOTIFICATION_ORDER_HANDOVER_REJECTED: Final[str] = "notification-order-handover-rejected"
"""To staff: the site refused an order handed over to it. Args: number, code."""
