import pytest

from goldy.application.common.ports.users import SiteLinkQueryGateway
from goldy.application.queries.site.get_site_finance_summary.handler import (
    GetSiteFinanceSummaryHandler,
)
from goldy.application.queries.site.get_site_link.handler import GetSiteLinkHandler
from goldy.application.queries.site.preview_site_link.handler import (
    PreviewSiteLinkHandler,
)
from tests.unit.stubs.identity import StubIdentityProvider
from tests.unit.stubs.site import InMemorySiteLinkQueryGateway, ScriptedSiteLinking
from tests.unit.stubs.site_finance import ScriptedSiteFinance


@pytest.fixture()
def site_links() -> InMemorySiteLinkQueryGateway:
    """Nobody is linked to the site unless a test links them."""
    return InMemorySiteLinkQueryGateway()


@pytest.fixture()
def site_linking() -> ScriptedSiteLinking:
    return ScriptedSiteLinking()


@pytest.fixture()
def site_finance() -> ScriptedSiteFinance:
    return ScriptedSiteFinance()


@pytest.fixture()
def get_site_link_handler(
    identity_provider: StubIdentityProvider,
    site_links: SiteLinkQueryGateway,
) -> GetSiteLinkHandler:
    return GetSiteLinkHandler(identity_provider, site_links)


@pytest.fixture()
def preview_site_link_handler(
    site_linking: ScriptedSiteLinking,
) -> PreviewSiteLinkHandler:
    return PreviewSiteLinkHandler(site_linking)


@pytest.fixture()
def get_site_finance_summary_handler(
    identity_provider: StubIdentityProvider,
    site_links: SiteLinkQueryGateway,
    site_finance: ScriptedSiteFinance,
) -> GetSiteFinanceSummaryHandler:
    return GetSiteFinanceSummaryHandler(identity_provider, site_links, site_finance)
