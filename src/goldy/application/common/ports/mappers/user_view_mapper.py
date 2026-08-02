from abc import abstractmethod
from typing import Protocol

from goldy.application.common.views.user import UserView
from goldy.domain.users.entities.user import User


class UserViewMapper(Protocol):
    """Renders a loaded aggregate as the view command handlers return.

    Only the aggregate's state crosses: its events collection and the value
    objects wrapping each field stay behind, so presentation never learns what
    a ``PhoneNumber`` is.
    """

    @abstractmethod
    def to_view(self, user: User) -> UserView:
        raise NotImplementedError
