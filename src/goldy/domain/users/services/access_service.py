import logging
from typing import Final, final

from goldy.domain.common.service import BaseDomainService
from goldy.domain.users.errors import AuthorizationError
from goldy.domain.users.services.authorization.base import (
    Permission,
    PermissionContext,
)
from goldy.domain.users.services.authorization.constants import AUTHZ_NOT_AUTHORIZED

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class AccessService(BaseDomainService):
    """Answers whether one person may act upon another.

    Deliberately changes nothing and records no events. "May the manager block
    this customer" needs two aggregates and so cannot live on either of them;
    "is this user already blocked" needs only one and lives on :class:`User`.
    Keeping the two apart is what lets the same permission back several
    commands.
    """

    def authorize[PC: PermissionContext](
        self,
        permission: Permission[PC],
        *,
        context: PC,
    ) -> None:
        """Lets the caller proceed, or refuses.

        Raises:
            AuthorizationError: the permission is not satisfied.
        """
        if permission.is_satisfied_by(context):
            return

        logger.info(
            "access: refused %s",
            type(permission).__name__,
        )
        raise AuthorizationError(AUTHZ_NOT_AUTHORIZED)
