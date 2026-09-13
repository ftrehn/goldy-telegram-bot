from abc import abstractmethod
from typing import Protocol

from goldy.application.common.ports.notifications.notification import Notification


class NotificationRenderer(Protocol):
    """Turns a typed notification into text in one language.

    A port rather than a call into the translation library, because the
    library is a presentation-shaped dependency and this runs in the worker.
    The adapter behind it ships its own ``.ftl`` files and owns the message
    keys: the handler chooses *what* to say by building a ``Notification``,
    and the adapter knows how to say it in a given language.

    Rendering is expected to fail loudly. A notification the adapter has no
    wording for, or a translation whose placeholder names a field the
    notification does not carry, raises rather than producing a message with
    ``{ $number }`` in it — a customer reading that learns nothing, and nobody
    finds out.
    """

    @abstractmethod
    def render(self, notification: Notification, locale: str) -> str:
        raise NotImplementedError
