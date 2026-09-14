"""The arithmetic four dialogs share, which is where an off-by-one would live.

Nothing here touches a ``DialogManager``: reading a page number out of
``dialog_data`` and writing it back is three lines with no decision in them,
while "is there a next page" is the one question every list screen asks and the
only one that can be wrong.
"""

from goldy.presentation.telegram.common.paging import DEFAULT_PAGE_SIZE, Paging


def test_the_first_page_starts_at_no_offset() -> None:
    paging = Paging(number=0, size=DEFAULT_PAGE_SIZE, total=100)

    assert (paging.limit, paging.offset) == (DEFAULT_PAGE_SIZE, 0)


def test_a_later_page_offsets_by_whole_pages() -> None:
    paging = Paging(number=3, size=10, total=100)

    assert paging.offset == 30


def test_the_page_a_person_reads_counts_from_one() -> None:
    paging = Paging(number=0, size=10, total=100)

    assert paging.human_number == 1


def test_a_partial_last_page_still_counts() -> None:
    paging = Paging(number=0, size=10, total=21)

    assert paging.page_count == 3


def test_an_empty_list_is_page_one_of_one() -> None:
    """An empty catalog would otherwise be headed "page 1 of 0"."""
    paging = Paging(number=0, size=10, total=0)

    assert (paging.human_number, paging.page_count) == (1, 1)


def test_the_first_page_offers_no_way_back() -> None:
    paging = Paging(number=0, size=10, total=100)

    assert not paging.has_previous


def test_the_last_page_offers_no_way_on() -> None:
    paging = Paging(number=2, size=10, total=21)

    assert not paging.has_next


def test_a_full_last_page_is_still_the_last() -> None:
    """The boundary the buttons get wrong: twenty rows over two pages of ten."""
    paging = Paging(number=1, size=10, total=20)

    assert not paging.has_next


def test_a_page_in_the_middle_moves_both_ways() -> None:
    paging = Paging(number=1, size=10, total=100)

    assert (paging.has_previous, paging.has_next) == (True, True)


def test_the_window_data_names_what_the_messages_interpolate() -> None:
    paging = Paging(number=1, size=10, total=21)

    assert paging.as_data() == {
        "page": 2,
        "pages": 3,
        "total": 21,
        "has_prev": True,
        "has_next": True,
    }
