"""Reading a built dialog the way aiogram-dialog reads it, with no bot involved.

Everything here walks the widget tree rather than taking a list of widgets,
because a list has to be kept in step with seven ``dialogs.py`` by hand and a
forgotten line looks exactly like a passing test. The lookups raise instead of
answering ``None`` for the same reason: a test that silently found nothing is
a test that passes for the wrong reason.

Support code rather than fixtures, following ``tests/unit/support.py`` — none
of it is state a test needs set up, all of it is a question a test asks of a
dialog that was built at import time.
"""

from collections.abc import Iterator
from typing import Final
from unittest.mock import MagicMock

from aiogram.fsm.state import State
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.common import Whenable

from goldy.presentation.telegram.common.widgets import I18NFormat

NO_MANAGER: Final[DialogManager] = MagicMock()
"""Stands in for the manager a visibility condition never looks at.

``Whenable`` turns ``when="is_priced"`` into a predicate taking the window
data, the widget and the manager, and the two predicates aiogram-dialog builds
— one for a field name, one for a magic filter — read the data and nothing
else. A manager here would therefore be furniture, and the real one cannot be
built without a bot, a storage and an update.

The only object in this test suite that is not hand-written, and it is never
configured and never asserted against: it exists to satisfy a signature.
"""


def walk(node: object, seen: set[int] | None = None) -> Iterator[object]:
    """Everything reachable from a built dialog, each object exactly once."""
    seen = set() if seen is None else seen

    if id(node) in seen:
        return

    seen.add(id(node))
    yield node

    if isinstance(node, list | tuple | set | frozenset):
        for item in node:
            yield from walk(item, seen)
        return

    if isinstance(node, dict):
        for value in node.values():
            yield from walk(value, seen)
        return

    attributes = getattr(node, "__dict__", None)

    if isinstance(attributes, dict):
        for value in attributes.values():
            yield from walk(value, seen)


def texts_of(node: object) -> Iterator[I18NFormat]:
    """Every translated text a widget tree holds."""
    for widget in walk(node):
        if isinstance(widget, I18NFormat):
            yield widget


def window_of(dialog: Dialog, state: State) -> Window:
    """The one screen of a dialog that stands in the given state.

    aiogram-dialog keys its windows by state, which is how it picks the screen
    to draw; this asks it the same question a render does — and a state the
    dialog does not own raises the ``KeyError`` that lookup produces.
    """
    window = dialog.windows[state]

    if isinstance(window, Window):
        return window

    raise TypeError(state)


def widget_of(node: object, widget_id: str) -> Whenable:
    """The widget declared under that id, wherever it sits in the tree.

    Raises rather than answering ``None``: every caller asks about a widget it
    believes is there, and a renamed id would otherwise turn an assertion about
    a button into an assertion about nothing.
    """
    for widget in walk(node):
        if isinstance(widget, Whenable) and getattr(widget, "widget_id", None) == (
            widget_id
        ):
            return widget

    raise LookupError(widget_id)


def is_shown(widget: Whenable, data: dict[str, object]) -> bool:
    """Whether that widget is drawn for a screen holding this data.

    Asks the widget's own condition rather than reading the ``when=`` written
    in ``dialogs.py``, so what is under test is the decision the dialog will
    actually take at render time.
    """
    return bool(widget.is_(data, NO_MANAGER))
