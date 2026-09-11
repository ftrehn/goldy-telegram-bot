"""Server-side paging, shared by every dialog that shows a list.

The page is taken by the query, with ``limit`` and ``offset``, and the buttons
move the offset. ``ScrollingGroup`` is the alternative and it is the wrong one:
it scrolls a list that has *already* been loaded, so using it for the catalog
would mean pulling every product into the dialog's memory before drawing the
first twenty. The docstring of the admin list getter already says this; the
catalog is the case it was written about.

One helper rather than one counter per dialog, because four screens — the
catalog listing, the search results, the customer's orders and the staff queue
— need exactly the same arithmetic, and four copies of "am I on the last page"
is four chances to be off by one.

The admin dialog deliberately keeps its own copy. Moving it over would not be
an additive change but a refactor of code with no automated coverage, in an
area this task does not otherwise touch; the duplication is recorded as debt in
``docs/design/ordering.md`` rather than paid for by a risk nobody asked for.
"""

from dataclasses import dataclass
from typing import Any, Final

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Row
from aiogram_dialog.widgets.kbd.button import OnClick

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.widgets import I18NFormat

PAGE_KEY: Final[str] = "page"
"""Where the current page lives in ``dialog_data``.

A dialog with two paged screens — the catalog has one for a listing and one for
search results — passes a key of its own to each, so that leaving a listing on
page four does not open the search results there too.
"""

DEFAULT_PAGE_SIZE: Final[int] = 8
"""Rows per page, chosen for the screen rather than for the database.

Eight buttons is about what fits in a Telegram chat without the keyboard
pushing the message that explains it out of view, and it is what the admin list
already uses. A caller with shorter rows is free to ask for more.
"""


@dataclass(frozen=True, slots=True)
class Paging:
    """Which page is being shown, out of how many.

    Built from the count the page query returned rather than from a second
    "how many are there" call: every paged read model in this project answers
    with its rows and its total together, precisely so the pager costs nothing.

    :attr:`number` counts from zero because that is what multiplies into an
    offset. What a person reads is :attr:`human_number`, and keeping the two
    apart is what stops an off-by-one from reaching either the SQL or the
    screen.
    """

    number: int
    size: int
    total: int

    @property
    def limit(self) -> int:
        return self.size

    @property
    def offset(self) -> int:
        return self.number * self.size

    @property
    def page_count(self) -> int:
        """At least one, so an empty list reads "page 1 of 1" and not "of 0"."""
        return max(1, -(-self.total // self.size))

    @property
    def human_number(self) -> int:
        return self.number + 1

    @property
    def has_previous(self) -> bool:
        return self.number > 0

    @property
    def has_next(self) -> bool:
        return self.offset + self.size < self.total

    def as_data(self) -> dict[str, Any]:
        """What a getter merges into its window data.

        The names match the ones the admin list already produces, so a reader
        moving between the two dialogs does not have to learn a second set.
        """
        return {
            "page": self.human_number,
            "pages": self.page_count,
            "total": self.total,
            "has_prev": self.has_previous,
            "has_next": self.has_next,
        }


def current_page(manager: DialogManager, *, key: str = PAGE_KEY) -> int:
    """Which page the dialog is on, defaulting to the first."""
    page: int = manager.dialog_data.get(key, 0)

    return page


def page_request(
    manager: DialogManager,
    *,
    size: int = DEFAULT_PAGE_SIZE,
    key: str = PAGE_KEY,
) -> tuple[int, int]:
    """The ``limit`` and ``offset`` to hand the query, in that order.

    Returned as a pair rather than as a :class:`Paging` because the total is
    not known until the query has answered — building the pager before the read
    would mean building it out of a number nobody has yet.
    """
    page = current_page(manager, key=key)

    return size, page * size


def paging_data(
    manager: DialogManager,
    *,
    total: int,
    size: int = DEFAULT_PAGE_SIZE,
    key: str = PAGE_KEY,
) -> dict[str, Any]:
    """The window data for a pager, built from the count the query returned."""
    paging = Paging(number=current_page(manager, key=key), size=size, total=total)

    return paging.as_data()


def reset_paging(manager: DialogManager, *, key: str = PAGE_KEY) -> None:
    """Sends the dialog back to the first page.

    Called whenever the thing being paged changes underneath the pager — a new
    search term, a different category, a status filter. Without it, searching
    for something with two matches while standing on page four shows an empty
    screen and looks like the search is broken.
    """
    manager.dialog_data[key] = 0


def turn_page(manager: DialogManager, *, step: int, key: str = PAGE_KEY) -> None:
    """Moves by one page, never below the first.

    The upper bound is not enforced here and does not need to be: the "next"
    button is drawn only while ``has_next`` says there is one, and a page past
    the end would come back empty with "previous" still on it.
    """
    manager.dialog_data[key] = max(0, current_page(manager, key=key) + step)


def page_turner(*, step: int, key: str = PAGE_KEY) -> OnClick:
    """Builds the ``on_click`` for one pager button.

    A factory rather than two module-level callbacks, because the key is what
    varies: a dialog paging two different lists needs two pairs of buttons that
    move two different counters, and a closure is the smallest thing that
    carries one.
    """

    async def on_click(
        _callback: CallbackQuery,
        _button: Button,
        manager: DialogManager,
    ) -> None:
        turn_page(manager, step=step, key=key)

    return on_click


def paging_row(*, key: str = PAGE_KEY, id_prefix: str = PAGE_KEY) -> Row:
    """The two buttons, wired to the counter and hidden when they lead nowhere.

    ``id_prefix`` exists because widget ids have to be unique inside a window,
    and a dialog that pages two lists would otherwise declare ``page_prev``
    twice.
    """
    return Row(
        Button(
            I18NFormat(text_keys.PAGING_PREV_BUTTON),
            id=f"{id_prefix}_prev",
            on_click=page_turner(step=-1, key=key),
            when="has_prev",
        ),
        Button(
            I18NFormat(text_keys.PAGING_NEXT_BUTTON),
            id=f"{id_prefix}_next",
            on_click=page_turner(step=1, key=key),
            when="has_next",
        ),
    )
