"""``/start``, which is three doors rather than one.

A plain ``/start`` is a greeting or an invitation to register. A ``/start``
with a payload after it is somebody who tapped "buy in Telegram" on the shop's
website, and they are owed the product they tapped — after the registration
gate if they are new, immediately if they are not.

The three are separate handlers rather than one with branches, and the reason
is the ceiling on how many things aiogram may inject into one signature.
Opening a product needs the mediator and the dialog manager; storing an intent
needs the FSM context; neither needs the other's. Splitting on the filters that
already tell them apart — a payload is present or it is not, a user was loaded
or was not — costs one ``MagicData`` and keeps each signature honest about what
its own case uses.

The order they are registered in is the order aiogram tries them, and it is
load-bearing: ``CommandStart()`` matches a deep link too, so the greeting has
to come last.
"""

import logging
from typing import Final

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandObject, CommandStart, MagicData
from aiogram.fsm.context import FSMContext
from aiogram.types import Contact, Message
from aiogram_dialog import DialogManager
from aiogram_i18n import I18nContext
from dishka import FromDishka

from goldy.application.commands.users.register_user.command import RegisterUserCommand
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.user import UserView
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.deeplinks import decode_payload
from goldy.presentation.telegram.common.keyboards import (
    remove_keyboard,
    share_phone_keyboard,
)
from goldy.presentation.telegram.errors import (
    ContactBelongsToSomeoneElseError,
    ContactHasNoPhoneNumberError,
)
from goldy.presentation.telegram.filters.chat import ChatTypeFilter
from goldy.presentation.telegram.handlers.start.deeplinks import (
    fsm_context,
    open_deeplink,
    remember_deeplink,
    take_deeplink,
)
from goldy.presentation.telegram.middlewares.auth_middleware import USER_KEY

logger: Final[logging.Logger] = logging.getLogger(__name__)

router: Final[Router] = Router(name="start")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message(CommandStart(deep_link=True), MagicData(F[USER_KEY]))
async def handle_deeplink(
    message: Message,
    command: CommandObject,
    i18n: I18nContext,
    dialog_manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Opens what the link pointed at, for a customer the bot already knows.

    ``CommandStart(deep_link=True)`` rather than a look at ``message.text``:
    Telegram delivers ``/start@goldy_bot`` in a group and ``/start <payload>``
    in a private chat, and only aiogram's own parser reads both correctly. That
    is the same reason the auth gate uses it, and getting it wrong there means
    an unregistered person cannot register at all. With ``deep_link=True`` a
    bare ``/start`` does not match and falls through to the greeting below.

    ``MagicData`` reads the update's *data* rather than the update: the user
    the gate loaded is put there under :data:`USER_KEY`, and filtering on it
    is what separates this handler from the registration one without either of
    them having to check.
    """
    await open_deeplink(
        decode_payload(command.args),
        message=message,
        i18n=i18n,
        sender=sender,
        dialog_manager=dialog_manager,
    )


@router.message(CommandStart(deep_link=True))
async def handle_deeplink_registration(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    i18n: I18nContext,
) -> None:
    """Holds on to where the link led, then asks for a phone number.

    The gate is not widened for a link and this handler does not try to. It
    answers exactly what a stranger typing ``/start`` is answered with, and the
    only difference is that the intent is written down first.

    Which is the order that matters. Somebody who tapped a product on a website
    and was met by a bot demanding their phone number has been asked for
    something real by something they have never spoken to; what makes the ask
    reasonable is that the product is still waiting on the other side of it.
    That only holds if the intent is stored before the prompt goes out, because
    between the two there is a person deciding whether to bother.
    """
    await remember_deeplink(state, command.args)
    await message.answer(
        i18n.get(text_keys.AUTH_REGISTRATION_REQUIRED),
        reply_markup=share_phone_keyboard(
            i18n.get(text_keys.AUTH_SHARE_PHONE_BUTTON),
        ),
    )


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

    Last of the three on purpose: ``CommandStart()`` with no ``deep_link``
    matches a payload as happily as it matches a bare command, so registered
    above the other two it would answer every link from the website with a
    greeting and drop what the link was for.
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


@router.message(F.contact.as_("contact"))
async def handle_shared_contact(
    message: Message,
    contact: Contact,
    sender: FromDishka[Sender],
    i18n: I18nContext,
    dialog_manager: DialogManager,
) -> None:
    """Registers whoever just shared their own contact, and redeems their link.

    ``F.contact.as_("contact")`` rather than a bare ``F.contact``: the filter
    only decides *whether* to run without it, and aiogram then calls this with
    no ``contact`` at all. ``Sender`` needs ``FromDishka`` for the same class of
    reason — the container fills annotated parameters and ignores the rest.
    Both fail at call time, as a ``TypeError`` about missing arguments.

    The ownership check is the security boundary of the whole bot: Telegram
    lets anyone forward a card from their address book, and registration links
    accounts by phone number, so an unchecked card is a way into someone else's
    account.

    A link followed before registration is redeemed at the end, after the
    welcome rather than instead of it. The welcome is what takes the phone
    keyboard away, and a dialog window drawn over a reply keyboard that is
    still standing is the one screen in this bot that looks broken.

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

    target = await take_deeplink(fsm_context(dialog_manager))

    if target is None:
        return

    await open_deeplink(
        target,
        message=message,
        i18n=i18n,
        sender=sender,
        dialog_manager=dialog_manager,
    )
