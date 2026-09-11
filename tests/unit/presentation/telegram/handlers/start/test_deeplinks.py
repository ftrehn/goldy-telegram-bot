"""The intent that has to survive a registration, and what happens if it does not.

This is the tricky half of deep linking, and it is tricky because of a rule
that must not bend. ``AuthMiddleware`` is fail-closed: a stranger following a
link from a product page gets the phone prompt and nothing else, so the product
they asked for and the screen showing it are two updates apart. Lose the intent
in between and the feature silently degrades into "every link opens a
greeting", which nobody notices because nothing fails.

The storage is aiogram's own FSM context, and it is exercised here through a
real one over ``MemoryStorage`` rather than a stand-in — what is being checked
is that the value comes back out, which a stand-in would grant for free.
"""

from typing import Final

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from goldy.presentation.telegram.common.deeplinks import (
    DeepLinkKind,
    DeepLinkTarget,
    encode_payload,
)
from goldy.presentation.telegram.handlers.start.deeplinks import (
    PENDING_DEEPLINK_KEY,
    remember_deeplink,
    take_deeplink,
)

PRODUCT: Final[DeepLinkTarget] = DeepLinkTarget(
    kind=DeepLinkKind.PRODUCT,
    id="9b2f5c1e-7a43-4d8e-9f10-6c3b2a1d0e5f",
)


@pytest.fixture()
def state() -> FSMContext:
    """One conversation's storage, the way the dispatcher would hand it over."""
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=42, chat_id=500_001, user_id=500_001),
    )


async def test_a_link_followed_by_a_stranger_waits_for_their_registration(
    state: FSMContext,
) -> None:
    """The one assertion the whole feature rests on for a new customer.

    Without it the link still works — it just works for people who were already
    registered, which is the half of the audience the link was not printed for.
    """
    await remember_deeplink(state, encode_payload(PRODUCT))

    assert await take_deeplink(state) == PRODUCT


async def test_the_intent_belongs_to_one_registration_and_is_spent_by_it(
    state: FSMContext,
) -> None:
    """Taken rather than read, so it cannot surface weeks later.

    Somebody who abandons the phone prompt and comes back with a plain
    ``/start`` is greeted. A stored intent that was only read would instead
    drop them on a product they have long forgotten asking about, with no
    explanation of where it came from.
    """
    await remember_deeplink(state, encode_payload(PRODUCT))
    await take_deeplink(state)

    assert await take_deeplink(state) is None


async def test_an_ordinary_registration_carries_no_intent(state: FSMContext) -> None:
    """Nobody followed a link, so nothing is waiting and the welcome is the end."""
    assert await take_deeplink(state) is None


@pytest.mark.parametrize(
    "payload",
    (None, "", "not a payload", "x_QUJD", "p_QUJ$"),
)
async def test_rubbish_after_start_is_not_worth_remembering(
    state: FSMContext,
    payload: str | None,
) -> None:
    """``/start`` is a command anybody may type, with anything after it.

    Storing what cannot be decoded would mean answering a person who typed a
    word after ``/start`` with an apology about a broken link they never
    followed — after they had shared their phone number, which is the worst
    possible moment to be told something went wrong.
    """
    await remember_deeplink(state, payload)

    assert await state.get_data() == {}


async def test_the_intent_does_not_trample_the_rest_of_the_conversation(
    state: FSMContext,
) -> None:
    """One key in shared storage, put back the way it was found.

    ``take_deeplink`` rewrites the whole data dictionary to drop its key, which
    is the only way aiogram offers to remove one — so anything else living
    there has to survive the rewrite.
    """
    await state.update_data(something_else="kept")
    await remember_deeplink(state, encode_payload(PRODUCT))
    await take_deeplink(state)

    assert await state.get_data() == {"something_else": "kept"}


async def test_the_payload_is_what_is_stored_rather_than_the_decoded_target(
    state: FSMContext,
) -> None:
    """Because FSM data is JSON, and a payload already is a string.

    Keeping the decoded pair would put a shape into Redis that has to be
    migrated the first time a kind is added, for a value the
    payload rebuilds in microseconds.
    """
    payload = encode_payload(PRODUCT)

    await remember_deeplink(state, payload)

    assert await state.get_data() == {PENDING_DEEPLINK_KEY: payload}
