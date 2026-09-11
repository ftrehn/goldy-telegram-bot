"""Whether text the shop did not write can still be put into a message.

The bot sends everything with ``ParseMode.HTML``, which makes every ``<`` in a
product name, a delivery address, a comment or a person's own name a piece of
markup as far as Telegram is concerned. ``Уголок <40x40>`` is an ordinary name
in 1C and an unsupported start tag in the Bot API, and the API answers a
malformed message by refusing all of it — so the failure is not an odd-looking
card, it is no card, for that product and for every cart and every order card
that contains it. Nothing else in this suite would notice: the text renders
perfectly well in Python, and the refusal happens at the far end.

Each screen is checked in the pure function that builds its arguments, which is
where the decision is made. Where one value goes into a message and onto a
button at once, both halves are checked together: quoting a button label would
show the customer ``&amp;`` where they wrote ``&``.
"""

from dataclasses import replace
from typing import Any, Final

from aiogram_i18n import I18nContext
from aiogram_i18n.cores import BaseCore

from goldy.application.common.views.order import OrderView
from goldy.application.common.views.user import MessengerAccountView, UserView
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import for_message_text
from goldy.presentation.telegram.common.order_cards import (
    format_order_lines,
    format_queue_lines,
    order_card_data,
)
from goldy.presentation.telegram.handlers.admin.getters import card_arguments
from goldy.presentation.telegram.handlers.cart.getters import line_arguments
from goldy.presentation.telegram.handlers.catalog.getters import (
    card_arguments as product_card_arguments,
)
from goldy.presentation.telegram.handlers.checkout.getters import (
    ADDRESS_KEY,
    COMMENT_KEY,
    FIRST_NAME_KEY,
    LAST_NAME_KEY,
    PHONE_KEY,
    typed_details,
)
from goldy.presentation.telegram.handlers.manage_orders.getters import customer_label
from goldy.presentation.telegram.handlers.profile.getters import profile_getter
from tests.unit.factories.cart_factories import make_cart_line_view
from tests.unit.factories.catalog_factories import make_product_view
from tests.unit.factories.domain_factories import CUSTOMER_PHONE, make_user_id
from tests.unit.factories.order_factories import (
    PLACED_AT,
    make_order_line_view,
    make_order_view,
)

ANGLED: Final[str] = "Уголок <40x40>"
"""A product name out of 1C, and a malformed tag to Telegram."""

QUOTED_ANGLED: Final[str] = "Уголок &lt;40x40&gt;"

TYPED_MARKUP: Final[str] = "дом 5 <b>кв 7</b>"
"""What somebody types when they have seen formatting work elsewhere."""


def _user(first_name: str = ANGLED, block_reason: str | None = None) -> UserView:
    """Somebody registered under whatever Telegram had them down as."""
    return UserView(
        id=make_user_id(),
        phone_number=CUSTOMER_PHONE,
        first_name=first_name,
        last_name=None,
        role=UserRole.CUSTOMER.value,
        status=(
            UserStatus.BLOCKED.value
            if block_reason is not None
            else UserStatus.ACTIVE.value
        ),
        block_reason=block_reason,
        notify_via="telegram",
        locale="ru",
        marketing_consent=False,
        accounts=(
            MessengerAccountView(
                platform="telegram",
                external_id="42",
                username=None,
                linked_at=PLACED_AT,
            ),
        ),
        created_at=PLACED_AT,
        updated_at=PLACED_AT,
    )


def _order_with_typing() -> OrderView:
    """An order whose every free-text field carries markup."""
    return replace(
        make_order_view(lines=(make_order_line_view(),)),
        delivery_address=TYPED_MARKUP,
        recipient_first_name=ANGLED,
        recipient_last_name=None,
        comment=TYPED_MARKUP,
        cancelled_by=ANGLED,
        cancellation_reason=TYPED_MARKUP,
    )


def test_it_quotes_what_the_html_parser_would_otherwise_eat() -> None:
    """The helper itself, so the rest of this file rests on one answer."""
    assert for_message_text(ANGLED) == QUOTED_ANGLED
    assert for_message_text("Болт & гайка") == "Болт &amp; гайка"


def test_a_cart_row_is_quoted_and_the_button_beside_it_is_not(
    russian: I18nContext,
) -> None:
    """The same name twice, and only one of the two parsed as markup.

    A button label is plain text to Telegram, so quoting it would put ``&lt;``
    in front of the customer — while leaving the row unquoted loses the whole
    cart screen rather than one line of it.
    """
    arguments = line_arguments(
        russian,
        1,
        replace(make_cart_line_view(), name=ANGLED),
    )

    assert arguments["name"] == QUOTED_ANGLED
    assert ANGLED in arguments["label"]


def test_an_order_card_quotes_every_field_a_person_typed(
    russian: I18nContext,
) -> None:
    """Address, recipient, comment, and who cancelled it and why.

    The last two are typed by staff rather than by the customer, which makes
    them differently sourced rather than safer.
    """
    card = order_card_data(russian, _order_with_typing(), lines="")

    assert "<" not in card["address"]
    assert "<" not in card["recipient"]
    assert "<" not in card["comment"]
    assert "<" not in card["cancelled_by"]
    assert "<" not in card["reason"]


def test_both_kinds_of_order_line_quote_the_product_name(
    russian: I18nContext,
) -> None:
    """The buyer's line and the queue's line share their arguments.

    Quoting one and not the other would leave the manager unable to open the
    very order the customer can see.
    """
    angled = replace(make_order_line_view(), name=ANGLED)

    assert QUOTED_ANGLED in format_order_lines(russian, (angled,))
    assert QUOTED_ANGLED in format_queue_lines(russian, (angled,))


def test_the_confirmation_quotes_what_was_typed_into_it() -> None:
    """The screen that reads four screens of typing back to the person.

    An address with a ``<`` in it makes this window unsendable, and the order
    can then never be placed at all: the confirm button is on the screen that
    does not arrive.
    """
    details = typed_details(
        {
            ADDRESS_KEY: TYPED_MARKUP,
            FIRST_NAME_KEY: ANGLED,
            LAST_NAME_KEY: None,
            PHONE_KEY: CUSTOMER_PHONE,
            COMMENT_KEY: TYPED_MARKUP,
        },
    )

    assert "<" not in details["address"]
    assert details["recipient"] == QUOTED_ANGLED
    assert "<" not in details["comment"]
    assert details["phone"] == CUSTOMER_PHONE


def test_the_staff_card_quotes_the_customer_it_names() -> None:
    """A name out of the buyer's own registration, printed for a manager."""
    assert customer_label(_user()) == f"{QUOTED_ANGLED} · {CUSTOMER_PHONE}"


def test_the_admin_card_quotes_the_name_and_the_block_reason() -> None:
    """Both of its free-text fields, one of them written by a manager."""
    arguments = card_arguments(_user(block_reason=TYPED_MARKUP))

    assert QUOTED_ANGLED in arguments["name"]
    assert "<" not in arguments["reason"]


async def test_a_person_sees_their_own_name_quoted_on_their_profile() -> None:
    """``FullName`` caps the length of a name and restricts nothing else.

    The first name is taken from Telegram at registration, where it is whatever
    its owner typed — so ``/me`` is breakable by anybody who cares to.
    """
    profile = await profile_getter(user=_user())

    assert profile["name"] == QUOTED_ANGLED


def test_a_product_card_quotes_the_name_the_listing_leaves_alone(
    russian: I18nContext,
) -> None:
    """The catalog made this decision first; it is asserted here as one rule.

    The card's name goes inside a caption and the listing row's goes onto a
    button, so the two have to differ — and a rule that holds in four dialogs
    and not the fifth is not a rule.
    """
    arguments = product_card_arguments(russian, replace(make_product_view(), name=ANGLED))

    assert arguments["name"] == QUOTED_ANGLED


def test_an_order_card_renders_a_name_telegram_would_have_refused(
    i18n_core: BaseCore[Any],
    russian: I18nContext,
) -> None:
    """End to end over the real ``.ftl``: no bare tag survives into the text.

    The assertions above cover the arguments one at a time; this one covers the
    sentence they end up in, because a card is only sendable if every part of
    it is. What it may not assert is the absence of ``<``: the card's own
    wording is written with ``<b>`` in the ``.ftl``, and that markup is ours
    and intended. What must not survive is the markup that arrived as data.
    """
    card = order_card_data(russian, _order_with_typing(), lines="")
    card["lines"] = format_order_lines(
        russian,
        (replace(make_order_line_view(), name=ANGLED),),
    )
    rendered = i18n_core.get(
        text_keys.ORDER_CARD,
        "ru",
        **{name: value for name, value in card.items() if isinstance(value, str)},
    )

    assert TYPED_MARKUP not in rendered
    assert QUOTED_ANGLED in rendered
    assert "&lt;b&gt;" in rendered
