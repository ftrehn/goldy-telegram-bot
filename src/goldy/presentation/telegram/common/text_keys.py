from typing import Final

"""Every Fluent message key the bot asks for, in one place.

Constants rather than literals at the call site for two reasons. A key is a
contract with the ``.ftl`` files, and the same one is often needed in two
places — ``auth-registration-required`` is used by both the gate and the
``/start`` handler, and two literals spelled slightly differently is how one of
them starts pointing at a message nobody wrote. And renaming a message becomes
one edit here instead of a grep across the presentation layer.

Names mirror the keys, so the mapping stays obvious in both directions.
"""

# Registration and the gate in front of it.
AUTH_REGISTRATION_REQUIRED: Final[str] = "auth-registration-required"
AUTH_SHARE_PHONE_BUTTON: Final[str] = "auth-share-phone-button"
AUTH_CONTACT_NOT_YOURS: Final[str] = "auth-contact-not-yours"
AUTH_CONTACT_WITHOUT_NUMBER: Final[str] = "auth-contact-without-number"

# Refusals, one per rule the domain can raise.
ERROR_FORBIDDEN: Final[str] = "error-forbidden"
ERROR_BLOCKED: Final[str] = "error-blocked"
ERROR_NOT_FOUND: Final[str] = "error-not-found"
ERROR_ALREADY_EXISTS: Final[str] = "error-already-exists"
ERROR_LAST_ACCOUNT: Final[str] = "error-last-account"
ERROR_UNKNOWN: Final[str] = "error-unknown"
"""Shown when nothing more specific fits. Used by the gate and the error
handler alike, which is exactly the duplication this module exists to stop."""

# Greetings.
START_WELCOME: Final[str] = "start-welcome"
START_WELCOME_BACK: Final[str] = "start-welcome-back"

# The commands anyone can reach.
HELP_CUSTOMER: Final[str] = "help-customer"
HELP_STAFF: Final[str] = "help-staff"
"""Two messages rather than one with a conditional.

Fluent can branch on a variable, but a customer must not even be told that
``/admin`` exists — and a selector that hides a line is one edit away from
showing it.
"""

ME_PROFILE: Final[str] = "me-profile"
UNKNOWN_COMMAND: Final[str] = "unknown-command"
CANCELLED: Final[str] = "cancelled"
