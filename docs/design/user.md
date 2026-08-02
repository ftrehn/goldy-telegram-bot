# Дизайн: пользователь

Проектный документ для агрегата `User` и его обвязки. Термины — в
[CONTEXT.md](../../CONTEXT.md), необратимое решение об identity — в
[ADR-0001](../adr/0001-single-user-across-messengers.md).

## Принятые решения

| Решение | Значение |
| --- | --- |
| Identity | Один `User` на человека, `MessengerAccount` внутри агрегата |
| Телефон | Обязателен, подтверждён кнопкой мессенджера, `not Optional` |
| Вторая площадка | Автопривязка к существующему `User` по совпадению телефона |
| 1С | Из 1С только читаем каталог. В `User` нет контрагента и нет синхронизации |
| Роли | Одно поле `role: UserRole` — CUSTOMER / MANAGER / ADMIN |
| Блокировка | `status` + причина, блокируется человек целиком |
| Адреса доставки | Отложены до заказов — аддитивное изменение |

## Где что лежит

Граница между агрегатом и доменным сервисом здесь одна:

- **В агрегате** — всё, что можно проверить, глядя только на его собственные
  поля. Привязка и отвязка площадок, блокировка, смена профиля и настроек,
  назначение роли. Агрегат сам записывает свои события в `events_collection`,
  который у него уже есть.
- **В доменном сервисе** — то, для чего агрегату чего-то не хватает:
  генератора идентификаторов (`UserService.create`) или второго агрегата и
  политики между ролями (`AccessService.authorize`).

Проверка «кому можно» и проверка «что при этом остаётся валидным» — разные
вещи и живут раздельно: `AccessService` решает, вправе ли менеджер трогать
покупателя, а `User.block()` не даёт заблокировать уже заблокированного.

## Изменение в существующем коде

У `Event` нужны значения по умолчанию, иначе каждое событие в агрегате тянуло
бы за собой `uuid4()` и `datetime.now(UTC)` руками. База уже `kw_only=True`,
поэтому дефолты не мешают наследникам объявлять обязательные поля.

```python
# src/goldy/domain/common/event.py
@dataclass(frozen=True, kw_only=True)
class Event:
    event_id: EventId = field(default_factory=lambda: EventId(uuid4()))
    event_date: datetime = field(default_factory=lambda: datetime.now(UTC))
```

`Aggregate.events_collection` остаётся как есть — он ровно для того, чтобы
агрегат записывал события сам. Один нюанс всплывёт на маппинге: это поле не
колонка, и SQLAlchemy не проставит его при загрузке из БД. Заполнять его будет
адаптер гейтвея, которому dishka отдаст ту же request-scoped коллекцию, что и
`EventsPipeline`.

## Структура

```
src/goldy/domain/
├── common/
│   ├── event.py                     # правка: дефолты
│   ├── value_object.py              # новое
│   └── services/base.py             # новое: DomainService
└── users/
    ├── entities/
    │   ├── user.py                  # агрегат, основное поведение
    │   └── messenger_account.py     # сущность внутри агрегата
    ├── values/
    │   ├── user_id.py
    │   ├── phone_number.py
    │   ├── full_name.py
    │   ├── messenger_platform.py
    │   ├── external_account_id.py
    │   ├── messenger_username.py
    │   ├── user_role.py
    │   ├── user_status.py
    │   ├── block_reason.py
    │   └── user_preferences.py
    ├── events.py
    ├── errors/
    │   ├── user.py
    │   ├── account.py
    │   └── access_service.py
    ├── ports/
    │   └── id_generator.py
    ├── factories/
    │   └── user_factory.py          # нужен UserIdGenerator
    └── services/
        ├── access_service.py        # политика: нужен субъект
        └── authorization/
            ├── base.py              # Permission, PermissionContext
            ├── composite.py         # AnyOf, AllOf
            ├── permission.py        # конкретные разрешения
            ├── role_hierarchy.py    # SUBORDINATE_ROLES
            └── constants.py
```

## Value objects

```python
# src/goldy/domain/common/value_object.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValueObject(ABC):
    def __post_init__(self) -> None:
        self._validate()

    @abstractmethod
    def _validate(self) -> None: ...
```

**`UserId`** — `NewType("UserId", UUID)`, как `EventId`.

**`PhoneNumber`** — единственный ключ человека, поэтому хранится строго в
каноническом виде E.164. Мессенджеры отдают номер по-разному (`79991234567`,
`+7 999 123-45-67`, `89991234567`), поэтому нормализация вынесена в отдельный
конструктор: сам `__init__` принимает только канонический вид, иначе сравнение
двух номеров перестанет быть надёжным, а на нём стоит вся автопривязка.

```python
@dataclass(frozen=True, slots=True, repr=False)
class PhoneNumber(ValueObject):
    value: str

    @classmethod
    def from_raw(cls, raw: str) -> Self:
        """Приводит к E.164: убирает разделители, 8XXXXXXXXXX -> +7XXXXXXXXXX."""

    def _validate(self) -> None:
        # ^\+[1-9]\d{7,14}$ иначе InvalidPhoneNumberFormatError
        ...
```

**`FullName`** — `first_name: str`, `last_name: str | None`. Пустое имя и длина
больше 100 — ошибка.

**`MessengerPlatform`** — `StrEnum`: `TELEGRAM`, `MAX`.

**`ExternalAccountId`** — обёртка над `str`. Именно строка, а не `int`: у
Telegram числовой id, у MAX формат может отличаться, а хранить их надо в одной
колонке.

**`MessengerUsername`** — `str | None`, меняется на стороне площадки, для нас
справочное поле.

**`UserRole`** — `StrEnum`: `CUSTOMER`, `MANAGER`, `ADMIN`. В отличие от
PixErase, свойств `is_assignable` / `is_changeable` здесь нет: что кому можно
менять, целиком описывает `SUBORDINATE_ROLES`, и второй источник правды на той
же теме разошёлся бы с ним при первой же правке.

**`UserStatus`** — `StrEnum`: `ACTIVE`, `BLOCKED`.

**`BlockReason`** — непустая строка до 500 символов.

**`UserPreferences`** — `notify_via: MessengerPlatform`,
`marketing_consent: bool`.

## Агрегат

```python
# src/goldy/domain/users/entities/user.py
@dataclass(eq=False, kw_only=True)
class User(Aggregate[UserId]):
    """Человек, пользующийся ботом. Опознаётся по телефону, а не по площадке."""

    phone_number: PhoneNumber
    full_name: FullName
    preferences: UserPreferences
    role: UserRole = field(default=UserRole.CUSTOMER)
    status: UserStatus = field(default=UserStatus.ACTIVE)
    block_reason: BlockReason | None = field(default=None)
    accounts: list[MessengerAccount] = field(default_factory=list)
```

### Создание

```python
    @classmethod
    def register(
        cls,
        *,
        user_id: UserId,
        events_collection: EventsCollection,
        phone_number: PhoneNumber,
        full_name: FullName,
        platform: MessengerPlatform,
        external_id: ExternalAccountId,
        username: MessengerUsername | None,
    ) -> Self:
        """Создаёт пользователя вместе с первым аккаунтом площадки.

        ``notify_via`` ставится в платформу, с которой человек пришёл.
        Записывает ``UserRegisteredEvent``.
        """
```

Пользователь всегда рождается с аккаунтом: отдельного шага «сначала создать,
потом привязать» нет, иначе в системе на мгновение появлялся бы недостижимый
человек. `user_id` приходит снаружи — его генерация единственное, чего агрегату
не хватает, и ради неё существует `UserService`.

### Площадки

```python
    def link_account(
        self,
        platform: MessengerPlatform,
        external_id: ExternalAccountId,
        username: MessengerUsername | None,
    ) -> None:
        """Привязывает площадку.

        Идемпотентно: если этот же аккаунт уже привязан — ничего не делает и
        события не пишет, потому что повторный ``/start`` не бизнес-факт.

        :raises PlatformAlreadyLinkedError: на этой площадке уже другой аккаунт.
        """

    def unlink_account(self, platform: MessengerPlatform) -> None:
        """Отвязывает площадку.

        Если отвязали адресата уведомлений — переключает ``notify_via`` на
        оставшуюся площадку, иначе агрегат остался бы невалидным.

        :raises MessengerAccountNotLinkedError:
        :raises LastMessengerAccountError: последний аккаунт снимать нельзя.
        """

    def refresh_username(
        self, platform: MessengerPlatform, username: MessengerUsername | None
    ) -> None:
        """Обновляет юзернейм из апдейта. События не пишет — не бизнес-факт."""
```

### Профиль

```python
    def rename(self, full_name: FullName) -> None: ...

    def change_phone_number(self, phone_number: PhoneNumber) -> None: ...

    def change_preferences(self, preferences: UserPreferences) -> None:
        """:raises NotificationTargetNotLinkedError: notify_via не привязан."""
```

### Доступ

Агрегат отвечает за корректность перехода состояния, но не за то, кому это
позволено, — второго участника он не видит.

```python
    def assign_role(self, new_role: UserRole) -> None:
        """Меняет роль. Кому это позволено, решает AccessService."""

    def block(self, reason: BlockReason) -> None:
        """:raises UserAlreadyBlockedError:"""

    def unblock(self) -> None:
        """:raises UserNotBlockedError:"""

    def ensure_active(self) -> None:
        """Гард перед действиями покупателя.

        :raises UserIsBlockedError:
        """
```

### Чтение

```python
    @property
    def is_active(self) -> bool: ...

    @property
    def is_staff(self) -> bool:
        """MANAGER или ADMIN — есть доступ к админской части."""

    def account_for(self, platform: MessengerPlatform) -> MessengerAccount | None: ...

    def has_account(
        self, platform: MessengerPlatform, external_id: ExternalAccountId
    ) -> bool: ...

    def notification_account(self) -> MessengerAccount:
        """Аккаунт из preferences.notify_via.

        :raises NotificationTargetNotLinkedError:
        """
```

Все мутирующие методы обновляют `updated_at` и пишут событие через приватный
`_record(event)`, который кладёт его в `self.events_collection`.

```python
# src/goldy/domain/users/entities/messenger_account.py
@dataclass(eq=False, kw_only=True)
class MessengerAccount:
    """Учётная запись пользователя на одной площадке.

    Изменяемый dataclass, а не frozen VO: класс мапится императивно, и
    SQLAlchemy проставляет поля при загрузке из БД.
    """

    platform: MessengerPlatform
    external_id: ExternalAccountId
    username: MessengerUsername | None
    linked_at: datetime
```

## Доменные сервисы

```python
# src/goldy/domain/common/service.py
class BaseDomainService:
    """Маркер доменного сервиса.

    Событий не копит: в goldy их записывают агрегаты в request-scoped
    ``EventsCollection``, откуда их забирает ``EventsPipeline``.
    """
```

### `UserFactory` — фабрика

Отдельный `factories/`, а не сервис: существует ровно потому, что агрегату
неоткуда взять новый `UserId`, а тащить генератор в презентационный слой
означало бы размазать создание пользователя по двум местам.

```python
@final
class UserFactory:
    def __init__(
        self,
        events_collection: EventsCollection,
        user_id_generator: UserIdGenerator,
    ) -> None: ...

    def create(
        self,
        *,
        phone_number: PhoneNumber,
        full_name: FullName,
        platform: MessengerPlatform,
        external_id: ExternalAccountId,
        username: MessengerUsername | None = None,
    ) -> User:
        """Генерирует идентификатор и вызывает ``User.register``."""
```

### `AccessService` — политика

Событий не пишет и состояние не меняет: отвечает только на вопрос «вправе ли
субъект». Само изменение делает агрегат.

```python
class AccessService(DomainService):
    def authorize[PC: PermissionContext](
        self, permission: Permission[PC], *, context: PC
    ) -> None:
        """:raises AuthorizationError:"""
```

Как это выглядит в хендлере блокировки:

```python
self._access_service.authorize(
    CanManageSubordinate(),
    context=UserManagementContext(subject=actor, target=target),
)
target.block(reason)   # инвариант перехода — на агрегате
```

### Авторизация

```python
# authorization/role_hierarchy.py
SUBORDINATE_ROLES: Final[Mapping[UserRole, set[UserRole]]] = {
    UserRole.ADMIN: {UserRole.MANAGER, UserRole.CUSTOMER},
    UserRole.MANAGER: {UserRole.CUSTOMER},
    UserRole.CUSTOMER: set(),
}
```

Из иерархии бесплатно следуют два правила, которые иначе пришлось бы писать
отдельными проверками: администратор не может тронуть другого администратора, и
никто не может заблокировать сам себя — субъект никогда не является собственным
подчинённым. Роль `ADMIN` не назначается через бота вообще: её нет ни в чьих
подчинённых, поэтому первые администраторы засеиваются из конфига.

```python
# authorization/base.py
@dataclass(frozen=True)
class PermissionContext: ...


class Permission[PC: PermissionContext](ABC):
    @abstractmethod
    def is_satisfied_by(self, context: PC) -> bool:
        raise NotImplementedError


# authorization/composite.py
class AnyOf[PC: PermissionContext](Permission[PC]): ...
class AllOf[PC: PermissionContext](Permission[PC]): ...


# authorization/permission.py
@dataclass(frozen=True, kw_only=True)
class UserManagementContext(PermissionContext):
    subject: User
    target: User


@dataclass(frozen=True, kw_only=True)
class RoleManagementContext(PermissionContext):
    subject: User
    target_role: UserRole


class CanManageSelf(Permission[UserManagementContext]): ...
class CanManageSubordinate(Permission[UserManagementContext]): ...
class CanManageRole(Permission[RoleManagementContext]): ...
```

| Команда | Разрешение |
| --- | --- |
| Правка своего профиля | `AnyOf(CanManageSelf(), CanManageSubordinate())` |
| Блокировка / разблокировка | `CanManageSubordinate()` |
| Смена роли | `CanManageSubordinate()` **и** `CanManageRole()` |
| Просмотр списка пользователей | `user.is_staff` |

### Порт генерации id

```python
# src/goldy/domain/users/ports/id_generator.py
class UserIdGenerator(Protocol):
    @abstractmethod
    def __call__(self) -> UserId:
        raise NotImplementedError
```

Реализация в инфраструктуре — `uuid7()` из stdlib (проект на 3.14). Для
первичного ключа это заметно лучше `uuid4`: значения возрастают во времени, и
вставки не разносят B-tree индекс по всей странице.

## События

Все `@dataclass(frozen=True, slots=True, kw_only=True)`, наследники `Event`.
Поля — примитивы, потому что события сериализуются в outbox.

| Событие | Поля | Кто пишет |
| --- | --- | --- |
| `UserRegistered` | `user_id`, `phone_number`, `platform`, `external_id` | `User.register` |
| `MessengerAccountLinked` | `user_id`, `platform`, `external_id` | `User.link_account` |
| `MessengerAccountUnlinked` | `user_id`, `platform`, `external_id` | `User.unlink_account` |
| `UserRenamed` | `user_id`, `old_full_name`, `new_full_name` | `User.rename` |
| `UserPhoneNumberChanged` | `user_id`, `old_phone_number`, `new_phone_number` | `User.change_phone_number` |
| `UserPreferencesChanged` | `user_id`, `notify_via`, `marketing_consent` | `User.change_preferences` |
| `UserRoleChanged` | `user_id`, `old_role`, `new_role` | `User.assign_role` |
| `UserBlocked` | `user_id`, `reason` | `User.block` |
| `UserUnblocked` | `user_id` | `User.unblock` |

## Слой приложения

### Порты

```python
class UserCommandGateway(Protocol):
    """Запись и чтение агрегата целиком."""

    async def add(self, user: User) -> None: ...
    async def by_id(self, user_id: UserId) -> User | None: ...
    async def by_phone_number(self, phone_number: PhoneNumber) -> User | None: ...
    async def by_messenger_account(
        self, platform: MessengerPlatform, external_id: ExternalAccountId
    ) -> User | None: ...


class UserQueryGateway(Protocol):
    """Чтение проекций для админки. Агрегаты не возвращает."""

    async def read_by_id(self, user_id: UserId) -> UserView | None: ...
    async def read_all(
        self, pagination: Pagination, sorting: SortingOrder, ...
    ) -> Sequence[UserView]: ...
    async def total(self) -> int: ...


class IdentityProvider(Protocol):
    """Кто выполняет команду. Заполняется middleware площадки."""

    async def get_current_user_id(self) -> UserId: ...
```

Реализация одна на площадку и выбирается dishka по процессу:
`MessengerIdentityProvider` в инфраструктуре держит общий поиск
`(platform, external_id) → UserId`, а наследник добавляет только константу
площадки и способ достать id аккаунта из апдейта. Telegram-воркер никогда не
конструирует MAX-овый.

### Мапперы

Два, и живут они в разных слоях по одной причине — что у них на входе.

| Маппер | Порт | Реализация |
| --- | --- | --- |
| `User` → `UserView` | `application/common/ports/mappers` | adaptix, `infrastructure/mappers` |
| `RowMapping` → `UserView` | `infrastructure/mappers` | руками, там же |

Порт второго остаётся в инфраструктуре намеренно: на входе у него
`sqlalchemy.RowMapping`, и объявить его среди портов приложения значило бы
затащить ORM в слой, который про неё знать не должен. Adaptix там тоже не
подходит — `RowMapping` не несёт типов полей, которые конвертер мог бы
проинспектировать.

В adaptix-маппере почти каждое поле идёт через `link_function`: он связывает
поля, а не пути, поэтому любой value object нужно разворачивать явно. `id` —
тоже, потому что `UserId` это `NewType`, сквозь который adaptix не видит.

### Команды и запросы

```
application/commands/users/
├── register_user/            # идемпотентная, обе площадки
├── rename_user/
├── change_notification_preferences/
├── unlink_messenger_account/
├── change_user_role/         # админка
├── block_user/               # админка
└── unblock_user/             # админка

application/queries/users/
├── get_current_user/
├── get_user_by_id/           # админка
└── list_users/               # админка, Pagination + SortingOrder + фильтры
```

### `RegisterUserHandler` — единственный нетривиальный

```python
async def handle(self, command: RegisterUserCommand) -> UserView:
    phone_number = PhoneNumber.from_raw(command.phone_number)

    existing = await self._gateway.by_messenger_account(
        command.platform, command.external_id
    )
    if existing is not None:                       # повторный /start
        existing.refresh_username(command.platform, command.username)
        return to_view(existing)

    by_phone = await self._gateway.by_phone_number(phone_number)
    if by_phone is not None:                       # человек пришёл со второй площадки
        by_phone.link_account(
            command.platform, command.external_id, command.username
        )
        return to_view(by_phone)

    user = self._user_service.create(...)
    await self._gateway.add(user)
    return to_view(user)
```

Два одновременных `/start` пройдут обе проверки и упрутся в уникальный индекс.
Адаптер переводит `IntegrityError` в `UserAlreadyExistsError`, команда
повторяется один раз — на втором проходе сработает ветка идемпотентности.

## Хранилище

Императивный маппинг, как у `outbox`.

```
users
  id                 uuid          pk
  phone_number       varchar(20)   not null  unique
  first_name         varchar(100)  not null
  last_name          varchar(100)  null
  role               varchar(20)   not null
  status             varchar(20)   not null
  block_reason       varchar(500)  null
  notify_via         varchar(20)   not null
  marketing_consent  boolean       not null
  created_at         timestamptz   not null
  updated_at         timestamptz   not null

messenger_accounts
  platform     varchar(20)   ┐ pk
  external_id  varchar(64)   ┘
  user_id      uuid          not null  fk -> users.id on delete cascade
  username     varchar(64)   null
  linked_at    timestamptz   not null
  unique (user_id, platform)
```

Составной первичный ключ `(platform, external_id)` — естественный ключ строки.
Он же бесплатно даёт уникальность аккаунта в системе и индекс ровно под самый
частый запрос бота: «кто мне пишет». `unique (user_id, platform)` держит
инвариант «одна площадка — один аккаунт» на уровне БД.

`FullName` и `UserPreferences` мапятся через `composite()`, `PhoneNumber` — через
`TypeDecorator`. `accounts` — `relationship(lazy="selectin",
cascade="all, delete-orphan")`: агрегат всегда грузится целиком, потому что
инварианты привязки считаются по всему списку.

`events_collection` не колонка, поэтому загруженному из БД агрегату его
проставляет сам адаптер гейтвея — иначе первый же вызов `block()` упадёт на
отсутствующем атрибуте.

## Инварианты

| Инвариант | Где держится |
| --- | --- |
| Телефон в формате E.164 | `PhoneNumber` |
| Имя непустое, до 100 символов | `FullName` |
| Причина блокировки непустая | `BlockReason` |
| Одна площадка — один аккаунт у пользователя | `User.link_account` + `unique (user_id, platform)` |
| Хотя бы один аккаунт всегда привязан | `User.unlink_account` |
| `notify_via` указывает на привязанную площадку | `User.change_preferences`, `User.unlink_account` |
| Нельзя заблокировать заблокированного | `User.block` |
| Заблокированный не действует | `User.ensure_active` |
| Нельзя управлять равным или старшим по роли | `AccessService` + `SUBORDINATE_ROLES` |
| Телефон уникален глобально | `unique` индекс + ретрай команды |
| Аккаунт принадлежит одному пользователю | `pk (platform, external_id)` + ретрай |

Последние два — межагрегатные, в домене их проверить нечем: любая проверка
чтением проигрывает гонке. Поэтому их держит БД, а приложение переводит
`IntegrityError` в доменную ошибку.

## Открытые вопросы

1. **Telegram отдаёт чужие контакты.** В презентационном слое обязательна
   проверка `contact.user_id == message.from_user.id`. Без неё человек
   зарегистрируется под чужим номером и по автопривязке получит чужую учётную
   запись со всей историей заказов. Это единственное место, где ADR-0001 можно
   пробить.

   MAX кнопку `request_contact` поддерживает
   ([dev.max.ru](https://dev.max.ru/docs-api)), так что предпосылка ADR-0001
   держится на обеих площадках.
3. **Все ли события должны улетать в RabbitMQ.** `EventsPipeline` публикует всё
   подряд, но `UserRenamedEvent` наружу не нужен никому. Когда шина начнёт
   забиваться, понадобится деление на внутренние и интеграционные события.
4. **Смена телефона на занятый.** Метод есть, команды нет. Когда появится,
   всплывёт слияние двух существующих пользователей — самый неприятный сценарий
   в этой модели, лучше решать его отдельно и осознанно.
