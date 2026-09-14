"""Server-side paging, the way aiogram-dialog means it to be done.

The page is taken by the query, with ``limit`` and ``offset``, and the buttons
move it. What holds "which page" is aiogram-dialog's own ``StubScroll``: a
scroll widget with no visual of its own that keeps the current page in the
dialog's widget data, so ``PrevPage`` and ``NextPage`` move it exactly as they
move a ``ScrollingGroup``, and a getter reads it back through
``manager.find(...).get_page()``. ``ScrollingGroup`` itself is the wrong tool
here — it scrolls a list that has *already* been loaded, and the catalog must
not be pulled into memory to draw its first eight rows.

What is ours is the arithmetic, in :class:`Paging`: how a page number becomes an
offset, how a total becomes a page count, and whether there is anywhere to go.
Four screens ask those questions and four copies of "am I on the last page" is
four chances to be off by one.

The admin dialog keeps its own counter for now. Moving it over is a refactor of
code with no automated coverage, recorded as debt in ``docs/design/ordering.md``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common import ManagedScroll
from aiogram_dialog.widgets.kbd import NextPage, PrevPage, Row, StubScroll

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.widgets import I18NFormat

PAGES_KEY: Final[str] = "pages"
"""The getter key ``StubScroll`` reads the page count from."""

DEFAULT_PAGE_SIZE: Final[int] = 8
"""Rows per page, chosen for the screen rather than for the database.

Eight buttons is about what fits in a Telegram chat without the keyboard
pushing the message that explains it out of view, and it is what the admin list
already uses. A caller with shorter rows is free to ask for more.
"""

type WhenPredicate = Callable[[dict[str, Any], Any, DialogManager], bool]


@dataclass(frozen=True, slots=True)
class Paging:
    """Which page is being shown, out of how many.

    Built from the count the page query returned rather than from a second
    "how many are there" call: every paged read model in this project answers
    with its rows and its total together, precisely so the pager costs nothing.

    :attr:`number` counts from zero because that is what multiplies into an
    offset and what the scroll stores. What a person reads is
    :attr:`human_number`, and keeping the two apart is what stops an
    off-by-one from reaching either the SQL or the screen.
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

        ``pages`` is what the scroll reads its page count from; ``page`` and
        ``total`` are what the headings print. The names match the ones the
        admin list already produces, so a reader moving between the two
        dialogs does not have to learn a second set.
        """
        return {
            "page": self.human_number,
            PAGES_KEY: self.page_count,
            "total": self.total,
            "has_prev": self.has_previous,
            "has_next": self.has_next,
        }


async def current_page(manager: DialogManager, *, scroll_id: str) -> int:
    """Which page the scroll is on, defaulting to the first.

    The scroll is looked up across the whole dialog, so a callback on one
    window can read and reset the page of another — the category screen
    sends the listing back to its first page before switching to it.
    """
    scroll: ManagedScroll | None = manager.find(scroll_id)

    return 0 if scroll is None else await scroll.get_page()


async def page_request(
    manager: DialogManager,
    *,
    scroll_id: str,
    size: int = DEFAULT_PAGE_SIZE,
) -> tuple[int, int]:
    """The ``limit`` and ``offset`` to hand the query, in that order.

    Returned as a pair rather than as a :class:`Paging` because the total is
    not known until the query has answered — building the pager before the read
    would mean building it out of a number nobody has yet.
    """
    page = await current_page(manager, scroll_id=scroll_id)

    return size, page * size


async def paging_data(
    manager: DialogManager,
    *,
    scroll_id: str,
    total: int,
    size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """The window data for a pager, built from the count the query returned."""
    page = await current_page(manager, scroll_id=scroll_id)

    return Paging(number=page, size=size, total=total).as_data()


async def reset_paging(manager: DialogManager, *, scroll_id: str) -> None:
    """Sends the scroll back to the first page.

    Called whenever the thing being paged changes underneath the pager — a new
    search term, a different category, a status filter. Without it, searching
    for something with two matches while standing on page four shows an empty
    screen and looks like the search is broken.
    """
    scroll: ManagedScroll | None = manager.find(scroll_id)

    if scroll is not None:
        await scroll.set_page(0)


def _has_previous(data: dict[str, Any], _widget: Any, _manager: DialogManager) -> bool:
    """The pager hands its buttons ``current_page`` and ``pages`` beside the data."""
    current: int = data["current_page"]

    return current > 0


def _has_next(data: dict[str, Any], _widget: Any, _manager: DialogManager) -> bool:
    current: int = data["current_page"]
    pages: int = data["pages"]

    return current + 1 < pages


def paging_widgets(scroll_id: str) -> tuple[StubScroll, Row]:
    """The scroll that holds the page and the two buttons that move it.

    Both go into the window, the scroll first: it renders nothing, and it is
    what the buttons are bound to by ``scroll_id``. The buttons are hidden
    when they lead nowhere, which is the one thing aiogram-dialog's pager does
    not do by itself — it clamps the target page instead and shows the button
    all the same.

    ``scroll_id`` doubles as the prefix of the button ids, because widget ids
    have to be unique inside a window and a dialog that pages two lists would
    otherwise declare ``page_prev`` twice.
    """
    return (
        StubScroll(id=scroll_id, pages=PAGES_KEY),
        Row(
            PrevPage(
                scroll=scroll_id,
                id=f"{scroll_id}_prev",
                text=I18NFormat(text_keys.PAGING_PREV_BUTTON),
                when=_has_previous,
            ),
            NextPage(
                scroll=scroll_id,
                id=f"{scroll_id}_next",
                text=I18NFormat(text_keys.PAGING_NEXT_BUTTON),
                when=_has_next,
            ),
        ),
    )
