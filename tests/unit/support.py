import traceback

from goldy.domain.common.events_collection import EventsCollection


def emitted_event_names(collection: EventsCollection) -> list[str]:
    """Drains the collection and names what was in it.

    Draining is the point: a test can assert what one operation recorded
    without every earlier operation's events piling up in the expectation.
    """
    return [type(event).__name__ for event in collection.pull_events()]


def render_exception(exc: BaseException) -> str:
    """Renders an exception, ExceptionGroup leaves included, as text.

    ``str()`` on a ``DatureConfigError`` shows only the group header; the
    per-field messages live in nested leaves. Formatting the whole traceback is
    what lets a test assert on the message an operator would actually read at
    startup.
    """
    return "".join(traceback.format_exception(exc))
