"""Builders for the commands the handlers are driven with.

Each takes only what a test varies and fills the rest with a valid default, so
a test reads as the one thing it is changing.
"""

from goldy.application.commands.users.register_user.command import RegisterUserCommand
from goldy.domain.users.values.messenger_platform import MessengerPlatform

DEFAULT_PHONE: str = "+79991234567"
DEFAULT_TELEGRAM_ID: str = "123456"
DEFAULT_MAX_ID: str = "987654"


def make_register_user_command(
    platform: MessengerPlatform = MessengerPlatform.TELEGRAM,
    external_id: str = DEFAULT_TELEGRAM_ID,
    phone_number: str = DEFAULT_PHONE,
    username: str | None = "c3equalz",
) -> RegisterUserCommand:
    return RegisterUserCommand(
        platform=platform,
        external_id=external_id,
        phone_number=phone_number,
        first_name="Данил",
        last_name="Ковалев",
        username=username,
    )
