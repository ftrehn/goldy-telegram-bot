import pytest

from goldy.domain.users.errors import (
    LastMessengerAccountError,
    MessengerAccountNotLinkedError,
    NotificationTargetNotLinkedError,
    PlatformAlreadyLinkedError,
    UserAlreadyBlockedError,
    UserIsBlockedError,
    UserNotBlockedError,
)
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.messenger_username import MessengerUsername
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus
from tests.unit.factories.domain_factories import (
    MAX_ACCOUNT_ID,
    TELEGRAM_ACCOUNT_ID,
    make_account,
    make_block_reason,
    make_full_name,
    make_registered_user,
)
from tests.unit.support import drain, emitted_event_names


def test_a_registered_user_arrives_with_the_account_they_wrote_from() -> None:
    user, collection = make_registered_user()

    assert user.role is UserRole.CUSTOMER
    assert user.status is UserStatus.ACTIVE
    assert len(user.accounts) == 1
    assert emitted_event_names(collection) == ["UserRegistered"]


def test_notifications_default_to_the_platform_they_came_from() -> None:
    """It is the only channel we know reaches them."""
    user, _ = make_registered_user(account=make_account(MessengerPlatform.MAX))

    assert user.preferences.notify_via is MessengerPlatform.MAX


def test_linking_a_second_platform_records_it() -> None:
    user, collection = make_registered_user()
    emitted_event_names(collection)

    user.link_account(make_account(MessengerPlatform.MAX, MAX_ACCOUNT_ID))

    assert len(user.accounts) == 2
    assert emitted_event_names(collection) == ["MessengerAccountLinked"]


def test_linking_the_same_account_again_changes_nothing() -> None:
    """``/start`` is a button people press twice; it is not a business fact."""
    user, collection = make_registered_user()
    emitted_event_names(collection)

    user.link_account(make_account(username="renamed"))

    assert len(user.accounts) == 1
    assert user.accounts[0].username == MessengerUsername(value="renamed")
    assert emitted_event_names(collection) == []


def test_a_second_account_on_the_same_platform_is_refused() -> None:
    user, _ = make_registered_user()

    other = make_account(external_id="999999")

    with pytest.raises(PlatformAlreadyLinkedError):
        user.link_account(other)


def test_unlinking_a_platform_records_it() -> None:
    user, collection = make_registered_user()
    user.link_account(make_account(MessengerPlatform.MAX, MAX_ACCOUNT_ID))
    emitted_event_names(collection)

    user.unlink_account(MessengerPlatform.MAX)

    assert len(user.accounts) == 1
    assert emitted_event_names(collection) == ["MessengerAccountUnlinked"]


def test_unlinking_the_notification_target_repoints_it() -> None:
    """Left alone, notifications would aim at a platform that is gone."""
    user, _ = make_registered_user()
    user.link_account(make_account(MessengerPlatform.MAX, MAX_ACCOUNT_ID))

    user.unlink_account(MessengerPlatform.TELEGRAM)

    assert user.preferences.notify_via is MessengerPlatform.MAX
    assert user.notification_account().platform is MessengerPlatform.MAX


def test_the_last_account_cannot_be_unlinked() -> None:
    """Without it the person is unreachable and can never come back."""
    user, _ = make_registered_user()

    with pytest.raises(LastMessengerAccountError):
        user.unlink_account(MessengerPlatform.TELEGRAM)


def test_unlinking_a_platform_that_was_never_linked_is_refused() -> None:
    user, _ = make_registered_user()

    with pytest.raises(MessengerAccountNotLinkedError):
        user.unlink_account(MessengerPlatform.MAX)


def test_refreshing_a_handle_is_not_a_business_fact() -> None:
    user, collection = make_registered_user()
    emitted_event_names(collection)

    user.refresh_username(MessengerPlatform.TELEGRAM, MessengerUsername(value="new"))

    assert user.accounts[0].username == MessengerUsername(value="new")
    assert emitted_event_names(collection) == []


def test_renaming_records_both_names() -> None:
    user, collection = make_registered_user()
    emitted_event_names(collection)

    user.rename(make_full_name(first_name="Пётр", last_name=None))

    assert user.full_name.first_name == "Пётр"
    assert emitted_event_names(collection) == ["UserRenamed"]


def test_renaming_to_the_same_name_records_nothing() -> None:
    user, collection = make_registered_user()
    emitted_event_names(collection)

    user.rename(make_full_name())

    assert emitted_event_names(collection) == []


def test_notifications_cannot_be_pointed_at_an_unlinked_platform() -> None:
    user, _ = make_registered_user()

    preferences = user.preferences.with_notify_via(MessengerPlatform.MAX)

    with pytest.raises(NotificationTargetNotLinkedError):
        user.change_preferences(preferences)


def test_changing_preferences_to_a_linked_platform_records_it() -> None:
    user, collection = make_registered_user()
    user.link_account(make_account(MessengerPlatform.MAX, MAX_ACCOUNT_ID))
    emitted_event_names(collection)

    user.change_preferences(
        user.preferences.with_notify_via(MessengerPlatform.MAX).with_marketing_consent(
            consent=True,
        ),
    )

    assert user.preferences.marketing_consent is True
    assert emitted_event_names(collection) == ["UserPreferencesChanged"]


def test_changing_the_channel_leaves_the_language_alone() -> None:
    """Derived preferences, not fresh ones — otherwise the language resets."""
    user, _ = make_registered_user()
    user.link_account(make_account(MessengerPlatform.MAX, MAX_ACCOUNT_ID))
    original_locale = user.preferences.locale

    user.change_preferences(user.preferences.with_notify_via(MessengerPlatform.MAX))

    assert user.preferences.locale == original_locale


def test_blocking_records_the_reason() -> None:
    user, collection = make_registered_user()
    emitted_event_names(collection)

    user.block(make_block_reason())

    assert user.status is UserStatus.BLOCKED
    assert user.block_reason == make_block_reason()
    assert user.is_active is False
    assert emitted_event_names(collection) == ["UserBlocked"]


def test_blocking_twice_is_refused() -> None:
    """Overwriting the reason would erase why they were blocked in the first place."""
    user, _ = make_registered_user()
    user.block(make_block_reason())

    reason = make_block_reason("Другая причина")

    with pytest.raises(UserAlreadyBlockedError):
        user.block(reason)


def test_unblocking_clears_the_reason() -> None:
    user, collection = make_registered_user()
    user.block(make_block_reason())
    emitted_event_names(collection)

    user.unblock()

    assert user.status is UserStatus.ACTIVE
    assert user.block_reason is None
    assert emitted_event_names(collection) == ["UserUnblocked"]


def test_unblocking_someone_who_was_never_blocked_is_refused() -> None:
    user, _ = make_registered_user()

    with pytest.raises(UserNotBlockedError):
        user.unblock()


def test_a_blocked_user_cannot_act() -> None:
    user, _ = make_registered_user()
    user.block(make_block_reason())

    with pytest.raises(UserIsBlockedError):
        user.ensure_active()


def test_an_active_user_passes_the_guard() -> None:
    user, _ = make_registered_user()

    user.ensure_active()


@pytest.mark.parametrize(
    ("role", "staff"),
    (
        (UserRole.CUSTOMER, False),
        (UserRole.MANAGER, True),
        (UserRole.ADMIN, True),
    ),
)
def test_only_managers_and_admins_are_staff(role: UserRole, *, staff: bool) -> None:
    user, _ = make_registered_user(role=role)

    assert user.is_staff is staff


def test_promoting_a_customer_to_staff_is_announced() -> None:
    """The role is what the staff filters read, so a change of it is a fact."""
    user, collection = make_registered_user()
    drain(collection)

    user.assign_role(UserRole.MANAGER)

    assert user.role is UserRole.MANAGER
    assert user.is_staff is True
    assert emitted_event_names(collection) == ["UserRoleChanged"]


def test_assigning_the_role_someone_already_has_records_nothing() -> None:
    user, collection = make_registered_user()
    drain(collection)

    user.assign_role(UserRole.CUSTOMER)

    assert emitted_event_names(collection) == []


def test_an_account_is_recognised_by_platform_and_id_together() -> None:
    """An id alone means nothing — it is only unique within its own platform."""
    user, _ = make_registered_user()

    telegram_id = ExternalAccountId(value=TELEGRAM_ACCOUNT_ID)

    assert user.has_account(MessengerPlatform.TELEGRAM, telegram_id) is True
    assert user.has_account(MessengerPlatform.MAX, telegram_id) is False


def test_the_full_lifecycle_records_its_events_in_order() -> None:
    user, collection = make_registered_user()
    user.link_account(make_account(MessengerPlatform.MAX, MAX_ACCOUNT_ID))
    user.block(make_block_reason())
    user.unblock()

    assert emitted_event_names(collection) == [
        "UserRegistered",
        "MessengerAccountLinked",
        "UserBlocked",
        "UserUnblocked",
    ]
