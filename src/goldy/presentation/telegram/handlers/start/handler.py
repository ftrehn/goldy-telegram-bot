import logging
from typing import Final

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import Contact, Message
from aiogram_i18n import I18nContext

from goldy.application.commands.users.register_user.command import RegisterUserCommand
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.user import UserView
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.keyboards import (
    remove_keyboard,
    share_phone_keyboard,
)
from goldy.presentation.telegram.errors import (
    ContactBelongsToSomeoneElseError,
    ContactHasNoPhoneNumberError,
)
from goldy.presentation.telegram.filters.chat import ChatTypeFilter

logger: Final[logging.Logger] = logging.getLogger(__name__)

router: Final[Router] = Router(name="start")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message(CommandStart())
async def handle_start(
    message: Message,
    i18n: I18nContext,
    user: UserView | None = None,
) -> None:
    """Greets a known person, and asks an unknown one for their number.

    ``/start`` is reachable without registration — it is the only way in. It is
    also the button people press twice, so the known case must be a greeting
    rather than a second registration.
    """
    if user is not None:
        await message.answer(
            i18n.get(text_keys.START_WELCOME_BACK, name=user.first_name),
            reply_markup=remove_keyboard(),
        )
        return

    await message.answer(
        i18n.get(text_keys.AUTH_REGISTRATION_REQUIRED),
        reply_markup=share_phone_keyboard(
            i18n.get(text_keys.AUTH_SHARE_PHONE_BUTTON),
        ),
    )


@router.message(F.contact)
async def handle_shared_contact(
    message: Message,
    contact: Contact,
    sender: Sender,
    i18n: I18nContext,
) -> None:
    """Registers whoever just shared their own contact.

    The ownership check is the security boundary of the whole bot: Telegram
    lets anyone forward a card from their address book, and registration links
    accounts by phone number, so an unchecked card is a way into someone else's
    account.

    Raises:
        ContactBelongsToSomeoneElseError: the card is not the sender's own.
        ContactHasNoPhoneNumberError: the card carries no number.
    """
    from_user = message.from_user

    if from_user is None or contact.user_id != from_user.id:
        logger.warning(
            "start: %s shared a contact belonging to %s",
            from_user.id if from_user else "unknown",
            contact.user_id,
        )
        msg = "The shared contact does not belong to the sender."
        raise ContactBelongsToSomeoneElseError(msg)

    if not contact.phone_number:
        msg = "The shared contact carries no phone number."
        raise ContactHasNoPhoneNumberError(msg)

    view = await sender.send(
        RegisterUserCommand(
            platform=MessengerPlatform.TELEGRAM,
            external_id=str(from_user.id),
            phone_number=contact.phone_number,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            username=from_user.username,
            language_code=from_user.language_code,
        ),
    )

    await message.answer(
        i18n.get(text_keys.START_WELCOME, name=view.first_name),
        reply_markup=remove_keyboard(),
    )
