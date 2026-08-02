import re
from dataclasses import dataclass
from typing import Final, Self, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.users.errors import UnsupportedLocaleError

_BCP47_LANGUAGE: Final[re.Pattern[str]] = re.compile(r"^([a-z]{2,3})(?:[-_].*)?$")

DEFAULT_LOCALE: Final[str] = "ru"
SUPPORTED_LOCALES: Final[frozenset[str]] = frozenset({"ru", "en"})


@dataclass(frozen=True, kw_only=True)
class Locale(ValueObject):
    """The language the bot answers this person in.

    Restricted to locales we actually ship translations for. Storing an
    arbitrary tag would let Fluent fall back silently, and the first sign of
    trouble would be a screen of message keys instead of Russian.
    """

    value: str

    @classmethod
    def from_language_code(cls, raw: str | None) -> Self:
        """Reads a messenger's ``language_code``, falling back to the default.

        Platforms send things like ``ru``, ``en-GB`` or ``pt_BR``; only the
        language subtag matters to us. Anything we do not translate becomes the
        default rather than an error — a Brazilian pressing ``/start`` should
        get a working bot, not a refusal.
        """
        if raw is None:
            return cls(value=DEFAULT_LOCALE)

        match = _BCP47_LANGUAGE.match(raw.strip().lower())

        if match is None or match.group(1) not in SUPPORTED_LOCALES:
            return cls(value=DEFAULT_LOCALE)

        return cls(value=match.group(1))

    @override
    def _validate(self) -> None:
        if self.value not in SUPPORTED_LOCALES:
            supported = ", ".join(sorted(SUPPORTED_LOCALES))
            msg = f"Locale {self.value!r} is not supported (have: {supported})."
            raise UnsupportedLocaleError(msg)

    def __str__(self) -> str:
        return self.value
