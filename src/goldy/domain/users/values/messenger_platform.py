from enum import StrEnum


class MessengerPlatform(StrEnum):
    """A messenger the bot runs in.

    Persisted as its value in a plain text column rather than a native database
    enum, so adding a platform is a code change and not a migration.
    """

    TELEGRAM = "telegram"
    MAX = "max"
