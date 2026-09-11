from importlib.resources import files  # nosemgrep: python37-compatibility-importlib2
from pathlib import Path
from typing import Final

LOCALES_DIRECTORY: Final[str] = "locales"

NOTIFICATION_RESOURCE: Final[str] = "notifications.ftl"

NOTIFICATION_LOCALES_PATH: Final[Path] = (
    Path(str(files("goldy.infrastructure.adapters.notifications"))) / LOCALES_DIRECTORY
)
"""Root of the notifier's Fluent translations, ``{locale}/LC_MESSAGES`` below.

Its own directory rather than the bot's. The worker is a separate process that
does not import ``presentation`` and must not start doing so — the layering
contract forbids it, and a worker that dragged in aiogram-dialog to read a
sentence would be paying for a dialogue engine to send a text message.

Resolved through ``importlib.resources`` rather than from ``__file__`` or the
working directory: both work while the project is a source checkout and stop
working the moment it is installed as a wheel.

The directory deliberately has no ``__init__.py``. It is data, not code, and
making it a package would put a ``__pycache__`` beside the languages — which
the Fluent loader reads as a locale of its own and then finds no ``.ftl`` in.
"""
