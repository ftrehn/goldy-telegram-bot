import pytest

from goldy.application.commands.site.unlink_site_account.handler import (
    UnlinkSiteAccountHandler,
)
from goldy.application.common.services.user_provider import UserProvider
from tests.unit.stubs.site import ScriptedSiteLinking


@pytest.fixture()
def site_linking() -> ScriptedSiteLinking:
    return ScriptedSiteLinking()


@pytest.fixture()
def unlink_site_account_handler(
    user_provider: UserProvider,
    site_linking: ScriptedSiteLinking,
) -> UnlinkSiteAccountHandler:
    return UnlinkSiteAccountHandler(user_provider, site_linking)
