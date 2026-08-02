from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionContext:
    """Everything a permission needs to reach its verdict.

    Subclassed per question rather than made into one wide bag, so a permission
    cannot silently start depending on a field the caller never meant to
    supply.
    """


class Permission[PC: PermissionContext](ABC):
    """One yes-or-no rule about who may do what.

    Rules are objects rather than ``if`` branches so they can be named after
    the thing the business actually says, combined with ``AnyOf`` / ``AllOf``,
    and tested without a user, a session or a database.
    """

    @abstractmethod
    def is_satisfied_by(self, context: PC) -> bool:
        raise NotImplementedError
