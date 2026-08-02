from dataclasses import dataclass
from typing import final

from goldy.domain.users.entities.messenger_account import MessengerAccount
from goldy.domain.users.values.full_name import FullName
from goldy.domain.users.values.locale import Locale
from goldy.domain.users.values.phone_number import PhoneNumber


@final
@dataclass(frozen=True, kw_only=True)
class Registration:
    """Everything a platform hands over when somebody shares their contact.

    A parameter object rather than six arguments on ``User.register``: these
    four always travel together, arrive from the same update, and will arrive
    the same way from MAX. Bundling them also keeps the call site readable —
    the alternative is a constructor nobody can invoke without looking it up.

    Not a value object: it carries a :class:`MessengerAccount`, which is a
    mutable entity. Nothing compares two registrations.
    """

    phone_number: PhoneNumber
    full_name: FullName
    account: MessengerAccount
    locale: Locale
