"""The receiver over a real aiohttp server, with a recording sender behind dishka.

``TestServer`` binds the application to a port on the loopback and
``TestClient`` talks to it over a socket, so what these tests exercise is the
receiver as 1C meets it: the middlewares in their order, aiohttp's own
handling of a body over the limit, the dishka request scope opened per
request. Only the sender is a stub — what the commands would do to the
projection is the handlers' business and is tested where they live.
"""

from collections.abc import AsyncIterator
from typing import Final

import pytest
from aiohttp.test_utils import TestClient, TestServer
from aiohttp.web import Application, Request
from dishka import AsyncContainer, Provider, Scope, make_async_container

from goldy.application.common.mediator.sender import Sender
from goldy.infrastructure.adapters.catalog.adaptix_catalog_snapshot_mapper import (
    AdaptixCatalogSnapshotMapper,
)
from goldy.infrastructure.adapters.catalog.catalog_snapshot_mapper import (
    CatalogSnapshotMapper,
)
from goldy.infrastructure.catalog_receiver.app import create_catalog_receiver_app
from tests.unit.stubs.catalog import RecordingCatalogSender

TOKEN: Final[str] = "test-catalog-token-0123456789abcdef"
MAX_BODY_BYTES: Final[int] = 4096
"""Small enough that a test can exceed it with a body it builds by hand."""

type ReceiverClient = TestClient[Request, Application]


@pytest.fixture()
def sender() -> RecordingCatalogSender:
    return RecordingCatalogSender()


@pytest.fixture()
def container(sender: RecordingCatalogSender) -> AsyncContainer:
    """The two things a handler asks for, scoped as the real container scopes them."""
    provider = Provider(scope=Scope.REQUEST)
    provider.provide(lambda: sender, provides=Sender)
    provider.provide(
        AdaptixCatalogSnapshotMapper,
        provides=CatalogSnapshotMapper,
        scope=Scope.APP,
    )
    return make_async_container(provider)


@pytest.fixture()
async def client(container: AsyncContainer) -> AsyncIterator[ReceiverClient]:
    async with _serve(container, TOKEN) as test_client:
        yield test_client

    await container.close()


@pytest.fixture()
async def padded_token_client(
    container: AsyncContainer,
) -> AsyncIterator[ReceiverClient]:
    """The receiver configured with the token as a ``.env`` can hand it over.

    A value in quotes keeps its spaces through ``python-dotenv``, and the
    loader lets it through as long as what is left after stripping is long
    enough — so the receiver has to compare it the way 1C will send it.
    """
    async with _serve(container, f" {TOKEN} ") as test_client:
        yield test_client

    await container.close()


def _serve(container: AsyncContainer, token: str) -> ReceiverClient:
    """A client over a real server, for the app built with this token."""
    app = create_catalog_receiver_app(
        container,
        token=token,
        max_body_bytes=MAX_BODY_BYTES,
    )

    return TestClient(TestServer(app))
