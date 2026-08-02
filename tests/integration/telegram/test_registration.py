"""Getting in, which is the only thing an unregistered person may do.

Every update here goes through the real dispatcher: dishka's middleware, the
auth gate, i18n, the router filters, the handler, the mediator, the transaction
and the outbox. Nothing below the ports is stubbed, so "registering worked"
means a row in Postgres and an event in the outbox, not a mock recording a call.
"""

import pytest
from aiogram.methods import SendMessage
from aiogram.types import ReplyKeyboardMarkup
from dishka import FromDishka

from goldy.application.commands.outbox.relay_outbox.command import RelayOutboxCommand
from goldy.application.common.ports.users import UserCommandGateway, UserQueryGateway
from goldy.application.common.query_params.user_filters import UserFilters
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.presentation.telegram.common import text_keys
from tests.integration.arrange import CommandSender
from tests.integration.brokers import PublishedEvents
from tests.integration.inject import inject
from tests.integration.telegram.arrange import (
    PersonRegistrar,
    TextRenderer,
    UpdateFeeder,
)
from tests.integration.telegram.personas import a_stranger
from tests.integration.telegram.sent import SentCalls

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

EVERYONE = UserFilters()


async def test_a_stranger_pressing_start_is_asked_for_their_number(
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """``/start`` is the only way in, so the gate has to let it through."""
    await feed(a_stranger().says("/start"))

    assert sent.only(SendMessage).text == text(text_keys.AUTH_REGISTRATION_REQUIRED)


async def test_the_invitation_carries_the_button_that_shares_a_number(
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Without it the instruction names a button that is not on screen."""
    await feed(a_stranger().says("/start"))

    markup = sent.only(SendMessage).reply_markup
    assert isinstance(markup, ReplyKeyboardMarkup)
    [[button]] = markup.keyboard
    assert button.text == text(text_keys.AUTH_SHARE_PHONE_BUTTON)
    assert button.request_contact is True


@inject
async def test_sharing_your_own_contact_registers_you(
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
    users: FromDishka[UserCommandGateway],
) -> None:
    stranger = a_stranger()

    await feed(stranger.shares_contact())

    assert sent.last_text() == text(
        text_keys.START_WELCOME,
        name=stranger.first_name,
    )
    stored = await users.by_phone_number(PhoneNumber(value=stranger.phone_number))
    assert stored is not None


@inject
async def test_registration_links_the_account_that_wrote_to_us(
    feed: UpdateFeeder,
    users: FromDishka[UserCommandGateway],
) -> None:
    """The link is what makes the next update recognisable as the same person."""
    stranger = a_stranger()

    await feed(stranger.shares_contact())

    stored = await users.by_messenger_account(
        MessengerPlatform.TELEGRAM,
        ExternalAccountId(value=str(stranger.telegram_id)),
    )
    assert stored is not None
    assert stored.phone_number == PhoneNumber(value=stranger.phone_number)


async def test_a_registered_person_pressing_start_is_greeted_back(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """``/start`` is a button people press twice; the second time is not a signup."""
    person = await register_person()

    await feed(person.says("/start"))

    assert sent.only(SendMessage).text == text(
        text_keys.START_WELCOME_BACK,
        name=person.first_name,
    )


@inject
async def test_somebody_elses_contact_registers_nobody(
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
    users: FromDishka[UserCommandGateway],
) -> None:
    """The security boundary of the whole bot.

    Telegram lets anyone forward a card from their address book, and
    registration links accounts by number — so an unchecked card is a way into
    somebody else's account.
    """
    attacker = a_stranger(telegram_id=999_000_777)
    victim_number = "+79995550000"

    await feed(attacker.shares_contact(phone_number=victim_number, owner_id=12345))

    assert sent.last_text() == text(text_keys.AUTH_CONTACT_NOT_YOURS)
    assert await users.by_phone_number(PhoneNumber(value=victim_number)) is None


async def test_a_contact_without_a_number_is_refused(
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    await feed(a_stranger().shares_contact_without_number())

    assert sent.last_text() == text(text_keys.AUTH_CONTACT_WITHOUT_NUMBER)


@inject
async def test_registering_twice_from_one_account_keeps_one_person(
    feed: UpdateFeeder,
    query_gateway: FromDishka[UserQueryGateway],
) -> None:
    """People press the share button again when they are unsure it worked."""
    stranger = a_stranger()

    await feed(stranger.shares_contact())
    await feed(stranger.shares_contact())

    assert await query_gateway.total(EVERYONE) == 1


async def test_a_registration_reaches_the_broker(
    feed: UpdateFeeder,
    send_worker_command: CommandSender,
    published: PublishedEvents,
) -> None:
    """The whole point of the outbox, across both processes.

    The bot writes the event in the same transaction as the user row and never
    touches RabbitMQ; the worker picks it up on its own tick. Nothing but a test
    spanning both containers shows that the handover works.
    """
    await feed(a_stranger().shares_contact())

    await send_worker_command(RelayOutboxCommand())

    assert published.routing_keys() == ("UserRegistered",)
