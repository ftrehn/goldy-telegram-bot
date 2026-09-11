import traceback

from goldy.domain.common.event import Event
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.user_role import UserRole

type People = dict[UserRole, User]
"""One person per role, which is what the ``people`` fixture hands out."""


def emitted_events(collection: EventsCollection) -> list[Event]:
    """Drains the collection and hands back what was in it.

    Draining is the point: a test can assert what one operation recorded
    without every earlier operation's events piling up in the expectation.
    """
    return list(collection.pull_events())


def emitted_event_names(collection: EventsCollection) -> list[str]:
    """Drains the collection and names what was in it."""
    return [type(event).__name__ for event in emitted_events(collection)]


def drain(collection: EventsCollection) -> None:
    """Throws away whatever the arrangement recorded, before the act.

    Named for the side effect the tests actually want. Calling
    ``emitted_event_names`` for it and dropping the result reads like a
    forgotten assertion, and a reader cannot tell the two apart.
    """
    collection.pull_events()


def render_exception(exc: BaseException) -> str:
    """Renders an exception, ExceptionGroup leaves included, as text.

    ``str()`` on a ``DatureConfigError`` shows only the group header; the
    per-field messages live in nested leaves. Formatting the whole traceback is
    what lets a test assert on the message an operator would actually read at
    startup.
    """
    return "".join(traceback.format_exception(exc))
