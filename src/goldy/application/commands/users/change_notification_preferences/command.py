from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.user import UserView
from goldy.domain.users.values.messenger_platform import MessengerPlatform


@dataclass(frozen=True, slots=True)
class ChangeNotificationPreferencesCommand(Command[UserView]):
    """Picks where order updates land and whether marketing is welcome.

    Replaces both settings at once rather than patching one: two half-updates
    racing each other would otherwise interleave into a state neither caller
    asked for.
    """

    user_id: UUID
    notify_via: MessengerPlatform
    marketing_consent: bool
