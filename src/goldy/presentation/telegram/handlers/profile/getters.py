from typing import Any

from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.user import UserView
from goldy.application.queries.site.get_site_link.query import GetSiteLinkQuery
from goldy.domain.users.values.locale import SUPPORTED_LOCALES
from goldy.presentation.telegram.common.formatting import for_message_text
from goldy.presentation.telegram.handlers.site.identity import describe_site_customer


async def profile_getter(user: UserView, **_kwargs: Any) -> dict[str, Any]:
    """The profile as it stands right now.

    ``user`` arrives from the update data, which aiogram-dialog passes into
    every getter — the auth gate reloaded it for this update, so a rename two
    screens ago is already visible. Caching it in ``dialog_data`` when the
    dialog opened would show the old name instead.

    The name is quoted because a person may call themselves anything and this
    screen prints it inside a message sent as HTML; ``FullName`` restricts the
    length and nothing else, and the first name is taken from Telegram at
    registration, where it is whatever its owner typed. See
    :func:`for_message_text`.
    """
    full_name = (
        user.first_name
        if user.last_name is None
        else f"{user.first_name} {user.last_name}"
    )

    return {
        "name": for_message_text(full_name),
        "phone": user.phone_number,
        "role": user.role,
        "locale": user.locale,
        "notify": user.notify_via,
        "can_unlink": len(user.accounts) > 1,
    }


@inject
async def site_link_getter(
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """Whether the person is linked to the site, and to whom.

    The bot's own copy of the link, read from the database and not from the
    site: the profile has to open while the site is down. A link removed in
    the site's cabinet still shows here until the person unlinks or links
    again — the site answers 204 to removing a link it no longer has. A getter of its
    own, beside :func:`profile_getter`, so that one stays a pure function of
    the person.
    """
    site_link = await sender.send(GetSiteLinkQuery())

    if site_link is None:
        return {"site_linked": False, "site_who": ""}

    return {
        "site_linked": True,
        "site_who": describe_site_customer(
            site_link.customer_name,
            company=site_link.company_name,
        ),
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
