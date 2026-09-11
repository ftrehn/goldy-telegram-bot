"""Integration test topology.

    PostgresContainer ──► PostgresConfig ──┬──► telegram container ──► MockedBot
                                           │
    InMemoryBroker + TestRabbitBroker ─────┴──► worker container   ──► relay task

Both containers are the production ones, built by ``make_telegram_container`` and
``make_worker_container``. Nothing is swapped below the ports: the database is
real, the mappings are real, the mediator and its pipelines are real. Only the
two transports the tests cannot reach are replaced, and both are replaced with
the libraries' own in-process implementations rather than with stubs of ours —
so the adapters under test stay the production ones.

Two containers rather than one assembled for testing, because the split is a
design decision worth keeping honest: the bot cannot resolve ``OutboxPublisher``
and the worker cannot resolve ``IdentityProvider``. A single test container
would resolve both and quietly stop testing that.

Every test starts against empty tables. Truncating is what keeps a test from
passing on rows another one left behind.
"""

import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
from collections.abc import AsyncIterator, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest
from dishka import AsyncContainer, Scope
from dishka.integrations.taskiq import setup_dishka as setup_taskiq_dishka
from faststream.rabbit import RabbitBroker, TestRabbitBroker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import clear_mappers
from sqlalchemy.pool import NullPool
from taskiq import AsyncBroker, InMemoryBroker, ScheduleSource
from taskiq.schedule_sources import LabelScheduleSource
from testcontainers.community.postgres import PostgresContainer

from goldy.application.common.mediator.markers import BaseRequest
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.ports.outbox import (
    OutboxCommandGateway,
    OutboxMessage,
)
from goldy.application.common.ports.transaction_manager import TransactionManager
from goldy.application.common.ports.users import UserCommandGateway
from goldy.domain.users.entities.user import User
from goldy.domain.users.factories.user_factory import UserFactory
from goldy.domain.users.values.block_reason import BlockReason
from goldy.domain.users.values.user_id import UserId
from goldy.domain.users.values.user_role import UserRole
from goldy.infrastructure.persistence.models.base import metadata
from goldy.setup.bootstrap.setups.configs_setup import (
    SharedConfigs,
    make_telegram_container_context,
    make_worker_container_context,
)
from goldy.setup.bootstrap.setups.database_setup import setup_map_tables
from goldy.setup.bootstrap.setups.task_manager_setup import setup_task_manager_tasks
from goldy.setup.configs.admin_config import AdminConfig
from goldy.setup.configs.alchemy_config import SQLAlchemyConfig
from goldy.setup.configs.catalog_config import CatalogConfig
from goldy.setup.configs.notification_config import NotificationConfig
from goldy.setup.configs.postgres_config import PostgresConfig
from goldy.setup.configs.taskiq_config import TaskIQConfig
from goldy.setup.configs.telegram_config import TelegramConfig
from goldy.setup.ioc.containers import make_telegram_container, make_worker_container
from tests.integration.arrange import (
    CommandSender,
    OutboxSeeder,
    UserBlocker,
    UserSeeder,
)
from tests.integration.brokers import PublishedEvents, make_recording_event_broker
from tests.integration.telegram.mocked_bot import RecordingBot
from tests.unit.factories.config_factories import (
    create_rabbitmq_config,
    create_redis_config,
)
from tests.unit.factories.domain_factories import (
    ADMIN_PHONE,
    CUSTOMER_PHONE,
    TELEGRAM_ACCOUNT_ID,
    make_account,
    make_registration,
)
from tests.unit.factories.outbox_factories import make_outbox_message
from tests.unit.factories.shop_factories import PRICE_TYPE_ID

POSTGRES_IMAGE: Final[str] = "postgres:17-alpine"
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
MIGRATION_CHECK_DB_NAME: Final[str] = "goldy_migration_check"
"""The database the migrations are replayed into from nothing."""

# Session-scoped async fixtures and the tests must share one loop, or the engine
# is created on a loop that is gone by the time a test uses it.
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """One database for the whole session — starting a container per test is slow."""
    with PostgresContainer(POSTGRES_IMAGE, driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="session")
def postgres_config(postgres_container: PostgresContainer) -> PostgresConfig:
    return PostgresConfig(
        user=postgres_container.username,
        password=postgres_container.password,
        host=postgres_container.get_container_host_ip(),
        port=int(postgres_container.get_exposed_port(5432)),
        db_name=postgres_container.dbname,
        driver="asyncpg",
    )


@pytest.fixture(scope="session")
def alchemy_config() -> SQLAlchemyConfig:
    return SQLAlchemyConfig(
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )


@pytest.fixture(scope="session")
def shared_configs(
    postgres_config: PostgresConfig,
    alchemy_config: SQLAlchemyConfig,
) -> SharedConfigs:
    """What both processes read, with the two unreachable services pointed nowhere.

    Redis and RabbitMQ are configured but never connected to: the broker objects
    handed to the container are in-process ones, and these configs exist only
    because ``configs_provider`` supplies them from context and dishka validates
    the whole graph when the container is built.
    """
    return SharedConfigs(
        postgres=postgres_config,
        alchemy=alchemy_config,
        redis=create_redis_config(),
        rabbitmq=create_rabbitmq_config(),
        taskiq=TaskIQConfig(),
        admin=AdminConfig(phone_numbers=ADMIN_PHONE),
        catalog=CatalogConfig(default_price_type_id=PRICE_TYPE_ID),
    )


@pytest.fixture(scope="session")
def telegram_config() -> TelegramConfig:
    """A bot with no Redis behind it.

    Memory storage and memory isolation are exactly what the flags exist for,
    and a single test process is the one place where "safe for one replica only"
    is not a caveat.
    """
    return TelegramConfig(
        bot_token=RecordingBot.TOKEN,
        use_redis_storage=False,
        use_redis_event_isolation=False,
        drop_pending_updates=False,
    )


@pytest.fixture(scope="session", autouse=True)
def _mapped_tables() -> Iterator[None]:
    """Links the domain classes to their tables, once.

    ``map_imperatively`` raises on a class that is already mapped, so this is a
    session fixture rather than something each container does — two containers
    are built here and only one mapping may exist.
    """
    setup_map_tables()
    yield
    clear_mappers()


@pytest.fixture(scope="session")
def _schema(postgres_config: PostgresConfig) -> None:
    """Builds the schema by running the migrations that will run in production.

    Not from ``metadata.create_all``: goldy keeps its migrations in the
    repository and generates them with a skill, so the failure worth catching is
    a migration that has fallen behind the mappers. Building the schema from the
    mappers themselves would hide precisely that.
    """
    _upgrade_to_head(postgres_config)


@pytest.fixture(scope="session")
async def migrated_database(
    postgres_config: PostgresConfig,
) -> AsyncIterator[AsyncEngine]:
    """A database of its own, taken from nothing to head by the migrations.

    Separate from the one every other test runs against, and that separation is
    the whole point. "The migrations build this schema out of an empty
    database" can only be shown on an empty database, and the session one has
    been migrated already — asking it would answer with the answer from before.

    The engine is built here rather than taken from a container because no
    container is pointed at this database: what is under test is the schema,
    not anything that reads it. ``NullPool`` because two statements are run
    against it in total and a pool would outlive the test that wanted it.
    """
    fresh = replace(postgres_config, db_name=MIGRATION_CHECK_DB_NAME)

    await _recreate_database(postgres_config, MIGRATION_CHECK_DB_NAME)
    _upgrade_to_head(fresh)

    engine = create_async_engine(fresh.uri, poolclass=NullPool)
    yield engine
    await engine.dispose()


def _upgrade_to_head(config: PostgresConfig) -> None:
    """Runs the migrations the way a deployment runs them, and reports failure.

    A subprocess because ``migrations/env.py`` calls ``setup_map_tables()`` on
    import, and this process has already done so.
    """
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env={**os.environ, **_postgres_env(config)},
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(
            f"alembic upgrade head against '{config.db_name}' failed:\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}",
        )


async def _recreate_database(config: PostgresConfig, db_name: str) -> None:
    """Drops and creates a database beside the one the tests use.

    ``AUTOCOMMIT`` because Postgres refuses ``CREATE DATABASE`` inside a
    transaction block, and the identifier is quoted rather than bound because
    DDL takes no parameters — it is a constant of this module, not input.
    """
    engine = create_async_engine(config.uri, isolation_level="AUTOCOMMIT")

    async with engine.connect() as connection:
        await connection.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        await connection.execute(text(f'CREATE DATABASE "{db_name}"'))

    await engine.dispose()


def _postgres_env(config: PostgresConfig) -> dict[str, str]:
    """The variables ``PostgresEnvSourceFactory`` maps, pointed at the container."""
    return {
        "POSTGRES_USER": config.user,
        "POSTGRES_PASSWORD": config.password,
        "POSTGRES_HOST": config.host,
        "POSTGRES_PORT": str(config.port),
        "POSTGRES_DB": config.db_name,
        "POSTGRES_DRIVER": config.driver,
    }


@pytest.fixture(scope="session")
def bot() -> RecordingBot:
    """The bot the container hands to every handler, wired to a fake transport."""
    return RecordingBot()


@pytest.fixture(scope="session")
async def telegram_container(
    shared_configs: SharedConfigs,
    telegram_config: TelegramConfig,
    bot: RecordingBot,
) -> AsyncIterator[AsyncContainer]:
    container = make_telegram_container(
        make_telegram_container_context(shared_configs, telegram_config, bot),
    )
    yield container
    await container.close()


@pytest.fixture(scope="session")
def _recording_broker() -> tuple[RabbitBroker, PublishedEvents]:
    """The broker and the record its subscriber writes to, created together.

    One fixture for both because the subscriber closes over the recorder: split
    into two independent fixtures, a test would read an empty record while
    events piled up in an object nobody could see.
    """
    return make_recording_event_broker()


@pytest.fixture(scope="session")
def published(
    _recording_broker: tuple[RabbitBroker, PublishedEvents],
) -> PublishedEvents:
    return _recording_broker[1]


@pytest.fixture(scope="session")
async def event_broker(
    _recording_broker: tuple[RabbitBroker, PublishedEvents],
) -> AsyncIterator[RabbitBroker]:
    """The relay's transport, routing in process instead of over AMQP."""
    broker, _ = _recording_broker

    async with TestRabbitBroker(broker) as test_broker:
        yield test_broker


@pytest.fixture(scope="session")
def taskiq_broker() -> AsyncBroker:
    """The production tasks, on a broker that runs them in this process.

    Registered through ``setup_task_manager_tasks`` rather than by hand: the
    failure this catches is a task the scheduler names and nobody registered,
    and a test that registered its own would never see it.
    """
    broker: Final[AsyncBroker] = InMemoryBroker()
    setup_task_manager_tasks(broker)
    return broker


@pytest.fixture(scope="session")
def schedule_source(taskiq_broker: AsyncBroker) -> ScheduleSource:
    """Reads the cron declared at registration, the way the scheduler does."""
    return LabelScheduleSource(taskiq_broker)


@pytest.fixture(scope="session")
async def worker_container(
    shared_configs: SharedConfigs,
    taskiq_broker: AsyncBroker,
    schedule_source: ScheduleSource,
    event_broker: RabbitBroker,
) -> AsyncIterator[AsyncContainer]:
    """The worker's container, wired to its broker the way ``worker_app`` does."""
    container = make_worker_container(
        make_worker_container_context(
            shared_configs,
            taskiq_broker,
            schedule_source,
            event_broker,
            NotificationConfig(bot_token=RecordingBot.TOKEN),
        ),
    )
    setup_taskiq_dishka(container, broker=taskiq_broker)

    await taskiq_broker.startup()
    yield container
    await taskiq_broker.shutdown()
    await container.close()


@pytest.fixture(scope="session")
async def engine(worker_container: AsyncContainer) -> AsyncEngine:
    """A container's own engine, so tests and the app share one database."""
    return await worker_container.get(AsyncEngine)


@pytest.fixture()
async def clean_tables(
    _schema: None,
    engine: AsyncEngine,
    published: PublishedEvents,
) -> None:
    """Empties every table and the publish record before each test.

    Requested with ``pytest.mark.usefixtures`` rather than as an argument: the
    test never touches its value, only its effect. Truncating up front rather
    than cleaning up afterwards means a test that fails leaves its rows behind
    to be inspected.

    The publish record is cleared here too, and not because a test asked. The
    broker is session-scoped, so events published by one test would otherwise
    still be visible to every test after it.
    """
    tables = ", ".join(table.name for table in metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    published.forget()


@pytest.fixture()
async def arrange_scope(
    worker_container: AsyncContainer,
) -> AsyncIterator[AsyncContainer]:
    """A request scope for arranging state, separate from the one under test.

    Taken from the worker's container on purpose. Arranging state must not
    depend on who is acting, and that container has no ``IdentityProvider`` — so
    an arrangement that started to need one would fail to resolve here rather
    than quietly borrow the identity of whoever the test is pretending to be.
    """
    async with worker_container(scope=Scope.REQUEST) as request_container:
        yield request_container


@pytest.fixture()
async def arrange_transaction(arrange_scope: AsyncContainer) -> TransactionManager:
    resolved: TransactionManager = await arrange_scope.get(TransactionManager)
    return resolved


@pytest.fixture()
async def arrange_users(arrange_scope: AsyncContainer) -> UserCommandGateway:
    resolved: UserCommandGateway = await arrange_scope.get(UserCommandGateway)
    return resolved


@pytest.fixture()
async def arrange_outbox(arrange_scope: AsyncContainer) -> OutboxCommandGateway:
    resolved: OutboxCommandGateway = await arrange_scope.get(OutboxCommandGateway)
    return resolved


@pytest.fixture()
async def arrange_user_factory(arrange_scope: AsyncContainer) -> UserFactory:
    resolved: UserFactory = await arrange_scope.get(UserFactory)
    return resolved


@pytest.fixture()
def seed_user(
    arrange_users: UserCommandGateway,
    arrange_user_factory: UserFactory,
    arrange_transaction: TransactionManager,
) -> UserSeeder:
    """Puts a registered person in the database, committed before the test reads.

    Written against the ports, not against SQLAlchemy: what a test arranges is
    "this person exists", and how they get there is the container's business.

    The role is applied after registration because that is the only way it can
    happen in production too — everyone starts as a customer.
    """

    async def seed(
        phone_number: str = CUSTOMER_PHONE,
        external_id: str = TELEGRAM_ACCOUNT_ID,
        role: UserRole = UserRole.CUSTOMER,
        username: str | None = "c3equalz",
    ) -> User:
        user = arrange_user_factory.create(
            make_registration(
                phone_number=phone_number,
                account=make_account(external_id=external_id, username=username),
            ),
        )
        if role is not UserRole.CUSTOMER:
            user.assign_role(role)

        await arrange_users.add(user)
        await arrange_transaction.commit()
        return user

    return seed


@pytest.fixture()
def block_user(
    arrange_users: UserCommandGateway,
    arrange_transaction: TransactionManager,
) -> UserBlocker:
    """Blocks somebody without an administrator having to do it.

    Through the aggregate rather than an ``UPDATE``, so the row that lands is
    the one a real block would leave — status and reason set together.
    """

    async def block(user_id: UserId, reason: str = "Тестовая причина") -> None:
        loaded = await arrange_users.by_id(user_id)
        assert loaded is not None
        loaded.block(BlockReason(value=reason))
        await arrange_transaction.commit()

    return block


@pytest.fixture()
def store_outbox_messages(
    arrange_outbox: OutboxCommandGateway,
    arrange_transaction: TransactionManager,
) -> OutboxSeeder:
    """Commits pending messages before the test reads them."""

    async def store(count: int) -> list[OutboxMessage]:
        messages = [make_outbox_message() for _ in range(count)]
        for message in messages:
            await arrange_outbox.add(message)
        await arrange_transaction.commit()
        return messages

    return store


@pytest.fixture()
def send_worker_command(worker_container: AsyncContainer) -> CommandSender:
    """Dispatches a command the way the worker's task does: one request scope each.

    A scope per command on purpose — every worker step commits independently,
    which is what lets a failed relay still leave the rows it did not publish.
    """

    async def send[TResponse](request: BaseRequest[TResponse]) -> TResponse:
        async with worker_container(scope=Scope.REQUEST) as request_container:
            sender: Sender = await request_container.get(Sender)
            response: TResponse = await sender.send(request)
            return response

    return send


@pytest.fixture()
def dishka_container(worker_container: AsyncContainer) -> AsyncContainer:
    """The container the ``inject`` decorator opens a request scope from.

    Named for the keyword ``inject`` looks up. Tests never reference it
    directly, they declare ``FromDishka[SomePort]`` instead — and a module that
    needs the bot's container overrides this fixture with that one.
    """
    return worker_container
