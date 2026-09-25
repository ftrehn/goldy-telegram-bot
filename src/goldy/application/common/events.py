"""Events the application records about integrations, not about the domain.

``Order`` knows nothing of the site, so a fact about handing it over cannot
be recorded by the aggregate. It is still a fact somebody reacts to, and it
travels the same way the domain's own do — through the events collection and
the outbox, atomically with the state change it describes.
"""

from dataclasses import dataclass
from uuid import UUID

from goldy.domain.common.event import Event


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderHandoverRejected(Event):
    """The site refused an order the bot handed over, and will refuse it again.

    ``code`` is the site's stable reason — ``prices_changed``,
    ``item_unavailable``, ``credit_limit_exceeded`` and the like. The order
    stays with the bot's managers, who have to sort it out by hand.
    """

    order_id: UUID
    order_number: str
    code: str
