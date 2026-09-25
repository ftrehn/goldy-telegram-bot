from typing import Final

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_i18n import I18nContext
from dishka import FromDishka

from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.site import SiteFinanceSummaryView
from goldy.application.queries.site.get_site_finance_summary.query import (
    GetSiteFinanceSummaryQuery,
)
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import (
    for_message_text,
    format_money,
    format_order_date,
)
from goldy.presentation.telegram.common.keyboards import remove_keyboard
from goldy.presentation.telegram.filters.chat import ChatTypeFilter

router: Final[Router] = Router(name="site_finance")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message(Command("finance"))
async def handle_finance(
    message: Message,
    sender: FromDishka[Sender],
    i18n: I18nContext,
) -> None:
    """The company's balances in 1C, read through the site.

    The refusals — not linked, no right to see the money, the site down —
    are raised by the query and answered by the central error handler, like
    every other refusal in the bot.
    """
    summary = await sender.send(GetSiteFinanceSummaryQuery())

    await message.answer(render_finance(summary, i18n), reply_markup=remove_keyboard())


def render_finance(summary: SiteFinanceSummaryView, i18n: I18nContext) -> str:
    """The summary as lines, each drawn only when its figure is known.

    ``None`` is *unknown* and never a zero: a credit limit printed as ``0 ₽``
    would tell a customer they may not buy on credit, when 1C simply keeps no
    limit. The stale and partial warnings go first, because figures read
    without them read as the truth.
    """
    locale = i18n.locale
    company = for_message_text(summary.company_name or "—")
    lines = [i18n.get(text_keys.FINANCE_TITLE, company=company)]

    if summary.is_stale and summary.as_of is not None:
        lines.append(
            i18n.get(
                text_keys.FINANCE_STALE,
                as_of=format_order_date(summary.as_of, locale),
            ),
        )

    if summary.is_partial:
        lines.append(i18n.get(text_keys.FINANCE_PARTIAL))

    if not summary.erp_linked:
        lines.append(i18n.get(text_keys.FINANCE_NO_ERP))
        return "\n\n".join(lines)

    figures: list[str] = []

    if summary.debt is not None:
        figures.append(
            i18n.get(text_keys.FINANCE_DEBT, amount=format_money(summary.debt, locale)),
        )

    if summary.advance is not None and summary.advance.amount:
        figures.append(
            i18n.get(
                text_keys.FINANCE_ADVANCE,
                amount=format_money(summary.advance, locale),
            ),
        )

    if summary.overdue is not None and summary.overdue.amount:
        figures.append(
            i18n.get(
                text_keys.FINANCE_OVERDUE,
                amount=format_money(summary.overdue, locale),
                days=summary.max_days_overdue or 0,
            ),
        )

    if summary.credit_limit is not None and summary.credit_available is not None:
        figures.append(
            i18n.get(
                text_keys.FINANCE_CREDIT_LIMIT,
                limit=format_money(summary.credit_limit, locale),
                available=format_money(summary.credit_available, locale),
            ),
        )
    else:
        figures.append(i18n.get(text_keys.FINANCE_CREDIT_UNTRACKED))

    lines.extend(("\n".join(figures), i18n.get(text_keys.FINANCE_FOOTER)))

    return "\n\n".join(lines)
