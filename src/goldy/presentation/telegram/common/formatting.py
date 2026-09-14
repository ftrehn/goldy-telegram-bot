"""How numbers, quantities, badges and order numbers are drawn.

Presentation, and specifically *Telegram* presentation, because every decision
here is about how a value looks on a screen rather than about what it means.
Nothing in this module knows a domain type: it takes the primitives a view
already carries, which is the same boundary ``MoneyView`` was flattened for.

It is a module rather than helpers inside each ``getters.py`` because five
dialogs print the same four things — a price, a quantity with its unit, a stock
badge and an order number — and five copies of a price formatter is five
chances for one screen to show ``1234.5`` while another shows ``1 234,50 ₽``.

Why a price is formatted here and not by Fluent's ``NUMBER()``: the currency
arrives as data. Fluent lets a function take only literal arguments, so the
currency of the amount being printed cannot be handed to it — the same
restriction that stops ``order-status`` from being a parameterised term. What
Fluent keeps is the wording around the number, which is what translation is
for; what Python keeps is the number itself.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from aiogram.utils.text_decorations import html_decoration
from aiogram_i18n import I18nContext

from goldy.application.common.views.money import MoneyView
from goldy.domain.common.values.currency import Currency
from goldy.domain.users.values.locale import DEFAULT_LOCALE
from goldy.presentation.telegram.common import text_keys

ENGLISH_LOCALE: Final[str] = "en"

MESSAGE_LIMIT: Final[int] = 4096
"""How much text Telegram lets one message carry.

A photo caption gets a quarter of this, which is why the product card keeps a
budget of its own.
"""

MAX_PLACEABLE_LENGTH: Final[int] = 2500
"""How long one ``{ $variable }`` may be before Fluent refuses the message.

``fluent.runtime`` caps the value substituted into a single placeable — its
``resolver.MAX_PART_LENGTH``, a guard against a pattern that expands without
bound — and going over does not truncate anything. ``format_pattern`` returns
an error, ``FluentRuntimeCore.get`` turns that into ``FluentMessageError``, and
the screen does not render at all.

It bites well below Telegram's own limit and therefore has to be applied
*first*: an order card whose lines are joined into one argument, or a
description pasted into another, both reach this ceiling with room to spare
under 4096. The error message the library prints names the wrong constant —
it reports the part *count* — which is why the number is written here rather
than read off a failure.
"""

YES: Final[str] = "yes"
NO: Final[str] = "no"
"""The two words a Fluent selector over a boolean branches on.

Fluent has no booleans and no null, so a flag reaches a message as a variant
key. Naming the two here keeps the ``.ftl`` variants and the getters that feed
them spelled the same way, which a stray ``"true"`` would quietly break — the
default branch would take over and the screen would simply be wrong.
"""

NARROW_NO_BREAK_SPACE: Final[str] = "\u202f"
"""What groups thousands in Russian, and never wraps mid-number.

Written as an escape rather than typed: a narrow no-break space and an
ordinary one are indistinguishable in an editor, and only one of them keeps
``1 234,50`` on a single line of a chat bubble.
"""


@dataclass(frozen=True, slots=True)
class NumberStyle:
    """Which separators a language writes numbers with."""

    group: str
    decimal: str

    def apply(self, amount: Decimal) -> str:
        """Draws the number itself, always with two decimal places.

        Python groups with ``,`` and points with ``.``; this swaps both in one
        pass by splitting the two halves apart rather than by running two
        replacements over the whole string. Sequential replacement only looks
        equivalent: a language that groups thousands with ``.`` — several do —
        would have its own separator rewritten by the second pass, turning
        ``1.234,50`` into ``1,234,50``. Splitting cannot do that, because the
        separators are never in the same half.

        Two decimals always, because a price with its trailing zero cut off
        reads as an approximation, and a shop whose display rounds its prices
        is a shop somebody argues with a manager about.
        """
        integer, _, fraction = f"{amount:,.2f}".partition(".")

        return f"{integer.replace(',', self.group)}{self.decimal}{fraction}"


NUMBER_STYLES: Final[Mapping[str, NumberStyle]] = {
    DEFAULT_LOCALE: NumberStyle(group=NARROW_NO_BREAK_SPACE, decimal=","),
    ENGLISH_LOCALE: NumberStyle(group=",", decimal="."),
}

DATE_FORMATS: Final[Mapping[str, str]] = {
    DEFAULT_LOCALE: "%d.%m.%Y %H:%M",
    ENGLISH_LOCALE: "%Y-%m-%d %H:%M",
}

CURRENCY_SIGNS: Final[Mapping[str, str]] = {
    Currency.RUB.value: "₽",
    Currency.USD.value: "$",
    Currency.EUR.value: "€",
}
"""Signs for the currencies we know, keyed by the value a view carries.

A currency with no sign here falls back to its code in capitals rather than to
a guess. The catalog import already refuses price types in currencies this
service does not know, so the fallback covers a currency added to the enum and
not yet to this table — visibly odd, which is the point.
"""


def for_message_text(value: str) -> str:
    """Text nobody in this project wrote, made safe to put inside a message.

    The bot sends everything with ``ParseMode.HTML``, so Telegram reads the
    text as markup. A product named ``Уголок <40x40>`` — an entirely ordinary
    name in 1C — is an unsupported start tag, and Telegram answers a malformed
    message by refusing the whole of it. The screen then does not arrive at
    all: not a card with odd punctuation, but no card, for that one product and
    for every cart and every order card that happens to contain it. The same
    goes for anything a person typed at us — a delivery address, a comment, a
    cancellation reason, their own name.

    Only what ends up *inside message text*. A button label is plain text to
    Telegram, with no parser behind it, so escaping one would show the customer
    ``&amp;`` where they wrote ``&``. That is why this is a call at each place a
    value enters a message rather than something applied to a whole getter's
    output: the cart line spells the same product name both ways at once, quoted
    for the row and bare for the button that opens it.

    Escaping makes the string longer than what Telegram counts towards a
    message limit, which is the harmless direction — every budget measured in
    this project then errs short. Fluent's own placeable ceiling is measured in
    Python characters, so there it is not an estimate but exact.
    """
    return html_decoration.quote(value)


def flag(*, value: bool) -> str:
    """Turns a boolean into the variant key a Fluent selector expects.

    Keyword-only because a boolean read positionally at a call site says
    nothing about which way round it goes, and this one is read at eight of
    them.
    """
    return YES if value else NO


def format_money(amount: MoneyView, locale: str = DEFAULT_LOCALE) -> str:
    """Draws an amount with its currency, in the reader's own conventions.

    An unknown locale is written the shop's own way rather than refused: a
    price is the one thing on the screen that must never be missing, and the
    worst a fallback can do here is group the thousands with the wrong space.
    """
    style = NUMBER_STYLES.get(locale, NUMBER_STYLES[DEFAULT_LOCALE])
    sign = CURRENCY_SIGNS.get(amount.currency, amount.currency.upper())

    return f"{style.apply(amount.amount)} {sign}"


def format_price(i18n: I18nContext, amount: MoneyView | None) -> str:
    """Draws a price, or says there is none to draw.

    A product with no row under this customer's price type is an ordinary state
    of the catalog rather than a defect, so the absence gets words instead of a
    zero: ``0 ₽`` reads as "free", which is worse than an error because nobody
    questions it.
    """
    if amount is None:
        return i18n.get(text_keys.PRICE_ON_REQUEST)

    return format_money(amount, i18n.locale)


def format_quantity(quantity: int, unit_name: str | None = None) -> str:
    """Draws a quantity with the unit it is counted in.

    The unit travels with the quantity everywhere it is shown, because "2" on
    its own tells a buyer nothing — two pieces, two metres and two packs are
    three different orders. It comes out of 1C already worded, so there is
    nothing here to translate.
    """
    if unit_name is None:
        return str(quantity)

    return f"{quantity} {unit_name}"


def format_stock(
    i18n: I18nContext,
    stock: Decimal | None,
    unit_name: str | None = None,
) -> str:
    """Draws the stock badge: how many are on the shelf, or "made to order".

    Never used to hide or refuse anything. Stock here is a projection of 1C
    with no reservation behind it, so a product at zero is one the shop brings
    in to order — and saying so sells it, while hiding the button does not.
    """
    in_stock = stock is not None and stock > 0

    return i18n.get(
        text_keys.STOCK_BADGE,
        in_stock=flag(value=in_stock),
        stock=format_stock_amount(stock),
        unit=unit_name or "",
    )


def format_stock_amount(stock: Decimal | None) -> str:
    """Just the number off the shelf, without the zeros a projection carries.

    Public, and public for one caller: the product card embeds ``stock-badge``
    inside ``catalog-card``, and an embedded Fluent message reads the arguments
    of the message that referenced it — so the card owes ``$stock`` the raw
    number and cannot hand over the badge :func:`format_stock` builds. Without
    this, the card copies the five lines below, and a shop that prints
    ``12.000 шт`` on one screen and ``12 шт`` on another has two of them.

    Stock is a ``Decimal`` because goods are sold by the metre as well as by
    the piece, so the ordinary case arrives as ``12.000`` where the fact is
    ``12``. Nothing at all is drawn for a product the projection has no stock
    row for: the badge's other branch is what speaks for that case.
    """
    if stock is None:
        return ""

    normalized = stock.normalize()

    if normalized == normalized.to_integral_value():
        return str(normalized.quantize(Decimal(1)))

    return str(normalized)


def format_order_number(i18n: I18nContext, number: str) -> str:
    """Draws an order number the way the language writes one.

    The number itself is untouched. Zero padding, prefixes and monthly resets
    would all live here if they were ever wanted, which is exactly why the
    domain knows nothing about them.
    """
    return i18n.get(text_keys.ORDER_NUMBER, number=number)


def format_order_date(moment: datetime, locale: str = DEFAULT_LOCALE) -> str:
    """Draws when an order was placed, to the minute.

    Seconds are dropped: nobody reads them, and they make a list column wider
    than the numbers beside it. The moment is printed in the zone it is stored
    in, which today is UTC — the shop has no timezone setting, and inventing
    one here would put this display three hours away from every other process
    that prints a timestamp.
    """
    template = DATE_FORMATS.get(locale, DATE_FORMATS[DEFAULT_LOCALE])

    return moment.strftime(template)


def format_order_status(i18n: I18nContext, status: str) -> str:
    """Looks a status up in the one dictionary there is.

    A status this bot has never heard of prints as itself, because the
    dictionary's default branch says so. That is deliberate over falling back
    to "new": a wrong status is a lie, an unfamiliar one is only ugly.
    """
    return i18n.get(text_keys.ORDER_STATUS, status=status)
