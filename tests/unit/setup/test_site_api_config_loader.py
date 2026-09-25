"""The settings the worker reaches the site with, and the ones it must refuse.

What is worth pinning is not that dature parses a float. It is the decisions:
the token must only travel over https except to a host where it never leaves
the machine, the page size stays inside what the site accepts (and under the
database's bind-parameter ceiling), a broken schedule fails at startup rather
than silently never firing, and the token never reaches a log.
"""

import pytest
from dature.errors.exceptions import DatureConfigError

from goldy.setup.bootstrap.loaders.site_api_config_loader import SiteApiConfigLoader
from goldy.setup.bootstrap.sources.site_api_env_source_factory import (
    SiteApiEnvSourceFactory,
)
from goldy.setup.configs.site_api_config import (
    DEFAULT_CATALOG_SYNC_CRON,
    DEFAULT_SITE_API_PAGE_SIZE,
    DEFAULT_SITE_API_TIMEOUT_SECONDS,
)
from tests.unit.factories.env_data_factories import site_api_env
from tests.unit.factories.source_stubs import site_api_source_stub
from tests.unit.factories.stub_source_factory import StubSourceFactory
from tests.unit.support import render_exception


def test_a_valid_environment_loads_every_setting() -> None:
    config = SiteApiConfigLoader(
        site_api_source_stub(
            GOLDY_SITE_API_TIMEOUT="12.5",
            GOLDY_SITE_API_PAGE_SIZE="250",
            GOLDY_CATALOG_SYNC_CRON="0 * * * *",
        ),
    ).load()

    assert config.base_url == "https://tkgoldy.ru/api/v1"
    assert config.token == site_api_env()["GOLDY_SITE_API_TOKEN"]
    assert config.timeout_seconds == pytest.approx(12.5)
    assert config.page_size == 250
    assert config.catalog_sync_cron == "0 * * * *"


def test_the_tuning_variables_fall_back_to_their_defaults() -> None:
    env = {
        "GOLDY_SITE_API_URL": "https://tkgoldy.ru/api/v1",
        "GOLDY_SITE_API_TOKEN": "tkg_abc",
    }
    source = StubSourceFactory.mirroring(SiteApiEnvSourceFactory(), env)

    config = SiteApiConfigLoader(source).load()

    assert config.timeout_seconds == pytest.approx(DEFAULT_SITE_API_TIMEOUT_SECONDS)
    assert config.page_size == DEFAULT_SITE_API_PAGE_SIZE
    assert config.catalog_sync_cron == DEFAULT_CATALOG_SYNC_CRON


@pytest.mark.parametrize(
    "url",
    (
        "http://localhost:8088/api/v1",
        "http://127.0.0.1/api/v1",
        "http://[::1]:8088/api/v1",
        "http://host.docker.internal/api/v1",
        "http://tkgoldy_web/api/v1",
    ),
)
def test_plain_http_is_allowed_where_the_token_never_leaves_the_machine(
    url: str,
) -> None:
    config = SiteApiConfigLoader(site_api_source_stub(GOLDY_SITE_API_URL=url)).load()

    assert config.base_url == url


@pytest.mark.parametrize(
    "url",
    (
        "http://tkgoldy.ru/api/v1",
        "ftp://tkgoldy.ru/api/v1",
        "tkgoldy.ru/api/v1",
        "https://tkgoldy.ru/api/v1?token=x",
        "https://",
        "",
    ),
)
def test_an_address_the_token_must_not_travel_to_is_refused_by_name(url: str) -> None:
    """The Bearer token rides in a header; over plain http anyone on the path reads it."""
    loader = SiteApiConfigLoader(site_api_source_stub(GOLDY_SITE_API_URL=url))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "GOLDY_SITE_API_URL" in render_exception(excinfo.value)


@pytest.mark.parametrize("token", ("", "tkg abc"))
def test_a_blank_or_broken_token_is_refused_by_name(token: str) -> None:
    loader = SiteApiConfigLoader(site_api_source_stub(GOLDY_SITE_API_TOKEN=token))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "GOLDY_SITE_API_TOKEN" in render_exception(excinfo.value)


def test_the_token_is_masked_in_error_output() -> None:
    """A startup failure is a log, and the key to the site must never reach one."""
    loader = SiteApiConfigLoader(
        site_api_source_stub(
            GOLDY_SITE_API_TOKEN="TOP-SECRET-VALUE",
            GOLDY_SITE_API_URL="http://tkgoldy.ru",
        ),
    )

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "TOP-SECRET-VALUE" not in render_exception(excinfo.value)


@pytest.mark.parametrize("timeout", ("0", "-1", "601"))
def test_a_timeout_out_of_bounds_is_refused_by_name(timeout: str) -> None:
    loader = SiteApiConfigLoader(site_api_source_stub(GOLDY_SITE_API_TIMEOUT=timeout))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "GOLDY_SITE_API_TIMEOUT" in render_exception(excinfo.value)


@pytest.mark.parametrize("page_size", ("0", "1001"))
def test_a_page_size_the_site_does_not_accept_is_refused_by_name(page_size: str) -> None:
    loader = SiteApiConfigLoader(site_api_source_stub(GOLDY_SITE_API_PAGE_SIZE=page_size))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "GOLDY_SITE_API_PAGE_SIZE" in render_exception(excinfo.value)


@pytest.mark.parametrize("cron", ("", "*/15 * * *", "every fifteen minutes"))
def test_a_schedule_that_is_not_five_fields_is_refused_by_name(cron: str) -> None:
    """Taskiq skips a schedule it cannot parse, and the catalog quietly stops updating."""
    loader = SiteApiConfigLoader(site_api_source_stub(GOLDY_CATALOG_SYNC_CRON=cron))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "GOLDY_CATALOG_SYNC_CRON" in render_exception(excinfo.value)
