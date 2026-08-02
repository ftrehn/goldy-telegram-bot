from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


def share_phone_keyboard(button_text: str) -> ReplyKeyboardMarkup:
    """The one keyboard that cannot be inline.

    ``request_contact`` only exists on a reply keyboard, which is why the
    registration step looks different from every other screen in the bot.

    Note that pressing it is not proof of anything: Telegram happily lets a
    person forward a card from their address book instead. The handler checks
    that the contact's ``user_id`` is the sender's own.
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=button_text, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    """Clears the reply keyboard once the number has been accepted."""
    return ReplyKeyboardRemove()
