from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.order import LastDeliveryAddressView


@dataclass(frozen=True, slots=True)
class GetLastDeliveryAddressQuery(Query[LastDeliveryAddressView]):
    """Where this person's previous order went, to offer as a button.

    Carries nothing, for the same reason ``ListMyOrdersQuery`` carries no
    customer: whose last order this is comes from the identity provider, so
    there is no field here through which somebody else's address could be
    asked for. An address is the most personal thing this bot stores, and the
    cheapest way to keep it unreachable is to have nowhere to name a stranger.

    Answers with ``LastDeliveryAddressView``, whose one field is ``None``
    for somebody ordering for the first time. That is the ordinary answer and
    not a failure: the address screen simply draws no button and waits for
    typing.
    """
