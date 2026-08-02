from typing import Final

from dishka import Provider, Scope

from goldy.application.common.services.user_provider import UserProvider


def services_provider() -> Provider:
    """Application services that sit between the handlers and the ports."""
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(source=UserProvider)
    return provider
