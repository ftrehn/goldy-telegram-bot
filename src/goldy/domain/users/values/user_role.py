from enum import StrEnum


class UserRole(StrEnum):
    """How much of the shop a person is allowed to run.

    One role per human, not per messenger account. There is deliberately no
    ``is_assignable`` / ``is_changeable`` here: which role may touch which is
    described once, by ``SUBORDINATE_ROLES``, and a second statement of the
    same rule would drift from it on the first edit.
    """

    CUSTOMER = "customer"
    MANAGER = "manager"
    ADMIN = "admin"
