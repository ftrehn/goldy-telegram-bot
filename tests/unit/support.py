from goldy.domain.common.events_collection import EventsCollection


def emitted_event_names(collection: EventsCollection) -> list[str]:
    """Drains the collection and names what was in it.

    Draining is the point: a test can assert what one operation recorded
    without every earlier operation's events piling up in the expectation.
    """
    return [type(event).__name__ for event in collection.pull_events()]
