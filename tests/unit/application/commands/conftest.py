"""The command handlers under test, assembled from the shared stubs."""

import pytest

from goldy.application.commands.users.block_user.handler import BlockUserHandler
from goldy.application.commands.users.change_user_role.handler import (
    ChangeUserRoleHandler,
)
from goldy.application.commands.users.register_user.handler import RegisterUserHandler
from goldy.application.commands.users.rename_user.handler import RenameUserHandler
from goldy.application.commands.users.seed_admins.handler import SeedAdminsHandler
from goldy.application.commands.users.unblock_user.handler import UnblockUserHandler
from goldy.application.common.ports.mappers import UserViewMapper
from goldy.application.common.services.user_provider import UserProvider
from goldy.domain.users.factories.user_factory import UserFactory
from goldy.domain.users.services.access_service import AccessService
from tests.unit.stubs.admin import StubAdminRegistry
from tests.unit.stubs.gateways import InMemoryUserCommandGateway


@pytest.fixture()
def register_user_handler(
    user_gateway: InMemoryUserCommandGateway,
    user_factory: UserFactory,
    user_view_mapper: UserViewMapper,
    admin_registry: StubAdminRegistry,
) -> RegisterUserHandler:
    return RegisterUserHandler(
        user_gateway,
        user_factory,
        user_view_mapper,
        admin_registry,
    )


@pytest.fixture()
def seed_admins_handler(
    user_gateway: InMemoryUserCommandGateway,
    admin_registry: StubAdminRegistry,
) -> SeedAdminsHandler:
    return SeedAdminsHandler(user_gateway, admin_registry)


@pytest.fixture()
def block_user_handler(
    user_provider: UserProvider,
    access_service: AccessService,
    user_view_mapper: UserViewMapper,
) -> BlockUserHandler:
    return BlockUserHandler(user_provider, access_service, user_view_mapper)


@pytest.fixture()
def unblock_user_handler(
    user_provider: UserProvider,
    access_service: AccessService,
    user_view_mapper: UserViewMapper,
) -> UnblockUserHandler:
    return UnblockUserHandler(user_provider, access_service, user_view_mapper)


@pytest.fixture()
def change_user_role_handler(
    user_provider: UserProvider,
    access_service: AccessService,
    user_view_mapper: UserViewMapper,
) -> ChangeUserRoleHandler:
    return ChangeUserRoleHandler(user_provider, access_service, user_view_mapper)


@pytest.fixture()
def rename_user_handler(
    user_provider: UserProvider,
    access_service: AccessService,
    user_view_mapper: UserViewMapper,
) -> RenameUserHandler:
    return RenameUserHandler(user_provider, access_service, user_view_mapper)
