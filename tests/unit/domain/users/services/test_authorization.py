import pytest

from goldy.domain.users.entities.user import User
from goldy.domain.users.errors import AuthorizationError
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.services.authorization.composite import AllOf, AnyOf
from goldy.domain.users.services.authorization.permission import (
    CanManageRole,
    CanManageSelf,
    CanManageSubordinate,
    IsStaff,
    RoleManagementContext,
    StaffContext,
    UserManagementContext,
)
from goldy.domain.users.values.user_role import UserRole

type People = dict[UserRole, User]


@pytest.mark.parametrize(
    ("subject_role", "target_role", "allowed"),
    (
        (UserRole.ADMIN, UserRole.CUSTOMER, True),
        (UserRole.ADMIN, UserRole.MANAGER, True),
        (UserRole.ADMIN, UserRole.ADMIN, False),
        (UserRole.MANAGER, UserRole.CUSTOMER, True),
        (UserRole.MANAGER, UserRole.MANAGER, False),
        (UserRole.MANAGER, UserRole.ADMIN, False),
        (UserRole.CUSTOMER, UserRole.CUSTOMER, False),
        (UserRole.CUSTOMER, UserRole.MANAGER, False),
        (UserRole.CUSTOMER, UserRole.ADMIN, False),
    ),
)
def test_only_a_strictly_lower_role_can_be_managed(
    people: People,
    subject_role: UserRole,
    target_role: UserRole,
    *,
    allowed: bool,
) -> None:
    """Refusing equals is the whole point.

    It is what stops an administrator from blocking a peer, and — since nobody
    outranks themselves — from locking themselves out.
    """
    context = UserManagementContext(
        subject=people[subject_role],
        target=people[target_role],
    )

    assert CanManageSubordinate().is_satisfied_by(context) is allowed


@pytest.mark.parametrize(
    "role",
    (UserRole.CUSTOMER, UserRole.MANAGER, UserRole.ADMIN),
)
def test_nobody_can_manage_themselves_through_the_hierarchy(
    people: People,
    role: UserRole,
) -> None:
    person = people[role]

    context = UserManagementContext(subject=person, target=person)

    assert CanManageSubordinate().is_satisfied_by(context) is False


def test_everyone_can_manage_themselves_explicitly(people: People) -> None:
    customer = people[UserRole.CUSTOMER]

    context = UserManagementContext(subject=customer, target=customer)

    assert CanManageSelf().is_satisfied_by(context) is True


def test_editing_a_profile_allows_the_owner_or_a_superior(people: People) -> None:
    customer = people[UserRole.CUSTOMER]
    manager = people[UserRole.MANAGER]
    permission = AnyOf(CanManageSelf(), CanManageSubordinate())

    own = UserManagementContext(subject=customer, target=customer)
    by_manager = UserManagementContext(subject=manager, target=customer)
    by_stranger = UserManagementContext(subject=customer, target=manager)

    assert permission.is_satisfied_by(own) is True
    assert permission.is_satisfied_by(by_manager) is True
    assert permission.is_satisfied_by(by_stranger) is False


@pytest.mark.parametrize(
    ("subject_role", "target_role", "allowed"),
    (
        (UserRole.ADMIN, UserRole.MANAGER, True),
        (UserRole.ADMIN, UserRole.CUSTOMER, True),
        (UserRole.ADMIN, UserRole.ADMIN, False),
        (UserRole.MANAGER, UserRole.CUSTOMER, True),
        (UserRole.MANAGER, UserRole.MANAGER, False),
    ),
)
def test_a_role_can_only_be_granted_by_someone_who_outranks_it(
    people: People,
    subject_role: UserRole,
    target_role: UserRole,
    *,
    allowed: bool,
) -> None:
    """A manager minting another manager would quietly manufacture a peer."""
    context = RoleManagementContext(
        subject=people[subject_role],
        target_role=target_role,
    )

    assert CanManageRole().is_satisfied_by(context) is allowed


def test_the_admin_role_cannot_be_granted_by_anyone(people: People) -> None:
    """It sits above everyone, so the first admins are seeded from config."""
    for subject in people.values():
        context = RoleManagementContext(subject=subject, target_role=UserRole.ADMIN)

        assert CanManageRole().is_satisfied_by(context) is False


@pytest.mark.parametrize(
    ("role", "allowed"),
    (
        (UserRole.CUSTOMER, False),
        (UserRole.MANAGER, True),
        (UserRole.ADMIN, True),
    ),
)
def test_the_admin_side_is_open_to_staff_only(
    people: People,
    role: UserRole,
    *,
    allowed: bool,
) -> None:
    context = StaffContext(subject=people[role])

    assert IsStaff().is_satisfied_by(context) is allowed


def test_any_of_refuses_when_it_holds_nothing(people: People) -> None:
    """A rule that permits nothing must refuse everything, not wave it through."""
    context = UserManagementContext(
        subject=people[UserRole.ADMIN],
        target=people[UserRole.CUSTOMER],
    )

    assert AnyOf[UserManagementContext]().is_satisfied_by(context) is False


def test_all_of_refuses_when_it_holds_nothing(people: People) -> None:
    context = UserManagementContext(
        subject=people[UserRole.ADMIN],
        target=people[UserRole.CUSTOMER],
    )

    assert AllOf[UserManagementContext]().is_satisfied_by(context) is False


def test_all_of_needs_every_rule_satisfied(people: People) -> None:
    customer = people[UserRole.CUSTOMER]
    own = UserManagementContext(subject=customer, target=customer)

    permission = AllOf(CanManageSelf(), CanManageSubordinate())

    assert permission.is_satisfied_by(own) is False


def test_authorize_lets_a_satisfied_permission_through(
    access: AccessService,
    people: People,
) -> None:
    context = UserManagementContext(
        subject=people[UserRole.ADMIN],
        target=people[UserRole.CUSTOMER],
    )

    access.authorize(CanManageSubordinate(), context=context)


def test_authorize_raises_on_refusal(access: AccessService, people: People) -> None:
    admin = people[UserRole.ADMIN]

    context = UserManagementContext(subject=admin, target=admin)

    with pytest.raises(AuthorizationError):
        access.authorize(CanManageSubordinate(), context=context)


def test_a_refusal_says_nothing_about_why(
    access: AccessService,
    people: People,
) -> None:
    """Explaining it would tell whoever is probing which roles exist."""
    admin = people[UserRole.ADMIN]
    context = UserManagementContext(subject=admin, target=admin)

    with pytest.raises(AuthorizationError) as raised:
        access.authorize(CanManageSubordinate(), context=context)

    assert str(raised.value) == "Not authorized."
