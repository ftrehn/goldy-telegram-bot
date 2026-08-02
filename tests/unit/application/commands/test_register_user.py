from goldy.application.commands.users.register_user.handler import RegisterUserHandler
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from tests.unit.factories.command_factories import (
    DEFAULT_MAX_ID,
    DEFAULT_PHONE,
    DEFAULT_TELEGRAM_ID,
    make_register_user_command,
)
from tests.unit.stubs.gateways import InMemoryUserCommandGateway
from tests.unit.support import emitted_event_names


async def test_a_new_contact_becomes_a_new_user(
    register_user_handler: RegisterUserHandler,
    user_gateway: InMemoryUserCommandGateway,
    events_collection: EventsCollection,
) -> None:
    view = await register_user_handler.handle(make_register_user_command())

    assert view.phone_number == DEFAULT_PHONE
    assert view.notify_via == MessengerPlatform.TELEGRAM.value
    assert [account.external_id for account in view.accounts] == [DEFAULT_TELEGRAM_ID]
    assert user_gateway.added == [view.id]
    assert emitted_event_names(events_collection) == ["UserRegistered"]


async def test_the_number_is_normalised_before_anything_else(
    register_user_handler: RegisterUserHandler,
) -> None:
    """Telegram sends it without a plus; storage must still be canonical."""
    view = await register_user_handler.handle(
        make_register_user_command(phone_number="8 (999) 123-45-67"),
    )

    assert view.phone_number == DEFAULT_PHONE


async def test_pressing_start_again_returns_the_same_user(
    register_user_handler: RegisterUserHandler,
    user_gateway: InMemoryUserCommandGateway,
    events_collection: EventsCollection,
) -> None:
    """The commonest bug in this flow would be a second user here."""
    first = await register_user_handler.handle(make_register_user_command())
    emitted_event_names(events_collection)

    second = await register_user_handler.handle(make_register_user_command())

    assert second.id == first.id
    assert len(user_gateway.users) == 1
    assert emitted_event_names(events_collection) == []


async def test_pressing_start_again_refreshes_the_handle(
    register_user_handler: RegisterUserHandler,
) -> None:
    await register_user_handler.handle(make_register_user_command(username="old"))

    view = await register_user_handler.handle(
        make_register_user_command(username="new"),
    )

    assert [account.username for account in view.accounts] == ["new"]


async def test_the_same_number_from_another_platform_joins_the_same_person(
    register_user_handler: RegisterUserHandler,
    user_gateway: InMemoryUserCommandGateway,
    events_collection: EventsCollection,
) -> None:
    """The whole point of ADR-0001: one human, one order history."""
    first = await register_user_handler.handle(make_register_user_command())
    emitted_event_names(events_collection)

    second = await register_user_handler.handle(
        make_register_user_command(
            platform=MessengerPlatform.MAX,
            external_id=DEFAULT_MAX_ID,
        ),
    )

    assert second.id == first.id
    assert len(user_gateway.users) == 1
    assert {account.platform for account in second.accounts} == {
        MessengerPlatform.TELEGRAM.value,
        MessengerPlatform.MAX.value,
    }
    assert emitted_event_names(events_collection) == ["MessengerAccountLinked"]


async def test_linking_does_not_move_the_notification_target(
    register_user_handler: RegisterUserHandler,
) -> None:
    """Where they already read their messages is not changed behind their back."""
    await register_user_handler.handle(make_register_user_command())

    view = await register_user_handler.handle(
        make_register_user_command(
            platform=MessengerPlatform.MAX,
            external_id=DEFAULT_MAX_ID,
        ),
    )

    assert view.notify_via == MessengerPlatform.TELEGRAM.value


async def test_a_different_number_becomes_a_different_person(
    register_user_handler: RegisterUserHandler,
    user_gateway: InMemoryUserCommandGateway,
) -> None:
    first = await register_user_handler.handle(make_register_user_command())

    second = await register_user_handler.handle(
        make_register_user_command(
            external_id="777777",
            phone_number="+79995554433",
        ),
    )

    assert second.id != first.id
    assert len(user_gateway.users) == 2
