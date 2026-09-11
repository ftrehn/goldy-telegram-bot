from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query


@dataclass(frozen=True, slots=True)
class GetLastDeliveryAddressQuery(Query[str | None]):
    """Where this person's previous order went, to offer as a button.

    Carries nothing, for the same reason ``ListMyOrdersQuery`` carries no
    customer: whose last order this is comes from the identity provider, so
    there is no field here through which somebody else's address could be
    asked for. An address is the most personal thing this bot stores, and the
    cheapest way to keep it unreachable is to have nowhere to name a stranger.

    Answers with the address as text rather than with a view. It is one
    nullable string and a wrapper around it would carry no second fact; the
    response is declared here because it is not a view, which is where the
    convention puts it.

    ``None`` is the ordinary answer for somebody ordering for the first time,
    not a failure: the address screen simply draws no button and waits for
    typing.
    """
