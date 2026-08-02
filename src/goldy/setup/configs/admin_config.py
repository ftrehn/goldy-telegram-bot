from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AdminConfig:
    """Who gets the administrator role without anybody granting it.

    ``ADMIN`` sits above every role in the hierarchy, so no subject may hand it
    out through the bot — which leaves the first administrator with no way to
    exist. This config is that way.

    Numbers rather than platform ids on purpose: identity in this system is the
    phone number, and an administrator listed by ``telegram_id`` would stop
    being one the moment they wrote from MAX.

    Attributes:
        phone_numbers: Comma-separated numbers, in whatever shape is convenient
            to type — they are normalised the same way a registration is. Kept
            raw here because a config object reads the environment, and giving
            meaning to what it read is the adapter's job.
    """

    phone_numbers: str = ""
