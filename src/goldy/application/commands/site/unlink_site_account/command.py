from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command


@dataclass(frozen=True, slots=True)
class UnlinkSiteAccountCommand(Command[None]):
    """The person asked to unlink their site account. Only their own — no id."""
