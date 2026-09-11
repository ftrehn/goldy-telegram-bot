"""Acting as somebody, without a messenger in the way.

Every request a person makes needs an answer to "who is writing", and the
production answer is ``TelegramIdentityProvider``, built by the bot's container
out of the account aiogram found on the update. These tests reuse exactly that:
a request scope is opened on the real Telegram container with the middleware
data an update would have carried, and the identity resolves through the real
adapter — account id to ``UserId``, against the real ``users`` table.

The alternative was a stub identity bound into a container assembled for tests,
and it was refused. Resolving a platform account into our own user is the first
step of every scenario in this package, it has its own failure mode — the
account belongs to nobody — and a stub would have quietly asserted that step
away while looking like it tested the same thing.

What is *not* here is a dispatcher, a dialog or a message. The scenarios send
the requests the dialogs send; what those dialogs draw is covered in
``tests/integration/telegram``.
"""

from collections.abc import Mapping
from dataclasses import replace
from itertools import count
from typing import Any, Final
from uuid import UUID

import pytest
from aiogram.types import User as TelegramUser
from dishka import AsyncContainer, Scope
from dishka.integrations.aiogram import AiogramMiddlewareData

from goldy.application.commands.carts.add_to_cart.command import AddToCartCommand
from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.commands.users.change_user_role.command import (
    ChangeUserRoleCommand,
)
from goldy.application.commands.users.register_user.command import RegisterUserCommand
from goldy.application.common.mediator.markers import BaseRequest
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.ports.catalog import CatalogScope, CatalogSnapshot
from goldy.application.common.views.order import OrderPlacedView
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.user_id import UserId
from goldy.domain.users.values.user_role import UserRole
from tests.integration.arrange import CommandSender
from tests.integration.scenarios.acting import (
    ActingSender,
    AdministratorRegistrar,
    CatalogPublisher,
    CatalogSweeper,
    ManagerRegistrar,
    OrderPlacer,
    ShopperRegistrar,
)
from tests.integration.scenarios.shop import a_checkout
from tests.integration.telegram.personas import Person
from tests.unit.factories.catalog_factories import make_product_id_value
from tests.unit.factories.domain_factories import ADMIN_PHONE

FIRST_TELEGRAM_ID: Final[int] = 600_001
"""Far away from the ids the Telegram tests hand out, so a failure names a file."""

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _send_as[TResponse](
    container: AsyncContainer,
    account: TelegramUser,
    request: BaseRequest[TResponse],
) -> TResponse:
    """One request, in a scope that believes *account* sent the update.

    ``event_from_user`` is the single key the container reads to build an
    identity, and it is read from the sender rather than from the chat for the
    reason ``TelegramProvider`` spells out: in a group the chat id belongs to
    the group and every member would share one account.
    """
    middleware_data: dict[str, Any] = {"event_from_user": account}

    async with container(
        {AiogramMiddlewareData: middleware_data},
        scope=Scope.REQUEST,
    ) as request_container:
        sender: Sender = await request_container.get(Sender)
        response: TResponse = await sender.send(request)
        return response


@pytest.fixture()
def act(telegram_container: AsyncContainer) -> ActingSender:
    """Sends one request as one person — how every scenario step is written."""

    async def send[TResponse](
        person: Person,
        request: BaseRequest[TResponse],
    ) -> TResponse:
        return await _send_as(telegram_container, person.account, request)

    return send


@pytest.fixture()
def register_shopper(telegram_container: AsyncContainer) -> ShopperRegistrar:
    """Puts somebody in the database through ``RegisterUserCommand``.

    Through the command and not through the gateway, unlike ``seed_user`` next
    door, because registration is a step of the scenario rather than a
    precondition for it: what a customer ends up being — their locale, their
    role, which account they are reachable on — is decided by that handler, and
    a row inserted around it would be a row production never produces.

    Each call gets an id and a number of its own, so a scenario with two
    customers in it cannot have them collide on the unique index.
    """
    telegram_ids = count(FIRST_TELEGRAM_ID)

    async def register(phone_number: str | None = None) -> Person:
        telegram_id = next(telegram_ids)
        number = phone_number if phone_number is not None else f"+79{telegram_id:09d}"
        candidate = Person(
            user_id=UserId(UUID(int=0)),
            telegram_id=telegram_id,
            phone_number=number,
        )

        view = await _send_as(
            telegram_container,
            candidate.account,
            RegisterUserCommand(
                platform=MessengerPlatform.TELEGRAM,
                external_id=str(telegram_id),
                phone_number=number,
                first_name=candidate.first_name,
                last_name=candidate.last_name,
                username=candidate.username,
                language_code=candidate.language_code,
            ),
        )
        return replace(candidate, user_id=UserId(view.id))

    return register


@pytest.fixture()
def register_administrator(
    register_shopper: ShopperRegistrar,
) -> AdministratorRegistrar:
    """The person whose number the bot is configured to treat as an administrator.

    Registered like anybody else — the role comes from ``AdminRegistry`` inside
    the handler, which is the only way anybody becomes one.

    Memoised because the number is fixed by configuration: a second
    registration from another Telegram account would find the number already
    taken and meet ``PlatformAlreadyLinkedError`` rather than create a second
    administrator.
    """
    administrator: Person | None = None

    async def register() -> Person:
        nonlocal administrator

        if administrator is None:
            administrator = await register_shopper(ADMIN_PHONE)

        return administrator

    return register


@pytest.fixture()
def register_manager(
    register_shopper: ShopperRegistrar,
    register_administrator: AdministratorRegistrar,
    act: ActingSender,
) -> ManagerRegistrar:
    """Somebody staff, promoted the only way anybody is promoted.

    An administrator hands the role out through ``ChangeUserRoleCommand``,
    because that command is the whole reason a manager exists in the database:
    assigning the role on the aggregate would arrange a state the bot has no
    path to and would skip the permission that guards it.
    """

    async def register() -> Person:
        administrator = await register_administrator()
        manager = await register_shopper()

        await act(
            administrator,
            ChangeUserRoleCommand(user_id=manager.user_id, role=UserRole.MANAGER),
        )
        return manager

    return register


@pytest.fixture()
def publish_catalog(send_worker_command: CommandSender) -> CatalogPublisher:
    """Imports one batch, as the seeder and the 1C consumer both do.

    Sent through the worker's container rather than the bot's, and that is the
    point of arranging it here: an import is nobody's request, so it must not
    need an identity to run.
    """

    async def publish(snapshot: CatalogSnapshot) -> None:
        await send_worker_command(ImportCatalogCommand(snapshot=snapshot))

    return publish


@pytest.fixture()
def sweep_catalog(send_worker_command: CommandSender) -> CatalogSweeper:
    """Finishes an import: whatever this batch did not mention is withdrawn."""

    async def sweep(batch_id: str, scope: CatalogScope) -> None:
        await send_worker_command(
            FinalizeCatalogImportCommand(batch_id=batch_id, scope=scope),
        )

    return sweep


@pytest.fixture()
def place_order(act: ActingSender) -> OrderPlacer:
    """Walks somebody through add, look at the cart, confirm what it showed."""

    async def place(
        person: Person,
        items: Mapping[int, int] | None = None,
    ) -> OrderPlacedView:
        for index, quantity in (items or {1: 1}).items():
            await act(
                person,
                AddToCartCommand(
                    product_id=make_product_id_value(index),
                    quantity=quantity,
                ),
            )

        cart = await act(person, GetCartQuery())
        return await act(person, a_checkout(cart))

    return place
