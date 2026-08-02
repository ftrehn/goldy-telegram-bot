from typing import Any

from goldy.application.common.views.user import UserView
from goldy.domain.users.values.locale import SUPPORTED_LOCALES


async def profile_getter(user: UserView, **_kwargs: Any) -> dict[str, Any]:
    """The profile as it stands right now.

    ``user`` arrives from the update data, which aiogram-dialog passes into
    every getter — the auth gate reloaded it for this update, so a rename two
    screens ago is already visible. Caching it in ``dialog_data`` when the
    dialog opened would show the old name instead.
    """
    full_name = (
        user.first_name
        if user.last_name is None
        else f"{user.first_name} {user.last_name}"
    )

    return {
        "name": full_name,
        "phone": user.phone_number,
        "role": user.role,
        "locale": user.locale,
        "notify": user.notify_via,
        "can_unlink": len(user.accounts) > 1,
    }


async def locales_getter(user: UserView, **_kwargs: Any) -> dict[str, Any]:
    """The languages we ship translations for."""
    return {
        "locales": [(code, code) for code in sorted(SUPPORTED_LOCALES)],
        "current": user.locale,
    }


async def accounts_getter(user: UserView, **_kwargs: Any) -> dict[str, Any]:
    """The platforms this person is reachable on."""
    return {
        "accounts": [(account.platform, account.platform) for account in user.accounts],
        "notify": user.notify_via,
        "marketing": user.marketing_consent,
    }
