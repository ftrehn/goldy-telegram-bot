"""What a product card is built out of, without a dialog to build it in.

Three things here can fail in a way nothing else catches. A missing argument
makes Fluent raise rather than leave a placeholder, so the screen does not
render at all; an over-long caption makes Telegram refuse the whole message,
so the card does not arrive; and an unescaped ``<`` in a name out of 1C makes
Telegram refuse it as a malformed tag. All three are invisible until somebody
opens that one product.
"""

from dataclasses import replace
from typing import Any

from aiogram_i18n import I18nContext
from aiogram_i18n.cores import BaseCore

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.handlers.catalog.getters import (
    CAPTION_LIMIT,
    card_arguments,
    card_excerpt,
    description_budget,
    listing_row,
    shorten,
)
from tests.unit.factories.catalog_factories import (
    make_product_list_item,
    make_product_view,
)

ENGLISH_LOCALE = "en"


def test_a_card_renders_with_every_argument_the_message_needs(
    russian: I18nContext,
) -> None:
    """The card embeds two more messages, and both read the caller's arguments.

    A forgotten one raises ``FluentMessageError`` instead of printing itself,
    which is a product nobody can open rather than a card with an odd word in
    it.
    """
    product = make_product_view()

    text = russian.get(
        text_keys.CATALOG_CARD,
        excerpt="",
        **card_arguments(russian, product),
    )

    assert product.name in text
    assert "SKU-1" in text


def test_the_english_card_asks_for_exactly_the_same_arguments(
    i18n_core: BaseCore[Any],
    russian: I18nContext,
) -> None:
    """One getter feeds both languages, so both must want the same set."""
    card = card_arguments(russian, make_product_view())

    text = i18n_core.get(text_keys.CATALOG_CARD, ENGLISH_LOCALE, excerpt="", **card)

    assert "Product 1" in text


def test_a_product_with_no_price_says_so_instead_of_showing_zero(
    russian: I18nContext,
) -> None:
    """``0 ₽`` reads as "free", which nobody questions and everybody acts on."""
    product = make_product_view(price=None)

    card = card_arguments(russian, product)

    assert card["price"] == russian.get(text_keys.PRICE_ON_REQUEST)
    assert card["has_price"] == "no"


def test_a_product_at_zero_stock_is_still_sold_to_order(
    russian: I18nContext,
) -> None:
    """The badge changes, the "add to cart" button does not go anywhere.

    Stock is a projection of 1C with no reservation behind it, so hiding the
    button at zero would block precisely the goods the shop brings in to order.
    """
    product = make_product_view(stock="0")

    card = card_arguments(russian, product)
    text = russian.get(text_keys.CATALOG_CARD, excerpt="", **card)

    assert card["in_stock"] == "no"
    assert "Под заказ" in text


def test_a_name_with_angle_brackets_cannot_break_the_card(
    russian: I18nContext,
) -> None:
    """``Уголок <40x40>`` is an ordinary name in 1C and a broken tag in HTML.

    Messages go out with HTML parse mode, and Telegram refuses the whole
    message rather than printing the brackets — so the card would simply never
    appear for that one product.
    """
    product = replace(make_product_view(), name="Уголок <40x40>")

    card = card_arguments(russian, product)

    assert card["name"] == "Уголок &lt;40x40&gt;"


def test_a_long_description_still_fits_a_photo_caption(
    russian: I18nContext,
) -> None:
    """Telegram does not trim a caption over 1024 — it refuses the message."""
    product = replace(make_product_view(), description="слово " * 900)

    card = card_arguments(russian, product)
    text = russian.get(
        text_keys.CATALOG_CARD,
        excerpt=card_excerpt(russian, product.description, card),
        **card,
    )

    assert len(text) <= CAPTION_LIMIT


def test_a_short_description_is_shown_whole(russian: I18nContext) -> None:
    product = replace(make_product_view(), description="Оцинкованный, с гайкой.")

    excerpt = card_excerpt(russian, product.description, card_arguments(russian, product))

    assert excerpt == "Оцинкованный, с гайкой."


def test_a_listing_row_leaves_its_label_unescaped(russian: I18nContext) -> None:
    """The row is a button label, and a button is plain text.

    Escaping it would not protect anything — nothing parses a button — and the
    customer would read ``&amp;`` in the middle of a product name.
    """
    product = replace(make_product_list_item(), name="Болт & гайка")

    label, product_id = listing_row(russian, product)

    assert "Болт & гайка" in label
    assert product_id == product.id


def test_a_listing_row_prices_what_has_a_price(russian: I18nContext) -> None:
    product = make_product_list_item()

    label, _ = listing_row(russian, product)

    assert "₽" in label


def test_text_that_fits_is_left_alone() -> None:
    assert shorten("Болт", 10) == "Болт"


def test_text_that_does_not_fit_is_cut_at_a_word() -> None:
    cut = shorten("Болт оцинкованный с гайкой", 12)

    assert cut == "Болт…"
    assert len(cut) <= 12


def test_no_room_at_all_means_no_excerpt() -> None:
    """A card whose name and price already fill the caption still renders."""
    assert not shorten("Болт оцинкованный", 0)


def test_a_description_longer_than_a_placeable_still_renders(
    russian: I18nContext,
) -> None:
    """Fluent's own ceiling is the one that binds here, not Telegram's.

    ``fluent.runtime`` refuses a single ``{ $variable }`` over 2500 characters
    by failing the whole message rather than by shortening it, so a description
    of three thousand characters — the length this screen exists for — left the
    customer with nothing at all while still being comfortably under 4096.
    """
    description = "слово " * 600

    text = russian.get(
        text_keys.CATALOG_DESCRIPTION,
        name="Болт",
        description=shorten(description, description_budget(russian, "Болт")),
    )

    assert text.endswith("…")


def test_a_description_that_fits_is_not_cut(russian: I18nContext) -> None:
    description = "Оцинкованный, с гайкой."

    assert shorten(description, description_budget(russian, "Болт")) == description
