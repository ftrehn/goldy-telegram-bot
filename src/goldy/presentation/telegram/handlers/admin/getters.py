from typing import Any, Final
from uuid import UUID

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.user import UserView
from goldy.application.queries.users.get_user_by_id.query import GetUserByIdQuery
from goldy.application.queries.users.list_users.query import ListUsersQuery
from goldy.domain.users.values.user_role import UserRole

PAGE_SIZE: Final[int] = 8

PAGE_KEY: Final[str] = "page"
USER_ID_KEY: Final[str] = "user_id"


def current_page(dialog_manager: DialogManager) -> int:
    page: int = dialog_manager.dialog_data.get(PAGE_KEY, 0)
    return page


def selected_user_id(dialog_manager: DialogManager) -> UUID:
    return UUID(dialog_manager.dialog_data[USER_ID_KEY])


@inject
async def users_getter(
    dialog_manager: DialogManager,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """One page of users, straight from the read side.

    Paged in the query rather than fetched whole and scrolled in the keyboard:
    the list grows with the shop, and a widget that has already loaded every
    row is not pagination, it is a delayed outage.
    """
    page = current_page(dialog_manager)
    view = await sender.send(
        ListUsersQuery(limit=PAGE_SIZE, offset=page * PAGE_SIZE),
    )

    return {
        "users": [(_label(user), str(user.id)) for user in view.users],
        "is_empty": not view.users,
        "page": page + 1,
        "pages": max(1, -(-view.total // PAGE_SIZE)),
        "total": view.total,
        "has_prev": page > 0,
        "has_next": (page + 1) * PAGE_SIZE < view.total,
    }


@inject
async def user_card_getter(
    dialog_manager: DialogManager,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """The selected person, re-read on every render.

    Re-reading is what makes a block or a role change show up the moment the
    dialog comes back to this screen, without anybody having to invalidate a
    copy held in ``dialog_data``.
    """
    user = await sender.send(GetUserByIdQuery(user_id=selected_user_id(dialog_manager)))

    return {
        "name": _label(user),
        "phone": user.phone_number,
        "role": user.role,
        "status": user.status,
        "locale": user.locale,
        "reason": user.block_reason or "",
        "is_blocked": user.is_blocked,
    }


async def roles_getter(**_kwargs: Any) -> dict[str, Any]:
    """The roles that can be handed out through the bot.

    ``ADMIN`` is absent because nobody may grant it — it sits above everyone in
    the hierarchy, so the command would refuse anyway. Offering a button that
    always fails is worse than not offering one.
    """
    return {
        "roles": [
            (role.value, role.value) for role in (UserRole.CUSTOMER, UserRole.MANAGER)
        ],
    }


def _label(user: UserView) -> str:
    name = (
        user.first_name
        if user.last_name is None
        else f"{user.first_name} {user.last_name}"
    )
    return f"{name} · {user.phone_number}"
