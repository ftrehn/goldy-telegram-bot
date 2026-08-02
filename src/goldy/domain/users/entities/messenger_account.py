from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import final

from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.messenger_username import MessengerUsername


@final
@dataclass(eq=False, kw_only=True)
class MessengerAccount:
    """One person's account on one platform — what they actually write from.

    Lives inside the :class:`User` aggregate and is never handed out on its
    own: the rules about it (one per platform, never the last one) can only be
    checked against the whole list.

    A mutable dataclass rather than a frozen value object because it is mapped
    imperatively, and SQLAlchemy assigns to these attributes when it loads a
    row. Its identity is ``(platform, external_id)``, which is also the table's
    primary key.
    """

    platform: MessengerPlatform
    external_id: ExternalAccountId
    username: MessengerUsername | None = field(default=None)
    linked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
