"""Linking the bot to a customer's account on the site (ADR-0004).

The site's cabinet hands out a one-time code as a deep link,
``t.me/<bot>?start=link_<code>``. The bot asks the site whose account the code
leads to, shows the person that masked identity and links only after they
press "yes". The confirmation step is the point, not ceremony: without it,
somebody who sent a victim a link carrying the attacker's own code would get
the victim's messenger bound to the attacker's account.
"""

import logging
from typing import Final

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram_i18n import I18nContext
from dishka import FromDishka

from goldy.application.commands.site.link_site_account.command import (
    LinkSiteAccountCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.services.site_link_code import normalize_link_code
from goldy.application.common.views.user import UserView
from goldy.application.queries.site.preview_site_link.query import (
    PreviewSiteLinkQuery,
)
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.keyboards import (
    remove_keyboard,
    share_phone_keyboard,
)
from goldy.presentation.telegram.filters.chat import ChatTypeFilter
from goldy.presentation.telegram.handlers.site.identity import describe_site_customer

logger: Final[logging.Logger] = logging.getLogger(__name__)

LINK_PAYLOAD_PREFIX: Final[str] = "link_"
"""What the site puts in front of the code in ``LINK_URLS`` (``docs/API.md``)."""

PENDING_CODE_KEY: Final[str] = "site_link_code"
"""Where a code waits while its owner registers.

FSM data rather than a column: it lives only until the contact arrives, and a
code is dead after fifteen minutes anyway. A stranger's first message is the
deep link, and the gate refuses everything but registration until they share
a number — so the code has to survive exactly one round trip.
"""

router: Final[Router] = Router(name="site_link")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


class SiteLinkCallback(CallbackData, prefix="sitelink"):
    """The answer to "is this you?", with the code it answers about.

    The code rides in the button rather than in FSM state: the message can be
    answered a minute later, after the person has opened another dialog that
    reset the state, and the button still knows what it confirms. Twenty
    characters plus the prefix sit well inside Telegram's 64 bytes.
    """

    confirm: bool
    code: str


@router.message(
    CommandStart(deep_link=True, magic=F.args.startswith(LINK_PAYLOAD_PREFIX)),
)
async def handle_link_deep_link(
    message: Message,
    sender: FromDishka[Sender],
    state: FSMContext,
    i18n: I18nContext,
    user: UserView | None = None,
) -> None:
    """``/start link_<code>`` — the site's cabinet sent this person here.

    A registered person gets the preview straight away. An unknown one is asked
    for their number first, exactly as a bare ``/start`` would, and the code
    waits in FSM data for the contact handler to pick up.

    Registered before the generic ``/start`` handler, and it has to be:
    ``CommandStart()`` matches a deep link too, and would greet the person and
    drop the code.
    """
    code = link_code_of(message.text or "")

    if user is None:
        await state.update_data({PENDING_CODE_KEY: code})
        await message.answer(
            i18n.get(text_keys.AUTH_REGISTRATION_REQUIRED),
            reply_markup=share_phone_keyboard(
                i18n.get(text_keys.AUTH_SHARE_PHONE_BUTTON),
            ),
        )
        return

    await send_link_preview(message, code, sender, i18n)


def link_code_of(text: str) -> str:
    """The code out of ``/start link_<code>`` — or ``/start@bot link_<code>``.

    Read from the text rather than from ``CommandObject``: the filter has
    already decided this is a linking deep link, and one parameter fewer keeps
    the handler inside the project's argument budget.
    """
    _, _, payload = text.partition(" ")
    return payload.strip().removeprefix(LINK_PAYLOAD_PREFIX)


async def take_pending_code(state: FSMContext) -> str | None:
    """The code a newly registered person arrived with, removed from FSM data."""
    data = await state.get_data()
    code = data.get(PENDING_CODE_KEY)

    if not isinstance(code, str):
        return None

    await state.update_data({PENDING_CODE_KEY: None})
    return code


async def send_link_preview(
    message: Message,
    code: str,
    sender: Sender,
    i18n: I18nContext,
) -> None:
    """Asks the site whose account ``code`` leads to, and asks the person.

    The code is normalised here as well as in the handler, because it goes
    into the buttons: a deep link carries up to 64 characters of whatever the
    sender typed, and only a real code is short and plain enough for callback
    data.

    Raises:
        SiteLinkCodeInvalidError: not a code, or the site does not know it.
        SiteUnavailableError: the site did not answer.
    """
    code = normalize_link_code(code)
    preview = await sender.send(
        PreviewSiteLinkQuery(code=code, platform=MessengerPlatform.TELEGRAM),
    )
    who = describe_site_customer(
        preview.customer_name,
        email=preview.email,
        company=preview.company_name,
    )

    await message.answer(
        i18n.get(text_keys.SITE_LINK_PREVIEW, who=who),
        reply_markup=_confirmation_keyboard(code, i18n),
    )


@router.callback_query(SiteLinkCallback.filter())
async def handle_link_answer(
    callback: CallbackQuery,
    callback_data: SiteLinkCallback,
    sender: FromDishka[Sender],
    i18n: I18nContext,
) -> None:
    """Links on "yes", says so on "no", and takes the buttons away either way.

    The buttons go before anything else is said, so a second press on a slow
    connection finds nothing to press rather than spending the code twice and
    getting "the link has expired" for the first press's success.
    """
    await callback.answer()

    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)

    if not callback_data.confirm:
        await _reply(callback, i18n.get(text_keys.SITE_LINK_CANCELLED))
        return

    link = await sender.send(
        LinkSiteAccountCommand(
            code=callback_data.code,
            platform=MessengerPlatform.TELEGRAM,
        ),
    )
    who = describe_site_customer(link.customer_name, company=link.company_name)

    await _reply(callback, i18n.get(text_keys.SITE_LINK_DONE, who=who))


def _confirmation_keyboard(code: str, i18n: I18nContext) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get(text_keys.SITE_LINK_CONFIRM_BUTTON),
                    callback_data=SiteLinkCallback(confirm=True, code=code).pack(),
                ),
                InlineKeyboardButton(
                    text=i18n.get(text_keys.SITE_LINK_CANCEL_BUTTON),
                    callback_data=SiteLinkCallback(confirm=False, code=code).pack(),
                ),
            ],
        ],
    )


async def _reply(callback: CallbackQuery, text: str) -> None:
    if isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=remove_keyboard())
