import pytest

from goldy.domain.users.entities.user import User
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.values.user_role import UserRole
from tests.unit.factories.domain_factories import make_people_by_role


@pytest.fixture()
def access() -> AccessService:
    return AccessService()


@pytest.fixture()
def people() -> dict[UserRole, User]:
    """One person per role, for checking a rule across the whole matrix."""
    return make_people_by_role()
