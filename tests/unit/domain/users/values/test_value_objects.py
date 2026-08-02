import pytest

from goldy.domain.users.errors import (
    EmptyBlockReasonError,
    EmptyExternalAccountIdError,
    EmptyFirstNameError,
    EmptyMessengerUsernameError,
    EmptyPhoneNumberError,
    InvalidPhoneNumberFormatError,
    TooLongBlockReasonError,
    TooLongNamePartError,
    UnsupportedLocaleError,
)
from goldy.domain.users.values.block_reason import (
    MAX_BLOCK_REASON_LENGTH,
    BlockReason,
)
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.full_name import MAX_NAME_PART_LENGTH, FullName
from goldy.domain.users.values.locale import Locale
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.messenger_username import MessengerUsername
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.domain.users.values.user_preferences import UserPreferences


@pytest.mark.parametrize(
    "raw",
    (
        "+79991234567",
        "79991234567",
        "89991234567",
        "8 (999) 123-45-67",
        "+7 999 123-45-67",
        "8-999-123-45-67",
    ),
)
def test_every_way_of_writing_one_number_normalises_to_the_same_value(
    raw: str,
) -> None:
    """Identity rests on this.

    Two accounts are recognised as one person because their numbers compare
    equal, so a number reaching storage in two different shapes would quietly
    become two people.
    """
    assert PhoneNumber.from_raw(raw) == PhoneNumber(value="+79991234567")


def test_a_foreign_number_keeps_its_own_country_code() -> None:
    """The 8 -> +7 rule must not fire on numbers that are not Russian."""
    assert PhoneNumber.from_raw("+380501234567").value == "+380501234567"


@pytest.mark.parametrize("blank", ("", "   ", "\t\n", "no digits here"))
def test_a_number_without_digits_is_rejected(blank: str) -> None:
    with pytest.raises(EmptyPhoneNumberError):
        PhoneNumber.from_raw(blank)


@pytest.mark.parametrize("malformed", ("+7999", "79991234567", "7999123456789012345"))
def test_a_number_that_is_not_e164_is_rejected(malformed: str) -> None:
    """The constructor takes canonical form only — normalising is from_raw's job."""
    with pytest.raises(InvalidPhoneNumberFormatError):
        PhoneNumber(value=malformed)


def test_a_name_needs_a_first_name() -> None:
    with pytest.raises(EmptyFirstNameError):
        FullName(first_name="   ")


def test_a_surname_is_optional() -> None:
    """Messengers do not guarantee one, and that must not block registration."""
    assert FullName(first_name="Данил").last_name is None


@pytest.mark.parametrize(
    ("first_name", "last_name"),
    (
        ("я" * (MAX_NAME_PART_LENGTH + 1), None),
        ("Данил", "я" * (MAX_NAME_PART_LENGTH + 1)),
    ),
)
def test_an_overlong_name_part_is_rejected(
    first_name: str,
    last_name: str | None,
) -> None:
    with pytest.raises(TooLongNamePartError):
        FullName(first_name=first_name, last_name=last_name)


def test_a_name_renders_with_and_without_a_surname() -> None:
    assert str(FullName(first_name="Данил", last_name="Ковалев")) == "Данил Ковалев"
    assert str(FullName(first_name="Данил")) == "Данил"


def test_a_block_reason_cannot_be_blank() -> None:
    """Whoever lifts the block months later needs to know why it was imposed."""
    with pytest.raises(EmptyBlockReasonError):
        BlockReason(value="  ")


def test_an_overlong_block_reason_is_rejected() -> None:
    with pytest.raises(TooLongBlockReasonError):
        BlockReason(value="x" * (MAX_BLOCK_REASON_LENGTH + 1))


def test_blank_platform_identifiers_are_rejected() -> None:
    with pytest.raises(EmptyExternalAccountIdError):
        ExternalAccountId(value=" ")
    with pytest.raises(EmptyMessengerUsernameError):
        MessengerUsername(value=" ")


def test_value_objects_compare_by_value() -> None:
    """Two separately built objects, so this is value equality, not identity."""
    one = ExternalAccountId(value="123")
    same_value = ExternalAccountId(value="123")
    other_value = ExternalAccountId(value="456")

    assert one == same_value
    assert one != other_value


def test_preferences_are_replaced_rather_than_mutated() -> None:
    original = UserPreferences(
        notify_via=MessengerPlatform.TELEGRAM, locale=Locale(value="ru")
    )

    changed = original.with_notify_via(MessengerPlatform.MAX)

    assert changed.notify_via is MessengerPlatform.MAX
    assert original.notify_via is MessengerPlatform.TELEGRAM
    assert changed.marketing_consent is original.marketing_consent


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        ("ru", "ru"),
        ("en", "en"),
        ("en-GB", "en"),
        ("pt_BR", "ru"),
        ("de", "ru"),
        (None, "ru"),
        ("  RU  ", "ru"),
    ),
)
def test_a_platform_language_code_falls_back_to_the_default(
    raw: str | None,
    expected: str,
) -> None:
    """A Brazilian pressing /start should get a working bot, not a refusal."""
    assert Locale.from_language_code(raw).value == expected


def test_a_locale_we_do_not_translate_is_refused_outright() -> None:
    """The constructor is for values we chose ourselves — a bug, not user input."""
    with pytest.raises(UnsupportedLocaleError):
        Locale(value="de")


def test_the_language_can_be_changed_without_touching_the_rest() -> None:
    original = UserPreferences(
        notify_via=MessengerPlatform.TELEGRAM,
        locale=Locale(value="ru"),
        marketing_consent=True,
    )

    changed = original.with_locale(Locale(value="en"))

    assert changed.locale == Locale(value="en")
    assert changed.notify_via is original.notify_via
    assert changed.marketing_consent is True


def test_marketing_consent_is_off_until_asked_for() -> None:
    assert (
        UserPreferences(
            notify_via=MessengerPlatform.TELEGRAM, locale=Locale(value="ru")
        ).marketing_consent
        is False
    )
