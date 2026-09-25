"""``normalize_link_code`` refuses before any request is sent.

A code that cannot be the site's is worth catching here: the site would say
"unknown code" anyway, and a request per typo counts against every other
customer's rate limit on the site.
"""

import pytest

from goldy.application.common.services.site_link_code import normalize_link_code
from goldy.application.error import SiteLinkCodeInvalidError

VALID_CODE: str = "abcdefghijklmnopqrst"


def test_a_wellformed_code_is_returned_unchanged() -> None:
    assert normalize_link_code(VALID_CODE) == VALID_CODE


def test_the_code_is_lowercased() -> None:
    assert normalize_link_code(VALID_CODE.upper()) == VALID_CODE


def test_surrounding_whitespace_is_stripped() -> None:
    assert normalize_link_code(f"  {VALID_CODE}\n") == VALID_CODE


def test_an_empty_string_is_refused() -> None:
    with pytest.raises(SiteLinkCodeInvalidError):
        normalize_link_code("")


@pytest.mark.parametrize(
    "raw",
    (
        "a" * 19,
        "a" * 21,
        "01234567890123456789",
        "abcdefghijklmnopqrs8",
        "abcdefghijklmnopqrs1",
        "not a link code at all",
    ),
)
def test_text_that_is_not_the_sites_code_is_refused(raw: str) -> None:
    with pytest.raises(SiteLinkCodeInvalidError):
        normalize_link_code(raw)
