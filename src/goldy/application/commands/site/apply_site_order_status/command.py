from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.ports.site import SiteOrderStatus


@dataclass(frozen=True, slots=True)
class ApplySiteOrderStatusCommand(Command[bool]):
    """Bring one bot order in line with what the site's feed says about it."""

    status: SiteOrderStatus
