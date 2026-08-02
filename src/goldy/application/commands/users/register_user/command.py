from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.user import UserView
from goldy.domain.users.values.messenger_platform import MessengerPlatform


@dataclass(frozen=True, slots=True)
class RegisterUserCommand(Command[UserView]):
    """Registers whoever just shared their contact, on either platform.

    Idempotent by design, because ``/start`` is a button people press twice:
    the same account registering again returns the same user, and a *different*
    account whose number is already known is attached to the person who owns
    that number instead of becoming a second one.

    ``phone_number`` arrives however the platform formats it and is normalised
    on the way in. It must come from the platform's own contact button — a
    number the user typed cannot be trusted to be theirs, and this command
    treats it as proof of identity.
    """

    platform: MessengerPlatform
    external_id: str
    phone_number: str
    first_name: str
    last_name: str | None = None
    username: str | None = None
