"""Previewing a code: it changes nothing on either side, so this is a query."""

import pytest

from goldy.application.error import SiteLinkCodeInvalidError
from goldy.application.queries.site.preview_site_link.handler import (
    PreviewSiteLinkHandler,
)
from goldy.application.queries.site.preview_site_link.query import PreviewSiteLinkQuery
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from tests.unit.stubs.site import ScriptedSiteLinking

CODE: str = "abcdefghijklmnopqrst"


async def test_the_preview_is_the_sites_answer(
    site_linking: ScriptedSiteLinking,
    preview_site_link_handler: PreviewSiteLinkHandler,
) -> None:
    view = await preview_site_link_handler.handle(
        PreviewSiteLinkQuery(code=CODE, platform=MessengerPlatform.TELEGRAM),
    )

    assert view is site_linking.preview_answer


async def test_the_code_is_normalized_before_being_sent(
    site_linking: ScriptedSiteLinking,
    preview_site_link_handler: PreviewSiteLinkHandler,
) -> None:
    await preview_site_link_handler.handle(
        PreviewSiteLinkQuery(
            code=f" {CODE.upper()} ", platform=MessengerPlatform.TELEGRAM
        ),
    )

    assert site_linking.previews == [(CODE, MessengerPlatform.TELEGRAM)]


async def test_an_invalid_code_never_reaches_the_site(
    site_linking: ScriptedSiteLinking,
    preview_site_link_handler: PreviewSiteLinkHandler,
) -> None:
    with pytest.raises(SiteLinkCodeInvalidError):
        await preview_site_link_handler.handle(
            PreviewSiteLinkQuery(code="not a code", platform=MessengerPlatform.TELEGRAM),
        )

    assert site_linking.previews == []


async def test_the_site_refusing_an_unknown_code_propagates(
    site_linking: ScriptedSiteLinking,
    preview_site_link_handler: PreviewSiteLinkHandler,
) -> None:
    site_linking.errors = [SiteLinkCodeInvalidError("unknown code")]

    with pytest.raises(SiteLinkCodeInvalidError):
        await preview_site_link_handler.handle(
            PreviewSiteLinkQuery(code=CODE, platform=MessengerPlatform.TELEGRAM),
        )
