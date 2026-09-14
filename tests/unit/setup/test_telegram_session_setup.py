"""The one decision behind the Bot API transport: proxy or not.

Everything else — that ``AiohttpSession`` opens a SOCKS connector for a
``socks5://`` URL — is aiogram's and aiohttp-socks's business. What is ours is
that a configured URL reaches the session, that no URL means no session of
ours, and that the password inside the URL stays out of the log.
"""

import logging

import pytest

from goldy.setup.bootstrap.setups.telegram_session_setup import make_telegram_session

PROXY_URL = "socks5://user:TOP-SECRET-VALUE@proxy.internal:1080"


def test_no_proxy_means_no_session_of_our_own() -> None:
    """``None`` lets the ``Bot`` build its default session — one code path, not two."""
    session = make_telegram_session(None)

    assert session is None


def test_a_proxy_url_becomes_a_session_that_goes_through_it() -> None:
    session = make_telegram_session(PROXY_URL)

    assert session is not None
    assert session.proxy == PROXY_URL


def test_the_proxy_password_never_reaches_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The startup log is the first thing pasted into a chat when a deploy fails."""
    with caplog.at_level(logging.INFO):
        make_telegram_session(PROXY_URL)

    assert "proxy.internal:1080" in caplog.text
    assert "TOP-SECRET-VALUE" not in caplog.text
