# goldy

A shop bot. It runs in Telegram today and MAX later, takes orders from
customers, and reads its product catalog out of a 1C installation on another
server over RabbitMQ.

**1C is read-only.** The catalog comes from it; customers, orders and everything
else belong to this service. There is no counterparty, no synchronisation back,
and no 1C concept inside the domain.

## Project structure

```
src/goldy/
  domain/          business rules; imports nothing from other layers
  application/     use cases, ports, pipelines
  infrastructure/  adapters implementing the ports
  presentation/    Telegram handlers, dialogs, middlewares
  setup/           configs, bootstrap, DI containers
  telegram_bot.py  bot entry point
  worker_app.py    taskiq worker entry point
  scheduler_app.py taskiq scheduler entry point
  catalog_seed_app.py  catalog seeder entry point — a JSON snapshot, no messenger
tests/
  unit/            domain + application + our own infrastructure logic
  integration/     anything crossing a process boundary
```

Rules:

- Dependencies flow inward: `presentation → application → domain`.
- `domain` contains only business logic and imports nothing from other layers.
- `infrastructure` implements interfaces defined in `application`, and must not
  import `setup` — the composition root depends on adapters, never the reverse.
- These are **enforced**: `just import-linter` fails the build. Read
  `.importlinter` before moving a module.

## Vocabulary

`CONTEXT.md` is the glossary and the single authority on wording. Use its terms
rather than inventing synonyms. The ones that carry the most weight:

- **User** — a *person*, not an account. Someone writing from Telegram today and
  MAX tomorrow is one `User` with two `MessengerAccount`s, one order history and
  one phone number. See [ADR-0001](docs/adr/0001-single-user-across-messengers.md).
- **Phone number** — the identity of a person, stored strictly in E.164. Two
  accounts are recognised as the same human because their numbers compare equal.
- **External id** — the id a platform gave its own account. Unique only within
  that platform, so it never identifies a user on its own.
- **Linking** — attaching a second platform to an existing person, which happens
  automatically when the number they share is already known.
- **Notification target** — which platform gets order updates, once more than
  one is linked.

`docs/design/user.md` records the decisions behind the user model and why the
rejected alternatives were rejected.

## Domain layer

```
domain/
  common/          Entity, Aggregate, ValueObject, Event, BaseDomainService
    values/        Money, Currency, Quantity — values no single aggregate owns
  users/
    entities/      User (aggregate), MessengerAccount
    values/        ValueObject subclasses and the NewType ids
    services/      AccessService and the authorization specifications
    factories/     UserFactory — exists only because ids need a generator
    ports/         Protocols the infrastructure implements
    registration.py  parameter object for User.register
    errors.py
    events.py
  catalog/
    values/        SourceId and its subclasses, Sku, ProductName,
                   UnitOfMeasure, PricedProduct
    errors.py      no entities and no aggregate — see below
  carts/
    entities/      Cart (aggregate), CartLine
    values/, factories/, ports/, errors.py
  orders/
    entities/      Order (aggregate), OrderLine
    values/, ports/, errors.py, events.py
    services/      CheckoutService and authorization/ (IsOrderOwner, CanManageOrders)
    checkout.py    parameter object for CheckoutService.checkout
    placement.py   parameter object for Order.place
    status_transitions.py  the lifecycle table
```

**`catalog` has no aggregate on purpose.** The catalog is a read-only
projection of 1C; the bot never creates, changes or deletes a product, so there
is no invariant for an aggregate to protect. What lives here is the handful of
values an order has to keep as a snapshot, and a `ProductId` the domain reads
but never mints — which is why this package has no id generator and must not
grow one.

**Domain packages depend in one direction only**: `catalog ← users ← carts ←
orders`. `orders` reaching into `carts` (checkout starts from one) and into
`users` (`UserId`, `FullName`, `PhoneNumber`) is the direction that is allowed;
nothing in `users` or `carts` may import `orders`. This is **enforced** by the
`domain_package_layers` contract, so a cycle fails the build rather than
waiting for somebody to notice it.

Owning an order is therefore a `Permission` like every other access rule, and
not a method on the aggregate. `OrderAccessContext` lives in
`domain/orders/services/authorization/` and carries `order_customer_id: UserId`
rather than an `Order`, so nothing in `users` learns about orders and no cycle
appears. One mechanism only — with ownership half method and half
specification, `AnyOf(IsOrderOwner(), CanManageOrders())` could not be written
at all.

Where behaviour goes:

- **On the aggregate** — anything decidable from its own fields. Linking and
  unlinking platforms, blocking, editing the profile, assigning a role. The
  aggregate records its own events into `events_collection`.
- **In a domain service** — what the aggregate lacks. `UserFactory` because a
  new user needs a generated id; `AccessService` because "may this person act on
  that one" needs two aggregates.

`AccessService` deliberately changes nothing and records no events. It answers
whether a subject is allowed; the aggregate performs the change and enforces its
own transitions. Both halves are needed and neither is the other's job.

Value objects inherit `ValueObject` and implement `_validate()` with
`@override`. They never override `__post_init__`.

**Value objects are keyword-only** — except those stored as a SQLAlchemy
`composite`, which the ORM rebuilds positionally. Today that is `FullName`,
`UserPreferences`, `Money`, `Recipient` and `UnitOfMeasure`. Do not add
`kw_only=True` to those without changing the mapping; each one says so in its
own docstring, and `test_money_is_built_positionally` and
`test_a_unit_of_measure_is_built_positionally` pin the positional call down.

## Authorization

Rules are objects, not `if` branches:

```python
access_service.authorize(
    CanManageSubordinate(),
    context=UserManagementContext(subject=actor, target=target),
)
target.block(reason)
```

`SUBORDINATE_ROLES` is the single source of truth for who may act on whom. Two
rules fall out of it for free, because nobody is their own subordinate: an
administrator cannot touch another administrator, and nobody can block
themselves. Do not re-state either as a separate check.

`ADMIN` appears in no one's subordinate set, so **the role cannot be granted
through the bot at all**. The first administrators come from
`GOLDY_ADMIN_PHONE_NUMBERS`, applied both at startup (`SeedAdminsCommand`) and
at registration time, so an administrator never has to wait for a restart.

## Application layer

```
application/
  commands/users/<use_case>/{command.py,handler.py}
  queries/users/<use_case>/{query.py,handler.py}
  common/
    mediator/      RequestHandler, PipelineHandler, markers, Sender
    ports/         every interface the infrastructure implements
    services/      UserProvider
    views/         read models returned to presentation
    query_params/  Pagination, SortingOrder, UserFilters
  pipelines/       TransactionPipeline, EventsPipeline
```

Handlers:

- Inherit `CommandHandler[TCommand, TResponse]` or `QueryHandler[...]`.
- Take collaborators in `__init__` and store them as `Final`.
- Implement `handle()` with `@override`.
- **Never catch `Exception`** — catch `AppError` or a specific subclass.
- **Never swallow a failure to report success**: the transaction pipeline would
  commit partially applied work.

Gateways, not repositories. `UserCommandGateway` hands back whole aggregates;
`UserQueryGateway` returns views and never aggregates. The query gateway is a
DAO and a `Protocol` on purpose — a caching decorator over it is invisible to
every handler.

Two rules **cannot** be enforced in the domain: that a phone number belongs to
one user, and that a messenger account does too. Both span aggregates and any
check-by-reading loses to a concurrent registration. Unique indexes hold them,
`SqlAlchemyUserCommandGateway.add` flushes so the clash surfaces as
`UserAlreadyExistsError`, and the caller retries once.

## Pipelines and the mediator

Commands go through `Sender` (`MediatorImpl`), which wraps the handler in the
pipelines registered for its type:

```python
registry.add_pipeline_handlers(Command, TransactionPipeline, EventsPipeline)
```

**Registration order is execution order.** The transaction opens first and
commits last, with events drained inside it. Reversed, events would be written
to the outbox after the commit and stop being atomic with the state change they
describe. Registering against the `Command` marker means a command added later
cannot escape the pipelines.

Queries are deliberately uncovered — they mutate nothing.

## Events and the outbox

Aggregates record events into a request-scoped `EventsCollection`.
`EventsPipeline` drains it and hands the events to `EventBus`, which writes them
to the outbox table **in the same transaction**. The scheduler fires
`RelayOutboxCommand`; the worker publishes to a RabbitMQ topic exchange.

Delivery is at-least-once, so consumers must be idempotent — they key off
`OutboxMessage.id`, which is stable across retries. That key is enforced by the
`inbox_messages` table: `InboxGateway.claim` is one
`INSERT ... ON CONFLICT (id) DO NOTHING RETURNING id`, and the row commits in
the same transaction as whatever the message caused. A handler that raises gives
the claim back and the message is redelivered; a handler that decides there is
nothing to do keeps it, because the answer will not be different next time.

The consumer side lives in `infrastructure/task_manager/consumers/`, which
`.importlinter` already allows to reach into `application.commands`. One durable
queue per event, bound by routing key — the event's class name — so one poisoned
message cannot hold up a different kind of message behind it.

Events carry primitives, not value objects: they are serialised, and their
`event_id` / `event_date` are stamped at construction because the outbox row is
keyed and ordered by them.

## Infrastructure

- **Postgres** + SQLAlchemy asyncio + asyncpg, **imperative mapping**
  (`persistence/models/`). The domain knows nothing about the ORM.
- **taskiq** over RabbitMQ (`taskiq-aio-pika`), Redis result backend.
- **FastStream** over RabbitMQ for domain events — the relay publishes to the
  `domain_events` topic exchange, and the notification consumers in
  `infrastructure/task_manager/consumers/` bind to it. The worker process is
  both ends, which is why it **starts** the event broker rather than only
  connecting it: a subscriber registered on a merely connected broker never
  consumes anything.
- **dishka** for DI, **aiogram** + **aiogram-dialog** for Telegram.
- **adaptix** for aggregate → view mapping.

Value objects reach the database through `TypeDecorator`s in
`persistence/models/types.py`. Multi-field value objects are a `composite`.

Adapters wrap third-party errors in `InfrastructureError` subclasses. Never let
a library exception escape an adapter.

Mappers come in two kinds, and the split is about their input:

| Mapper | Port lives in | Written with |
|---|---|---|
| `User` → `UserView` | `application/common/ports/mappers` | adaptix |
| `RowMapping` → `UserView` | `infrastructure/mappers` | by hand |

The second keeps its port in infrastructure because its input is a
`sqlalchemy.RowMapping` — declaring it among the application ports would put the
ORM in the layer meant not to know one.

## Dependency injection

Providers are split by concern in `setup/ioc/providers/`, and **containers are
assembled per process** in `setup/ioc/containers/`:

| Container | Gets |
|---|---|
| `make_telegram_container` | core + interactive + Telegram + aiogram |
| `make_worker_container` | core + task manager + outbox handlers + notifications + taskiq |
| `make_catalog_seed_container` | core + the catalog source, and nothing that expects a person |

Handlers are grouped by **what they need**, not who calls them. Anything needing
an `IdentityProvider` is in `user_handlers_provider`, which the worker does not
get — a background task is nobody's request. dishka validates the whole graph
when a container is built, so a handler in the wrong group fails at startup
rather than halfway through a task. This has already caught two real mistakes;
do not merge the groups to make a wiring error go away.

`notifications_provider` is the same rule applied to a secret rather than to an
identity. It carries the Bot API client and the token behind it, and only the
worker gets it: the bot answers whoever wrote to it, while the worker writes to
people who did not. `configs_provider` still hands `TelegramConfig` and
`NotificationConfig` to nobody — each process contributes its own.

MAX will be a fourth container over the same core, differing only in how it
answers "who is writing".

## Configuration

One dataclass per config in `setup/configs/`, one env source factory in
`setup/bootstrap/sources/`, one `dature` loader in `setup/bootstrap/loaders/`.
Configs are loaded at startup by `load_shared_configs()` and handed to the
container as context — a container that read the environment itself could not be
built for a test.

Validation belongs in the loader, as `V.root(...)` predicates with messages that
name the environment variable. A bad environment must fail at startup listing
every offending variable, not on the first update that needs the setting.

## Presentation layer

```
presentation/telegram/
  common/        text_keys, keyboards, replying, widgets, locale_manager, locales_path
  filters/       ChatTypeFilter, IsStaffFilter
  handlers/
    common/      help, fallback
    start/       registration
    profile/     dialog: states, getters, callbacks, dialogs, handler
    admin/       dialog: states, getters, callbacks, dialogs, handler
    errors.py    the one error handler
    routers.py   ROUTERS and DIALOGS, in matching order
  locales/       Fluent .ftl files, ru and en — a data directory, not a package
  middlewares/   AuthMiddleware, TimingMiddleware
```

**Middleware order is load-bearing**, and `setup_telegram_bot_middlewares`
documents it: dishka → timing → auth → i18n. Authentication needs the container
dishka provides; i18n needs the user authentication loads.

The **auth gate is fail-closed**. Anything that is not `/start` or a shared
contact stops there unless a user was found, so a router added later is covered
without anybody remembering to cover it. Blocked users are stopped in the same
place.

**Every Fluent key lives in `common/text_keys.py`.** No literals at call sites —
the same key is often needed twice, and two literals spelled differently is how
one starts pointing at a message nobody wrote.

Domain errors become messages in one place: `handlers/errors.py`, keyed by type
with an MRO walk so a new subclass of a handled error is covered automatically.

Commands without state are ordinary handlers; anything with screens is an
aiogram-dialog. Dialog getters take what they need from the middleware data as
parameters — `user: UserView` works, because aiogram-dialog passes the update
data in.

## Testing rules (mandatory)

- Tests mirror `src/` structure, under `unit/` and `integration/`.
- **Arrange / Act / Assert**, separated by blank lines.
- Name tests by behaviour and outcome, not by method name.
- A docstring on a test explains *why the behaviour matters*. Most need none.
- **Fixtures live only in `conftest.py`**, one per level. Builders live in
  `tests/unit/factories/`, stubs in `tests/unit/stubs/`. Never define either
  next to a test.

**Do not test libraries.** Building a dishka container to assert dishka wires it
is a test of dishka. Test the decisions we made: phone normalisation, the
registration branches, the role hierarchy, the aggregate's invariants.

Integration tests need **Docker** (testcontainers Postgres) and name ports,
never implementations.

## Tooling & standards (mandatory)

- Python **3.14**, package manager **uv**, task runner **just**
- Formatting & linting: **ruff** (`select = ["ALL"]`, line length 90)
- Type checking: **mypy**, strict; everything fully annotated
- Testing: **pytest**

Conventions this project insists on:

- **No `from __future__ import annotations`.** PEP 649 handles it.
- **Constructor parameter types must be importable at runtime** — dishka and
  adaptix resolve them then. Do not move them under `if TYPE_CHECKING`.
  (`TC001`/`TC002`/`TC003` are disabled for this reason.)
- Store injected collaborators as `Final`.
- `@override` on every overriding method, including `_validate`.
- Avoid `typing.Any`.
- **Avoid `# noqa` and `# type: ignore`.** Prefer changing the code: a signature
  that trips `PLR0913` usually wants a parameter object. If a rule is genuinely
  wrong for a whole class of files, add a scoped `per-file-ignores` entry with a
  comment saying why.
- **Comments are a last resort; prefer docstrings.** If a decision needs
  explaining, explain it where the thing is defined.

```sh
just lint              # ruff format + ruff check + codespell
just mypy              # type check
just static-analysis   # mypy + bandit + semgrep + import-linter
just pre-commit-all    # everything the hooks run
just test-unit         # fast, no Docker
just migrate           # alembic upgrade head
```

## Code quality rules (mandatory)

**After writing ANY code**, run in this order:

```sh
just lint
just mypy
just pre-commit-all
uv run --active pytest tests/unit -q
```

Fix everything before moving on. Never claim work is done without running the
tests and reporting how many ran.

## Things that have bitten us

Read the relevant entry before touching that area.

**Persistence**

- **`composite` column order must match the dataclass field order.** Composites
  are rebuilt positionally, so swapping two columns swaps the values silently,
  with nothing failing until somebody reads a profile.
- **`events_collection` is not a column.** SQLAlchemy leaves it unset on loaded
  aggregates, so `SqlAlchemyUserCommandGateway` injects the request-scoped one on
  every read. Without it the first method that records an event fails on a
  missing attribute, far from the load that caused it.
- **`MessengerAccount` must stay a mutable dataclass.** SQLAlchemy assigns to its
  attributes when loading a row; a frozen value object cannot be mapped.
- **`setup_map_tables()` must run exactly once per process** — `map_imperatively`
  raises on an already-mapped class.
- **Alembic needs `recursive_version_locations = true`** — revisions live in
  dated subdirectories, and without it alembic silently finds none.
- **The initial migration was written by hand**, from DDL compiled off the
  metadata. Run `just migration "check"` against a real database before the
  first deploy; the diff should be empty.

**Mapping**

- **adaptix links fields, not paths.** `P[User].full_name.first_name` is
  rejected, so every value object needs its own `link_function`. `id` needs one
  too — `UserId` is a `NewType`, which adaptix does not see through.

**Wiring**

- **dishka validates the whole graph at build time**, and that is the feature.
  A handler needing `IdentityProvider` placed in the shared providers makes the
  *worker* container refuse to build. Move the handler, do not merge the groups.
- **Infrastructure must not import `setup`.** `StaticAdminRegistry` takes parsed
  numbers rather than an `AdminConfig` for exactly this reason.

**Telegram**

- **Telegram lets a person forward somebody else's contact card.** The
  `request_contact` button is not proof of ownership, and registration links
  accounts by number — so an unchecked card is a way into someone else's
  account. `contact.user_id == message.from_user.id` is the security boundary of
  the whole bot.
- **Do not compare message text to `"/start"`.** Telegram delivers
  `/start@goldy_bot` in groups and `/start <payload>` for deep links. Use
  aiogram's `CommandStart()`, which needs the `Bot` to strip the mention.
- **`callback_query.message` may be an `InaccessibleMessage`.** Answer the
  callback instead of writing into it; `common/replying.py` does this in one
  place for everybody.
- **A Fluent placeholder with no argument does not render as text.** It raises.
  `notification-order-status-changed` missing its `$status` produces no message
  at all and one line in a log, so notification texts are verified by *rendering*
  every key with the arguments its handler builds — see
  `tests/unit/infrastructure/adapters/notifications/`. Read `.ftl` files by eye
  and you will ship a message nobody receives.
- **The locales directory must not be a Python package.** An `__init__.py` puts
  a `__pycache__` beside the languages, and the Fluent core reads that as a
  locale and then fails to find any `.ftl` in it.
- **Resolve the locales path with `importlib.resources`.** Anything relative to
  the working directory works until the service is installed as a wheel.
- **The auth gate handles its own `AppError`.** It runs before i18n, so a
  failure there would reach an error handler with no context to render with, and
  the person would get nothing at all.

**Testing**

- **Never build a mapped entity at module level in a test.** Collection imports
  every test module before the first test runs, so the instance is created
  before `setup_map_tables()` has mapped its class; reading a composite off it
  afterwards raises a missing `_sa_instance_state`. The suite passes when unit
  tests run alone and fails when they run beside the integration ones, which is
  the shape of failure that costs the most to find. Build entities inside the
  test or in a fixture.
- **Run `pytest tests` before claiming green, not `tests/unit` and
  `tests/integration` separately.** CI runs them in one process, and imperative
  mapping is process-wide state — the split hides exactly the bug above.

**Tooling**

- **`PLR0913` counts keyword-only arguments.** Six named parameters trip it even
  when every call site is readable. That is why `User.register` takes a
  `Registration` parameter object.
- **detect-secrets reports Windows paths with backslashes**, so a `migrations/`
  exclusion silently misses every migration and flags each revision hash.
  Patterns in `.pre-commit-config.yaml` match both separators.
- **`RUF029` fires on dialog getters and callbacks.** They are async by
  aiogram-dialog's contract even with nothing to await; the exemption is scoped
  in `ruff.toml`.
