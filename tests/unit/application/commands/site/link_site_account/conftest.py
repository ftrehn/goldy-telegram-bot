import pytest

from goldy.application.commands.site.link_site_account.handler import (
    LinkSiteAccountHandler,
)
from goldy.application.common.services.user_provider import UserProvider
from tests.unit.stubs.site import ScriptedSiteLinking


@pytest.fixture()
def site_linking() -> ScriptedSiteLinking:
    return ScriptedSiteLinking()


@pytest.fixture()
def link_site_account_handler(
    user_provider: UserProvider,
    site_linking: ScriptedSiteLinking,
) -> LinkSiteAccountHandler:
    return LinkSiteAccountHandler(user_provider, site_linking)
