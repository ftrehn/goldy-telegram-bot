"""The one setting the worker cannot start without.

Its own module rather than a pair of cases beside the infrastructure loaders,
because the thing being checked is not really the parsing. It is that the
notifier reads the *same* variable as the bot — one bot, one token, one thing
to rotate — while getting a config object of its own, so the token never lands
in ``configs_provider`` where every process could reach it.
"""

import pytest
from dature.errors.exceptions import DatureConfigError

from goldy.setup.bootstrap.loaders.notification_config_loader import (
    NotificationConfigLoader,
)
from goldy.setup.bootstrap.sources.notification_env_source_factory import (
    NotificationEnvSourceFactory,
)
from tests.unit.factories.env_data_factories import telegram_env
from tests.unit.factories.stub_source_factory import StubSourceFactory
from tests.unit.support import render_exception


def notification_source_stub(**overrides: str) -> StubSourceFactory:
    """Serves the bot's own environment, which is the point of the test.

    Built from ``telegram_env`` rather than a table of its own: if the notifier
    ever started reading a different variable, this stub would stop supplying
    it and the loader would fail here rather than in a deployment.
    """
    return StubSourceFactory.mirroring(
        NotificationEnvSourceFactory(),
        telegram_env(**overrides),
    )


def test_the_notifier_reads_the_same_token_as_the_bot() -> None:
    config = NotificationConfigLoader(notification_source_stub()).load()

    assert config.bot_token == telegram_env()["TELEGRAM_BOT_TOKEN"]


@pytest.mark.parametrize("token", ("", "   ", "not-a-token"))
def test_a_token_of_the_wrong_shape_is_refused_by_name(token: str) -> None:
    """The message names the variable, because that is what the reader can fix.

    Without this the worker starts perfectly well and fails on the first order,
    at 401, in a log nobody is watching.
    """
    loader = NotificationConfigLoader(notification_source_stub(TELEGRAM_BOT_TOKEN=token))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "TELEGRAM_BOT_TOKEN" in render_exception(excinfo.value)


def test_the_token_is_masked_in_error_output() -> None:
    """A startup failure is a log, and a token must never reach one."""
    loader = NotificationConfigLoader(
        notification_source_stub(TELEGRAM_BOT_TOKEN="TOP-SECRET-VALUE"),
    )

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "TOP-SECRET-VALUE" not in render_exception(excinfo.value)
