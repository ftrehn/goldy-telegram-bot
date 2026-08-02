import pytest

from goldy.application.commands.users.block_user.command import BlockUserCommand
from goldy.application.commands.users.block_user.handler import BlockUserHandler
from goldy.application.commands.users.change_user_role.command import (
    ChangeUserRoleCommand,
)
from goldy.application.commands.users.change_user_role.handler import (
    ChangeUserRoleHandler,
)
from goldy.application.commands.users.rename_user.command import RenameUserCommand
from goldy.application.commands.users.rename_user.handler import RenameUserHandler
from goldy.application.commands.users.unblock_user.command import UnblockUserCommand
from goldy.application.commands.users.unblock_user.handler import UnblockUserHandler
from goldy.application.error import UserNotFoundError
from goldy.domain.users.errors import AuthorizationError
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.stubs.identity import sequential_user_ids

REASON: str = "Оскорблял поддержку"

CUSTOMER = {"phone_number": "+79991111111", "external_id": "111"}
MANAGER = {"phone_number": "+79992222222", "external_id": "222"}
ADMIN = {"phone_number": "+79993333333", "external_id": "333"}


async def test_a_manager_can_block_a_customer(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    block_user_handler: BlockUserHandler,
) -> None:
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    customer = await seed_user(**CUSTOMER)
    acting_as(manager.id)

    view = await block_user_handler.handle(
        BlockUserCommand(user_id=customer.id, reason=REASON),
    )

    assert view.status == UserStatus.BLOCKED.value
    assert view.block_reason == REASON


async def test_a_customer_cannot_block_anyone(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    block_user_handler: BlockUserHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    victim = await seed_user(phone_number="+79994444444", external_id="444")
    acting_as(customer.id)

    command = BlockUserCommand(user_id=victim.id, reason=REASON)

    with pytest.raises(AuthorizationError):
        await block_user_handler.handle(command)


async def test_an_admin_cannot_block_another_admin(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    block_user_handler: BlockUserHandler,
) -> None:
    """Peers must not be able to lock each other out of the shop."""
    admin = await seed_user(**ADMIN, role=UserRole.ADMIN)
    peer = await seed_user(
        phone_number="+79995555555",
        external_id="555",
        role=UserRole.ADMIN,
    )
    acting_as(admin.id)

    command = BlockUserCommand(user_id=peer.id, reason=REASON)

    with pytest.raises(AuthorizationError):
        await block_user_handler.handle(command)


async def test_nobody_can_block_themselves(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    block_user_handler: BlockUserHandler,
) -> None:
    """Falls out of the hierarchy: nobody is their own subordinate."""
    admin = await seed_user(**ADMIN, role=UserRole.ADMIN)
    acting_as(admin.id)

    command = BlockUserCommand(user_id=admin.id, reason=REASON)

    with pytest.raises(AuthorizationError):
        await block_user_handler.handle(command)


async def test_unblocking_restores_the_customer(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    block_user_handler: BlockUserHandler,
    unblock_user_handler: UnblockUserHandler,
) -> None:
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    customer = await seed_user(**CUSTOMER)
    acting_as(manager.id)
    await block_user_handler.handle(
        BlockUserCommand(user_id=customer.id, reason=REASON),
    )

    view = await unblock_user_handler.handle(UnblockUserCommand(user_id=customer.id))

    assert view.status == UserStatus.ACTIVE.value
    assert view.block_reason is None


async def test_blocking_a_user_who_does_not_exist_is_refused(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    block_user_handler: BlockUserHandler,
) -> None:
    admin = await seed_user(**ADMIN, role=UserRole.ADMIN)
    acting_as(admin.id)
    stranger = sequential_user_ids(99)[-1]

    command = BlockUserCommand(user_id=stranger, reason=REASON)

    with pytest.raises(UserNotFoundError):
        await block_user_handler.handle(command)


async def test_an_admin_can_promote_a_customer_to_manager(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    change_user_role_handler: ChangeUserRoleHandler,
) -> None:
    admin = await seed_user(**ADMIN, role=UserRole.ADMIN)
    customer = await seed_user(**CUSTOMER)
    acting_as(admin.id)

    view = await change_user_role_handler.handle(
        ChangeUserRoleCommand(user_id=customer.id, role=UserRole.MANAGER),
    )

    assert view.role == UserRole.MANAGER.value


async def test_a_manager_cannot_mint_another_manager(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    change_user_role_handler: ChangeUserRoleHandler,
) -> None:
    """Managing the target is not the same as being allowed to grant the role."""
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    customer = await seed_user(**CUSTOMER)
    acting_as(manager.id)

    command = ChangeUserRoleCommand(user_id=customer.id, role=UserRole.MANAGER)

    with pytest.raises(AuthorizationError):
        await change_user_role_handler.handle(command)


async def test_the_admin_role_cannot_be_granted_through_the_bot(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    change_user_role_handler: ChangeUserRoleHandler,
) -> None:
    """It is seeded from configuration and nowhere else."""
    admin = await seed_user(**ADMIN, role=UserRole.ADMIN)
    customer = await seed_user(**CUSTOMER)
    acting_as(admin.id)

    command = ChangeUserRoleCommand(user_id=customer.id, role=UserRole.ADMIN)

    with pytest.raises(AuthorizationError):
        await change_user_role_handler.handle(command)


async def test_a_customer_can_rename_themselves(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    rename_user_handler: RenameUserHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    view = await rename_user_handler.handle(
        RenameUserCommand(user_id=customer.id, first_name="Пётр", last_name=None),
    )

    assert view.first_name == "Пётр"
    assert view.last_name is None


async def test_a_customer_cannot_rename_someone_else(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    rename_user_handler: RenameUserHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    stranger = await seed_user(phone_number="+79996666666", external_id="666")
    acting_as(customer.id)

    command = RenameUserCommand(user_id=stranger.id, first_name="Взлом")

    with pytest.raises(AuthorizationError):
        await rename_user_handler.handle(command)


async def test_a_manager_can_fix_a_customers_name(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    rename_user_handler: RenameUserHandler,
) -> None:
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    customer = await seed_user(**CUSTOMER)
    acting_as(manager.id)

    view = await rename_user_handler.handle(
        RenameUserCommand(user_id=customer.id, first_name="Данила"),
    )

    assert view.first_name == "Данила"
