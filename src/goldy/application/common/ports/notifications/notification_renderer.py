from abc import abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NotificationText:
    """What to say, before anyone has decided in which language.

    A key and its arguments rather than a string, so the handler picks the
    message and the recipient's own locale picks the wording. Building the
    sentence in the handler would mean one language for everybody, and the
    person being written to is not the one running the worker.

    ``args`` carries only ``str`` and ``int``. Money and quantities are
    formatted before they get here: a ``Decimal`` would reach Fluent as a
    number and be printed by its own rules, which are not the shop's.
    """

    key: str
    args: Mapping[str, str | int] = field(default_factory=dict)


class NotificationRenderer(Protocol):
    """Turns a message key and its arguments into text in one language.

    A port rather than a call into the translation library, because the
    library is a presentation-shaped dependency and this runs in the worker.
    The adapter behind it ships its own ``.ftl`` files.

    Rendering is expected to fail loudly. A key with no translation, or a
    placeholder whose argument was forgotten, raises rather than producing a
    message with ``{ $number }`` in it — a customer reading that learns
    nothing, and nobody finds out.
    """

    @abstractmethod
    def render(self, text: NotificationText, locale: str) -> str:
        raise NotImplementedError
