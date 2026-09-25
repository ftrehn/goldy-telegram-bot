import re
from typing import Final

from goldy.application.error import SiteLinkCodeInvalidError

LINK_CODE_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-z2-7]{20}")
"""The site's linking code: twenty characters of lowercase base32."""


def normalize_link_code(raw: str) -> str:
    """The code as the site issued it, or a refusal before any request.

    A code that cannot be the site's is refused here rather than sent: the
    site would say "unknown code" anyway, and a request per typo is a request
    the site's rate limit counts against every other customer of the bot.

    Raises:
        SiteLinkCodeInvalidError: the text is not a linking code at all.
    """
    code = raw.strip().lower()

    if LINK_CODE_PATTERN.fullmatch(code) is None:
        msg = "This is not a site linking code."
        raise SiteLinkCodeInvalidError(msg)

    return code
