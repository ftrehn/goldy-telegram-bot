from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update


async def answer_update(
    update: Update,
    text: str,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
) -> None:
    """Answers an update whichever way it arrived.

    Exists because "where do I reply" is a question two different places were
    each answering for themselves — the auth gate and the error handler — and
    both were getting it slightly wrong in different ways.

    A callback query is answered as a callback, not by writing into the message
    it came from. That message may be an ``InaccessibleMessage`` — Telegram
    sends one for buttons on posts the bot can no longer read — and replying to
    it fails at runtime. The toast also lands where the person is looking,
    which for a button press is the button.

    Anything else is ignored on purpose: an inline query or a channel post has
    nowhere to put a refusal, and inventing one would send a stranger a message
    they never asked for.
    """
    if update.message is not None:
        await update.message.answer(text, reply_markup=reply_markup)
        return

    if update.callback_query is not None:
        await update.callback_query.answer(text, show_alert=True)
