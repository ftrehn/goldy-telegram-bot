from importlib.resources import files  # nosemgrep: python37-compatibility-importlib2
from pathlib import Path
from typing import Final

LOCALES_DIRECTORY: Final[str] = "locales"

LOCALES_PATH: Final[Path] = (
    Path(str(files("goldy.presentation.telegram"))) / LOCALES_DIRECTORY
)
"""Root of the Fluent translations, with ``{locale}/LC_MESSAGES`` underneath.

Resolved through ``importlib.resources`` rather than from ``__file__`` or the
working directory: both work while the project is a source checkout and stop
working the moment it is installed, which is the least convenient time to find
out that the bot answers in message keys.

The directory deliberately has no ``__init__.py``. It is data, not code — and
making it a package would put a ``__pycache__`` beside the languages, which the
Fluent core reads as a locale of its own and then fails to find any ``.ftl`` in.
"""
