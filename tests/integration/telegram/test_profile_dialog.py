"""The profile dialog, driven the way a person drives it.

Buttons are pressed by the label on them, not by the callback data
aiogram-dialog generates from widget ids — a test naming that data would be
asserting on something nobody using the bot can see, and would break on a
rename that changed nothing.

Every window here is a real ``aiogram_dialog.Window``, which is why the fake
transport has to answer sends with a real ``Message``: the dialog stores the id
it gets back and edits that message on the next press.
"""

import pytest
from aiogram.methods import SendMessage
from dishka import FromDishka

from goldy.application.common.ports.users import UserQueryGateway
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.presentation.telegram.common import text_keys
from tests.integration.inject import inject
from tests.integration.telegram.arrange import (
    ButtonPresser,
    PersonRegistrar,
    TextRenderer,
    UpdateFeeder,
)
from tests.integration.telegram.sent import SentCalls

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]


async def test_the_profile_shows_who_you_are(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    person = await register_person()

    await feed(person.says("/me"))

    assert sent.last(SendMessage).text == text(
        text_keys.ME_PROFILE,
        name=f"{person.first_name} {person.last_name}",
        phone=person.phone_number,
        role="customer",
        locale="ru",
        notify=MessengerPlatform.TELEGRAM.value,
    )


async def test_the_profile_offers_what_can_be_changed(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    person = await register_person()

    await feed(person.says("/me"))

    assert set(sent.buttons()) == {
        text(text_keys.PROFILE_RENAME_BUTTON),
        text(text_keys.PROFILE_LOCALE_BUTTON),
        text(text_keys.PROFILE_NOTIFICATIONS_BUTTON),
        text(text_keys.PROFILE_CLOSE_BUTTON),
    }


async def test_unlinking_is_not_offered_to_somebody_with_one_account(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """The aggregate would refuse it anyway; a button that always fails is worse."""
    person = await register_person()

    await feed(person.says("/me"))

    assert text(text_keys.PROFILE_ACCOUNTS_BUTTON) not in sent.buttons()


@inject
async def test_renaming_through_the_dialog_persists(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    """Two words: the first is the name, the rest is the surname."""
    person = await register_person()
    await feed(person.says("/me"))

    await press(person, text(text_keys.PROFILE_RENAME_BUTTON))
    await feed(person.says("Пётр Петров"))

    view = await users.read_by_id(person.user_id)
    assert view is not None
    assert (view.first_name, view.last_name) == ("Пётр", "Петров")


@inject
async def test_one_word_is_a_name_without_a_surname(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    """Normal, not an error — plenty of people go by one name."""
    person = await register_person()
    await feed(person.says("/me"))

    await press(person, text(text_keys.PROFILE_RENAME_BUTTON))
    await feed(person.says("Пётр"))

    view = await users.read_by_id(person.user_id)
    assert view is not None
    assert (view.first_name, view.last_name) == ("Пётр", None)


@inject
async def test_choosing_a_language_persists_it(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    """Stored rather than held in the i18n context.

    The worker sends order updates outside any conversation, and it reads the
    language from the database — a preference living only in the dialog would
    leave those messages in the wrong one.
    """
    person = await register_person()
    await feed(person.says("/me"))

    await press(person, text(text_keys.PROFILE_LOCALE_BUTTON))
    await press(person, "en")

    view = await users.read_by_id(person.user_id)
    assert view is not None
    assert view.locale == "en"


async def test_the_language_screen_offers_what_we_translate(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Anything else would fall back silently to a screen of message keys."""
    person = await register_person()
    await feed(person.says("/me"))

    await press(person, text(text_keys.PROFILE_LOCALE_BUTTON))

    assert {"en", "ru"} <= set(sent.buttons())


@inject
async def test_a_language_change_shows_up_on_the_next_screen(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    sent: SentCalls,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    """The locale is read once per update, so the change lands on the next one."""
    person = await register_person()
    await feed(person.says("/me"))
    await press(person, text(text_keys.PROFILE_LOCALE_BUTTON))
    await press(person, "en")

    await feed(person.says("/help"))

    view = await users.read_by_id(person.user_id)
    assert view is not None
    assert sent.last_text() == text(text_keys.HELP_CUSTOMER, "en")


@inject
async def test_toggling_the_mailing_consent_persists(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    person = await register_person()
    await feed(person.says("/me"))

    await press(person, text(text_keys.PROFILE_NOTIFICATIONS_BUTTON))
    await press(person, text(text_keys.PROFILE_MARKETING_BUTTON))

    view = await users.read_by_id(person.user_id)
    assert view is not None
    assert view.marketing_consent is True


@inject
async def test_toggling_the_mailing_consent_leaves_the_language_alone(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    press: ButtonPresser,
    text: TextRenderer,
    users: FromDishka[UserQueryGateway],
) -> None:
    """Preferences are derived from the current ones, never built fresh.

    Built fresh, changing the channel would quietly reset the language back to
    the default — which is the kind of bug nobody reports, they just stop using
    the bot in their own language.
    """
    person = await register_person()
    await feed(person.says("/me"))
    await press(person, text(text_keys.PROFILE_LOCALE_BUTTON))
    await press(person, "en")

    await feed(person.says("/me"))
    await press(person, text(text_keys.PROFILE_NOTIFICATIONS_BUTTON, "en"))
    await press(person, text(text_keys.PROFILE_MARKETING_BUTTON, "en"))

    view = await users.read_by_id(person.user_id)
    assert view is not None
    assert view.locale == "en"
    assert view.marketing_consent is True
