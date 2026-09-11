"""Signatures of the scenario fixtures.

Beside them rather than inside ``conftest.py`` so a test can name what it
depends on without importing a conftest, which pytest owns — the same split
``tests/integration/arrange.py`` makes.
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol

from goldy.application.common.mediator.markers import BaseRequest
from goldy.application.common.ports.catalog import CatalogScope, CatalogSnapshot
from goldy.application.common.views.order import OrderPlacedView
from tests.integration.telegram.personas import Person

type CatalogPublisher = Callable[[CatalogSnapshot], Awaitable[None]]
type CatalogSweeper = Callable[[str, CatalogScope], Awaitable[None]]
type AdministratorRegistrar = Callable[[], Awaitable[Person]]
type ManagerRegistrar = Callable[[], Awaitable[Person]]


class ShopperRegistrar(Protocol):
    """Registers somebody the way pressing "share my number" registers them."""

    async def __call__(self, phone_number: str | None = None) -> Person: ...


class ActingSender(Protocol):
    """Dispatches one request on behalf of one person, in a scope of its own.

    A scope per request because that is what an update gets: the bot opens one
    around each handler, and a scenario that shared a session between two
    commands would be testing something the bot never does — a cart still in
    the identity map when the next screen asks for it.
    """

    async def __call__[TResponse](
        self,
        person: Person,
        request: BaseRequest[TResponse],
    ) -> TResponse: ...


class OrderPlacer(Protocol):
    """Fills a cart and checks it out, for a scenario that is about what follows.

    Takes ``{product number: quantity}`` and goes through the same three steps
    the dialogs do — add, read the cart, confirm what it showed — so an order
    arranged this way is one the bot could have produced.
    """

    async def __call__(
        self,
        person: Person,
        items: Mapping[int, int] | None = None,
    ) -> OrderPlacedView: ...
