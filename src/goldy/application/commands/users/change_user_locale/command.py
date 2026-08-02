from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.user import UserView


@dataclass(frozen=True, slots=True)
class ChangeUserLocaleCommand(Command[UserView]):
    """Switches the language the bot answers this person in.

    Separate from the notification settings because it is a separate screen and
    a separate decision — bundling them would mean the language picker had to
    restate a notification channel it has no business knowing about.
    """

    user_id: UUID
    locale: str
