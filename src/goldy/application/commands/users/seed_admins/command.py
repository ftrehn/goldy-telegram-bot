from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.user import SeedAdminsResponse


@dataclass(frozen=True, slots=True)
class SeedAdminsCommand(Command[SeedAdminsResponse]):
    """Grants the administrator role to everyone the configuration names.

    Run at startup. Covers the people already registered when their number was
    added to the list; anyone registering afterwards is caught by the
    registration handler instead. Between the two there is no gap, which is the
    point — an administrator who has to wait for a restart looks like a bug.

    Idempotent: someone who already holds the role records no event.
    """
