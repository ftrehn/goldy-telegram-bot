"""The settings the catalog receiver refuses to start without.

Its own module for the reason the notifier's loader has one: what is being
checked is not dature's parsing but our decision about where the secret
lives. 1C presents a token, exactly one process compares it, and that process
loads the setting itself — so a mistake here is caught at startup on the
machine running the receiver, rather than as a 401 in the 1C event log on a
different one.
"""

import pytest
from dature.errors.exceptions import DatureConfigError

from goldy.setup.bootstrap.loaders.catalog_receiver_config_loader import (
    CatalogReceiverConfigLoader,
)
from goldy.setup.bootstrap.sources.catalog_receiver_env_source_factory import (
    CatalogReceiverEnvSourceFactory,
)
from goldy.setup.configs.catalog_receiver_config import CatalogReceiverConfig
from tests.unit.factories.env_data_factories import catalog_receiver_env
from tests.unit.factories.source_stubs import catalog_receiver_source_stub
from tests.unit.factories.stub_source_factory import StubSourceFactory
from tests.unit.support import render_exception


def test_every_receiver_variable_reaches_the_config() -> None:
    config = CatalogReceiverConfigLoader(catalog_receiver_source_stub()).load()

    expected = catalog_receiver_env()
    assert config.host == expected["GOLDY_CATALOG_RECEIVER_HOST"]
    assert config.port == int(expected["GOLDY_CATALOG_RECEIVER_PORT"])
    assert config.token == expected["GOLDY_CATALOG_RECEIVER_TOKEN"]
    assert config.max_body_mib == int(expected["GOLDY_CATALOG_RECEIVER_MAX_BODY_MIB"])


def test_the_optional_variables_fall_back_to_their_defaults() -> None:
    """A deployment sets the token and nothing else, and gets a working receiver."""
    token = catalog_receiver_env()["GOLDY_CATALOG_RECEIVER_TOKEN"]
    stub = StubSourceFactory.mirroring(
        CatalogReceiverEnvSourceFactory(),
        {"GOLDY_CATALOG_RECEIVER_TOKEN": token},
    )

    config = CatalogReceiverConfigLoader(stub).load()

    assert config == CatalogReceiverConfig(token=token)


@pytest.mark.parametrize(
    "token",
    ("", "   ", "short", "0123456789012345678901234567890", "   " + "x" * 31 + "   "),
)
def test_a_short_token_is_refused_by_variable_name(token: str) -> None:
    """The message names the variable, because that is what the reader can fix.

    Length is measured after stripping: a token padded to the minimum with
    spaces would pass a naive check, and what would then be compared on both
    sides is the few characters that are left of it.
    """
    loader = CatalogReceiverConfigLoader(
        catalog_receiver_source_stub(GOLDY_CATALOG_RECEIVER_TOKEN=token),
    )

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "GOLDY_CATALOG_RECEIVER_TOKEN" in render_exception(excinfo.value)


@pytest.mark.parametrize("port", ("0", "65536", "-1"))
def test_a_port_outside_the_valid_range_is_refused_by_variable_name(port: str) -> None:
    loader = CatalogReceiverConfigLoader(
        catalog_receiver_source_stub(GOLDY_CATALOG_RECEIVER_PORT=port),
    )

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "GOLDY_CATALOG_RECEIVER_PORT must be between 1 and 65535" in render_exception(
        excinfo.value,
    )


@pytest.mark.parametrize("mib", ("0", "-1"))
def test_a_body_ceiling_below_one_mebibyte_is_refused_by_variable_name(
    mib: str,
) -> None:
    """A ceiling of zero would refuse every batch 1C sends, silently, as 413."""
    loader = CatalogReceiverConfigLoader(
        catalog_receiver_source_stub(GOLDY_CATALOG_RECEIVER_MAX_BODY_MIB=mib),
    )

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "GOLDY_CATALOG_RECEIVER_MAX_BODY_MIB" in render_exception(excinfo.value)
