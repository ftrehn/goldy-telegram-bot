import logging
from typing import Final

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.types import Message
from aiogram_i18n import I18nContext

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.filters.chat import ChatTypeFilter

logger: Final[logging.Logger] = logging.getLogger(__name__)

router: Final[Router] = Router(name="fallback")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message()
async def handle_unknown(message: Message, i18n: I18nContext) -> None:
    """Answers anything no other handler claimed.

    Registered last, and it matches everything — which is the point. Without
    it a registered person who mistypes a command gets silence, and silence
    from a bot is indistinguishable from the bot being down.
    """
    logger.debug("fallback: unhandled message from %s", message.chat.id)

    await message.answer(i18n.get(text_keys.UNKNOWN_COMMAND))
