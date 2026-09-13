from dataclasses import dataclass

from goldy.application.common.views.money import MoneyView


@dataclass(frozen=True, slots=True, kw_only=True)
class Notification:
    """What a handler decided to say, before anyone has decided in which language.

    A typed message rather than a key with a bag of arguments. Each subclass
    names its fields, so a handler that forgets one fails to construct the
    message instead of shipping a placeholder nobody filled, and a renderer
    that needs a field reads it by name instead of hoping the dictionary has
    it. The subclasses are the vocabulary of the notifier: adding a kind of
    message is adding a class here and a rendering for it in the adapter.

    Text and numbers only, no domain values. A notification is on its way out
    of the application, and the renderer behind the port has no business
    unwrapping a ``Money``.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPlacedNotification(Notification):
    """To staff: a new order is in the queue, and here is whose and where to."""

    number: str
    customer_name: str
    phone_number: str
    address: str
    line_count: int
    total: MoneyView


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderStatusChangedNotification(Notification):
    """To the customer: the order moved on, and why if it was stopped.

    ``reason`` is set on a cancellation and nowhere else. It is the one
    transition whose explanation the person is owed, and the renderer chooses
    a wording with a reason in it only when there is one to print.
    """

    number: str
    status: str
    reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderDeliveryAddressChangedNotification(Notification):
    """To the customer: the order is going somewhere else — from here, to here."""

    number: str
    old_address: str
    new_address: str
