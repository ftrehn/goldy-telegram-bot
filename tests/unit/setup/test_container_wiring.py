"""Every container is built, and two deliberately impossible ones are not.

This is not a test of dishka. dishka resolving what it was told to resolve is
its own business, and a test asserting that would be worthless. What is
asserted here is *our* wiring: that no port anywhere in the graph was left
without an adapter, and that a process is still refused the handlers it must
not be able to run — the worker the ones that need to know who is asking, the
bot the ones that carry a Bot API token to write to somebody who did not ask.

The two are the same mechanism seen from either side. Building a container
walks every factory in every scope and fails on the first dependency nothing
provides, which is why a forgotten line in ``gateways_provider`` or
``mappers_provider`` shows up here as a failure naming the missing port rather
than in production as a resolution error in the middle of an update.

It costs one build per process and needs no database: the engine is created
when something first asks for a session, not when the container is made.
"""

import pytest
from dishka import make_async_container
from dishka.exceptions import GraphMissingFactoryError

from goldy.setup.ioc.containers import (
    make_catalog_seed_container,
    make_telegram_container,
    make_worker_container,
)
from goldy.setup.ioc.containers.telegram import telegram_providers
from goldy.setup.ioc.containers.worker import worker_providers
from goldy.setup.ioc.providers import (
    notification_handlers_provider,
    shop_handlers_provider,
)
from tests.unit.factories.container_factories import (
    create_catalog_seed_context,
    create_telegram_context,
    create_worker_context,
)


def test_the_telegram_container_is_fully_wired() -> None:
    container = make_telegram_container(create_telegram_context())

    assert container is not None


def test_the_worker_container_is_fully_wired() -> None:
    container = make_worker_container(create_worker_context())

    assert container is not None


def test_the_catalog_seed_container_is_fully_wired() -> None:
    container = make_catalog_seed_container(create_catalog_seed_context())

    assert container is not None


def test_the_bot_refuses_notification_handlers() -> None:
    """The token isolation, stated the same way the identity one is.

    ``notifications_provider`` is what carries the Bot API client the worker
    writes with, and the bot process does not get it. Dropping the notification
    handlers into the Telegram container therefore fails to build: nothing
    there provides an ``InboxGateway`` or a ``NotificationDispatcher``.

    Worth pinning because the failure it prevents is not a crash. A bot that
    could resolve one of these would be answering somebody's update by writing
    to a different person, which no screen has any business doing.
    """
    providers = (*telegram_providers(), notification_handlers_provider())

    with pytest.raises(GraphMissingFactoryError):
        make_async_container(*providers, context=create_telegram_context())


def test_the_worker_refuses_storefront_handlers() -> None:
    """The reason the handler groups are split, stated as a failing build.

    A storefront handler reaches ``IdentityProvider`` sooner or later, and a
    background task is nobody's request. Moving the group into the core to make
    a wiring error go away would silently give the worker handlers that cannot
    answer "who is buying" — and the failure would surface halfway through a
    task instead of at startup.
    """
    providers = (*worker_providers(), shop_handlers_provider())

    with pytest.raises(GraphMissingFactoryError):
        make_async_container(*providers, context=create_worker_context())
