from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.infrastructure.mappers.adaptix_user_view_mapper import AdaptixUserViewMapper
from tests.unit.factories.domain_factories import (
    MAX_ACCOUNT_ID,
    TELEGRAM_ACCOUNT_ID,
    make_account,
    make_block_reason,
    make_registered_user,
)


def test_every_value_object_is_unwrapped_to_a_primitive() -> None:
    """The view crosses out of the domain, so nothing domain-shaped may ride along."""
    user, _ = make_registered_user()

    view = AdaptixUserViewMapper().to_view(user)

    assert view.id == user.id
    assert view.phone_number == "+79991234567"
    assert view.first_name == "Данил"
    assert view.last_name == "Ковалев"
    assert view.role == "customer"
    assert view.status == "active"
    assert view.notify_via == "telegram"
    assert view.locale == "ru"
    assert view.marketing_consent is False
    assert view.block_reason is None


def test_the_accounts_come_across_in_order() -> None:
    user, _ = make_registered_user()
    user.link_account(make_account(MessengerPlatform.MAX, MAX_ACCOUNT_ID))

    view = AdaptixUserViewMapper().to_view(user)

    assert [account.platform for account in view.accounts] == ["telegram", "max"]
    assert [account.external_id for account in view.accounts] == [
        TELEGRAM_ACCOUNT_ID,
        MAX_ACCOUNT_ID,
    ]


def test_an_absent_handle_stays_absent() -> None:
    """``None`` must not become the string ``"None"`` on the way out."""
    user, _ = make_registered_user(account=make_account(username=None))

    view = AdaptixUserViewMapper().to_view(user)

    assert view.accounts[0].username is None


def test_a_block_reason_is_carried_across() -> None:
    user, _ = make_registered_user()
    user.block(make_block_reason())

    view = AdaptixUserViewMapper().to_view(user)

    assert view.status == "blocked"
    assert view.block_reason == "Оскорблял поддержку"
