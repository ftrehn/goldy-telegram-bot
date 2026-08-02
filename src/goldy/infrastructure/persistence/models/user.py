from typing import Final

from sqlalchemy import (
    UUID as SA_UUID,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import composite, relationship

from goldy.domain.users.entities.messenger_account import MessengerAccount
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.full_name import FullName
from goldy.domain.users.values.user_preferences import UserPreferences
from goldy.infrastructure.persistence.models.base import mapper_registry
from goldy.infrastructure.persistence.models.types import (
    BlockReasonType,
    ExternalAccountIdType,
    MessengerPlatformType,
    MessengerUsernameType,
    PhoneNumberType,
    UserRoleType,
    UserStatusType,
)

MAX_NAME_COLUMN_LENGTH: Final[int] = 100

users_table: Final[Table] = Table(
    "users",
    mapper_registry.metadata,
    Column("id", SA_UUID(as_uuid=True), primary_key=True),
    Column("phone_number", PhoneNumberType, nullable=False, unique=True),
    Column("first_name", String(MAX_NAME_COLUMN_LENGTH), nullable=False),
    Column("last_name", String(MAX_NAME_COLUMN_LENGTH), nullable=True),
    Column("role", UserRoleType, nullable=False, index=True),
    Column("status", UserStatusType, nullable=False, index=True),
    Column("block_reason", BlockReasonType, nullable=True),
    Column("notify_via", MessengerPlatformType, nullable=False),
    Column("marketing_consent", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
"""One row per human.

``phone_number`` is unique because it is the identity of a person, and that
rule spans aggregates: no amount of checking inside :class:`User` can stop two
concurrent registrations from both inserting, so the index has to hold it.
"""

messenger_accounts_table: Final[Table] = Table(
    "messenger_accounts",
    mapper_registry.metadata,
    Column("platform", MessengerPlatformType, primary_key=True),
    Column("external_id", ExternalAccountIdType, primary_key=True),
    Column(
        "user_id",
        SA_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("username", MessengerUsernameType, nullable=True),
    Column("linked_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("user_id", "platform"),
)
"""One row per platform account.

The primary key is the natural key ``(platform, external_id)`` rather than a
surrogate. It earns three things at once: an account cannot belong to two
people, the lookup the bot performs on literally every incoming update — "who
is writing to me" — is an index seek, and there is no synthetic id anybody
could mistake for the user's.

``unique (user_id, platform)`` is the other half: one account per platform per
person, held here as well as in :meth:`User.link_account` because a concurrent
link would slip past the aggregate's check.
"""


def map_users_table() -> None:
    """Maps the User aggregate and the accounts inside it.

    ``events_collection`` is intentionally absent — it is not a column, so
    SQLAlchemy leaves it unset on loaded instances and the gateway supplies the
    request-scoped one.
    """
    mapper_registry.map_imperatively(
        MessengerAccount,
        messenger_accounts_table,
        properties={
            "platform": messenger_accounts_table.c.platform,
            "external_id": messenger_accounts_table.c.external_id,
            "username": messenger_accounts_table.c.username,
            "linked_at": messenger_accounts_table.c.linked_at,
        },
    )

    mapper_registry.map_imperatively(
        User,
        users_table,
        properties={
            "id": users_table.c.id,
            "phone_number": users_table.c.phone_number,
            "full_name": composite(
                FullName,
                users_table.c.first_name,
                users_table.c.last_name,
            ),
            "preferences": composite(
                UserPreferences,
                users_table.c.notify_via,
                users_table.c.marketing_consent,
            ),
            "role": users_table.c.role,
            "status": users_table.c.status,
            "block_reason": users_table.c.block_reason,
            "created_at": users_table.c.created_at,
            "updated_at": users_table.c.updated_at,
            "accounts": relationship(
                MessengerAccount,
                lazy="selectin",
                cascade="all, delete-orphan",
                order_by=messenger_accounts_table.c.linked_at,
            ),
        },
    )
