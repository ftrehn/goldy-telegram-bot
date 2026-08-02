from collections.abc import Sequence
from typing import final, override

from sqlalchemy import RowMapping

from goldy.application.common.views.user import MessengerAccountView, UserView
from goldy.infrastructure.mappers.user_row_view_mapper import UserRowViewMapper


@final
class SqlAlchemyUserRowViewMapper(UserRowViewMapper):
    """Flattens user and account rows into the views the admin side renders.

    Written by hand rather than with adaptix: a ``RowMapping`` carries no field
    types for a converter to introspect, and the accounts are not a column of
    the user row at all — they arrive from a second query and are grafted on
    here.

    The values are already value objects, not raw text: the columns carry type
    decorators, so the same unwrapping the aggregate mapper does is needed
    again.
    """

    @override
    def to_view(
        self,
        row: RowMapping,
        accounts: Sequence[MessengerAccountView],
    ) -> UserView:
        block_reason = row["block_reason"]

        return UserView(
            id=row["id"],
            phone_number=row["phone_number"].value,
            first_name=row["first_name"],
            last_name=row["last_name"],
            role=row["role"].value,
            status=row["status"].value,
            block_reason=block_reason.value if block_reason is not None else None,
            notify_via=row["notify_via"].value,
            locale=row["locale"].value,
            marketing_consent=row["marketing_consent"],
            accounts=tuple(accounts),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @override
    def to_account_view(self, row: RowMapping) -> MessengerAccountView:
        username = row["username"]

        return MessengerAccountView(
            platform=row["platform"].value,
            external_id=row["external_id"].value,
            username=username.value if username is not None else None,
            linked_at=row["linked_at"],
        )
