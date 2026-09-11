"""What a cart line is drawn from, without a dialog to draw it in.

Two things here fail in a way nothing else catches. A line message short of one
argument does not render as a stray placeholder — the Fluent core raises on an
unknown external, so the whole cart screen fails to draw. And a mark that is
chosen wrongly tells a customer that a product they can still buy has left the
catalog, or the reverse, which is the one thing this screen exists to say.
"""

from dataclasses import replace

from aiogram_i18n import I18nContext

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.handlers.cart.getters import (
    MAX_LABEL_LENGTH,
    has_fallen_off,
    line_arguments,
    line_label,
    line_mark,
    line_name,
)
from tests.unit.factories.cart_factories import make_cart_line_view

LONG_NAME = "Болт оцинкованный с шестигранной головкой ГОСТ 7798-70"


def test_a_line_renders_with_every_argument_its_message_needs(
    russian: I18nContext,
) -> None:
    """A forgotten argument raises instead of printing itself.

    Which makes it a screen that does not appear at all, rather than a screen
    with an odd word on it — so the getter owes the message every name it uses.
    """
    line = make_cart_line_view(quantity=3, stock="12")

    text = russian.get(text_keys.CART_LINE, **line_arguments(russian, 1, line))

    assert "Product 1" in text


def test_a_line_that_left_the_catalog_is_marked_and_not_badged(
    russian: I18nContext,
) -> None:
    """The two never appear together.

    A product the catalog no longer holds has no stock worth printing, and
    "made to order" next to "gone from the catalog" reads as an offer to order
    the very thing that cannot be ordered.
    """
    line = make_cart_line_view(stock="12", is_available=False)

    assert line_mark(russian, line) == "⚠ нет в каталоге"


def test_a_line_still_on_sale_shows_what_is_on_the_shelf(
    russian: I18nContext,
) -> None:
    line = make_cart_line_view(stock="12")

    assert line_mark(russian, line) == "В наличии: 12 шт"


def test_a_product_with_nothing_in_stock_is_still_offered_to_order(
    russian: I18nContext,
) -> None:
    """Stock never hides anything here — the shop brings such goods in."""
    line = make_cart_line_view(stock=None)

    assert line_mark(russian, line) == "Под заказ"


def test_an_unpriced_line_is_not_marked_as_gone(russian: I18nContext) -> None:
    """It is still in the catalog; what it lacks is a price for this customer.

    Marking it would make the mark and the "remove unavailable" button disagree
    about which lines they mean, and the button would leave behind a line the
    screen had just called broken.
    """
    line = make_cart_line_view(price=None, stock="12")

    assert line_mark(russian, line) == "В наличии: 12 шт"


def test_a_short_name_keeps_all_of_itself() -> None:
    assert line_label(2, "Болт М8") == "2. Болт М8"


def test_a_name_too_long_for_a_button_is_cut() -> None:
    """A label out of 1C wraps over three lines and turns a list into a wall."""
    label = line_label(1, LONG_NAME)

    assert label.endswith("…")
    assert len(label.removeprefix("1. ")) <= MAX_LABEL_LENGTH


def test_a_product_whose_catalog_row_is_gone_is_named_by_its_article() -> None:
    """The article is what the customer ordered by and a manager can look up."""
    line = replace(make_cart_line_view(), name=None)

    assert line_name(line) == "SKU-1"


def test_a_line_with_neither_name_nor_article_is_named_by_its_reference() -> None:
    """Ugly on purpose: an unreadable line invites removing it."""
    line = replace(make_cart_line_view(), name=None, sku=None)

    assert line_name(line) == line.product_id


def test_an_emptied_cart_is_not_left_standing_on_page_four() -> None:
    """The case the clamp exists for, and the one a row count excludes.

    "Clear the cart" takes away every page, so a guard that only fires while
    rows remain fires for every page but the ones that have all gone — and the
    person is left reading "your cart is empty" with a "previous" button under
    it, which looks like the cart was lost rather than emptied.
    """
    assert has_fallen_off(offset=24, total=0)


def test_a_page_past_the_last_row_is_a_page_that_went() -> None:
    assert has_fallen_off(offset=8, total=8)


def test_a_page_with_rows_on_it_stays_put() -> None:
    assert not has_fallen_off(offset=8, total=9)


def test_the_first_page_has_nowhere_to_fall_back_to() -> None:
    assert not has_fallen_off(offset=0, total=0)
