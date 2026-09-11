"""Where a deep link waits while the person following it registers.

The hard part of deep linking this bot is not the payload, it is the gate.
``AuthMiddleware`` turns away anybody it cannot load a user for, everywhere
except ``/start`` and a shared contact card, and that gate is fail-closed by
construction and must not be widened to let a link through. So a stranger who
taps "buy in Telegram" on a product page is two updates away from the screen
they asked for, and the thing that has to survive those two updates is the
intent.

It survives in aiogram's FSM context — the per-conversation storage the
dispatcher already keeps between updates, backed by Redis wherever the bot runs
for real. Three alternatives were considered and each loses something the
feature needs. The contact card carries no payload, so nothing can be
recovered from the registration itself. ``dialog_data`` belongs to a dialog,
and no dialog may be open in front of the gate. A table of pending intents
would be a migration, an adapter and a row nobody ever collects for every
visitor who walks away at the phone prompt.

Writing there is safe alongside aiogram-dialog, which keeps its stack and its
contexts under storage keys of its own destiny and never reads or clears the
default data this uses.

The intent is *taken* rather than read. It belongs to the registration it was
waiting for, so somebody who abandons the prompt and comes back a week later
with a plain ``/start`` is greeted, rather than dropped without warning on a
product they have long forgotten asking about.
"""

from typing import Final

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode
from aiogram_i18n import I18nContext

from goldy.application.common.mediator.sender import Sender
from goldy.presentation.telegram.common.deeplinks import DeepLinkTarget, decode_payload
from goldy.presentation.telegram.handlers.catalog.deeplinks import resolve_deeplink

PENDING_DEEPLINK_KEY: Final[str] = "pending_deeplink"
"""Where the payload waits. The payload, and not the decoded target.

FSM data is stored as JSON, and a payload is already a string in an alphabet
chosen to survive being copied through anything. Keeping the decoded pair
instead would mean a shape to migrate the first time a kind is added, for a
value the payload rebuilds in microseconds.
"""

STATE_KEY: Final[str] = "state"
"""What aiogram names the FSM context in the update data."""


async def remember_deeplink(state: FSMContext, payload: str | None) -> None:
    """Keeps where a link led until the person following it has a number.

    Only a payload that decodes is kept, and that is the entire handling of
    rubbish on this path. Nothing is stored, so registration ends in the
    ordinary welcome rather than in an apology for a link the person may not
    even have used — ``/start`` with a word after it is also just something
    somebody can type. The message about a link that does not work belongs to
    the case where there is a screen to show instead, and here it would arrive
    before the greeting.
    """
    if decode_payload(payload) is None:
        return

    await state.update_data({PENDING_DEEPLINK_KEY: payload})


async def take_deeplink(state: FSMContext) -> DeepLinkTarget | None:
    """The link that was waiting, removed from storage as it is handed over."""
    data = await state.get_data()

    if PENDING_DEEPLINK_KEY not in data:
        return None

    payload = data.pop(PENDING_DEEPLINK_KEY)
    await state.set_data(data)

    return decode_payload(payload if isinstance(payload, str) else None)


async def open_deeplink(
    target: DeepLinkTarget | None,
    *,
    message: Message,
    i18n: I18nContext,
    sender: Sender,
    dialog_manager: DialogManager,
) -> None:
    """Lands the visitor where the link led, or says why it could not.

    ``RESET_STACK`` for the reason ``/catalog`` uses it: somebody arriving from
    outside is asking to be taken somewhere, not to have a second dialog
    stacked on whatever they left open last week.

    The sentence about a dead link is sent as a message of its own rather than
    drawn into the first window. It is about the link and not about the
    catalog, it is true exactly once, and a window carrying it would keep
    repeating it as the person walked the tree.
    """
    entry = await resolve_deeplink(sender, target)

    if entry.notice is not None:
        await message.answer(i18n.get(entry.notice))

    await dialog_manager.start(entry.state, data=entry.data, mode=StartMode.RESET_STACK)


def fsm_context(manager: DialogManager) -> FSMContext:
    """Aiogram's conversation storage, reached through the dialog manager.

    The handler that needs it is already at the ceiling of five parameters with
    what aiogram injects into it by name, and the manager carries the rest of
    that conversation's state anyway — the same route the storefront's
    callbacks take to the ``I18nContext``. Asking the dispatcher for both by
    name would be two parameters for one idea.
    """
    state: FSMContext = manager.middleware_data[STATE_KEY]

    return state
