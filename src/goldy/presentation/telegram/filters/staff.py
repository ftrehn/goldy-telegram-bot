from typing import final, override

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from goldy.application.common.views.user import UserView


@final
class IsStaffFilter(BaseFilter):
    """Keeps the admin routers from even matching for a customer.

    Not the authorization check — that one lives in the handlers, where it is
    enforced against the aggregate and cannot be bypassed. This is only so a
    customer who guesses ``/admin`` gets "unknown command" instead of a refusal
    that confirms the command exists.
    """

    @override
    async def __call__(
        self,
        event: TelegramObject,
        user: UserView | None = None,
    ) -> bool:
        return user is not None and user.is_staff
