from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.domain.users.values.user_id import UserId


class UserIdGenerator(Protocol):
    @abstractmethod
    def __call__(self) -> UserId:
        raise NotImplementedError
