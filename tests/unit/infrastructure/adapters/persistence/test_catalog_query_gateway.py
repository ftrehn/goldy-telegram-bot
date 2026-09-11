"""The text handling the storefront queries do before any SQL is built.

The statements themselves belong to the integration suite — compiling one and
reading the string back would be a test of SQLAlchemy. What is ours, and what
is a real way to select the wrong rows, is the escaping: identifiers come from
1C and may contain the characters ``LIKE`` reads as wildcards.
"""

from goldy.infrastructure.adapters.persistence import (
    sqlalchemy_catalog_query_gateway as query_gateway,
)

LIKE_ESCAPE = query_gateway.LIKE_ESCAPE
MIN_TRIGRAM_LENGTH = query_gateway.MIN_TRIGRAM_LENGTH
_escape_like = query_gateway._escape_like


def test_ordinary_text_is_left_exactly_as_it_was_typed() -> None:
    assert _escape_like("1c-category-1") == "1c-category-1"


def test_a_percent_sign_in_an_identifier_stops_being_a_wildcard() -> None:
    """Unescaped, a group whose path holds one would list a different subtree."""
    assert _escape_like("50%") == f"50{LIKE_ESCAPE}%"


def test_an_underscore_stops_matching_any_single_character() -> None:
    """The quieter of the two: it matches one character and looks like data."""
    assert _escape_like("AB_12") == f"AB{LIKE_ESCAPE}_12"


def test_a_backslash_is_doubled_before_anything_else_is_escaped() -> None:
    """Order matters, and getting it wrong is invisible in the result.

    Escaping the wildcards first and the backslash afterwards would double the
    backslash this function had just written, turning an escaped wildcard back
    into a live one.
    """
    escaped = _escape_like(f"a{LIKE_ESCAPE}%b")

    assert escaped == f"a{LIKE_ESCAPE * 2}{LIKE_ESCAPE}%b"


def _bound_patterns(sku_term: str, name_term: str) -> set[str]:
    """The ``LIKE`` patterns a match condition would actually send.

    Read off the bound parameters rather than off the SQL text: what is being
    asserted is which pattern we chose, not how SQLAlchemy renders an ``OR``.
    """
    compiled = query_gateway._search_match(sku_term, name_term).compile()

    return {
        value
        for value in compiled.params.values()
        if isinstance(value, str) and "%" in value
    }


def test_a_term_too_short_for_a_trigram_is_matched_as_a_prefix() -> None:
    """Two characters produce no trigram, so a substring match would scan.

    A sequential scan of the whole catalog on every keystroke is the cost, and
    somebody who typed two characters typed the start of something anyway.
    """
    patterns = _bound_patterns("AB", "ab")

    assert patterns == {"AB%", "ab%"}


def test_a_term_long_enough_for_a_trigram_is_matched_anywhere_in_an_article() -> None:
    """A fragment of an article is what the trigram index exists to find."""
    patterns = _bound_patterns("AB1", "ab1")

    assert patterns == {"%AB1%"}
    assert len("AB1") == MIN_TRIGRAM_LENGTH
