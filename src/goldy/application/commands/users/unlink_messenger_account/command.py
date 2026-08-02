from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.user import UserView
from goldy.domain.users.values.messenger_platform import MessengerPlatform


@dataclass(frozen=True, slots=True)
class UnlinkMessengerAccountCommand(Command[UserView]):
    """Detaches one platform from a person.

    Names the platform rather than the account id: a person has at most one
    account per platform, so the id would only be a second way to say the same
    thing, and a wrong one to act on.
    """

    user_id: UUID
    platform: MessengerPlatform
