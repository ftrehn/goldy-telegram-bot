from typing import Any, Final, final, override

from aiogram_dialog.api.internal import TextWidget
from aiogram_dialog.api.protocols import DialogManager
from aiogram_dialog.widgets.common import WhenCondition
from aiogram_dialog.widgets.text import Text
from aiogram_i18n import I18nContext
from magic_filter import MagicFilter

I18N_CONTEXT_KEY: Final[str] = "i18n"

type Resolvable = TextWidget | MagicFilter | str | float | bool


@final
class I18NFormat(Text):
    """A dialog text that renders through Fluent instead of ``str.format``.

    Windows are built at import time, long before anybody's language is known,
    so they hold a message key and resolve it per render against the
    ``I18nContext`` the middleware put in the update data.

    Placeholders may be widgets or magic filters, which is what lets a window
    interpolate values the getter produced without the key having to know where
    they came from.
    """

    def __init__(
        self,
        text: str,
        when: WhenCondition | None = None,
        /,
        **mapping: Resolvable,
    ) -> None:
        super().__init__(when)
        self.text: Final[str] = text
        self.mapping: Final[dict[str, Resolvable]] = dict(mapping)

    @override
    async def _render_text(self, data: dict[str, Any], manager: DialogManager) -> str:
        i18n: I18nContext | None = manager.middleware_data.get(I18N_CONTEXT_KEY)

        if i18n is None:
            msg = "No I18nContext in the update data — is the i18n middleware set up?"
            raise RuntimeError(msg)

        return i18n.get(self.text, **await self._resolve_mapping(data, manager))

    async def _resolve_mapping(
        self,
        data: dict[str, Any],
        manager: DialogManager,
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {}

        for key, value in self.mapping.items():
            rendered = await self._resolve(value, data, manager)
            # Fluent has no concept of null, and passing one renders the
            # literal word into the message.
            resolved[key] = "" if rendered is None else rendered

        return resolved

    @staticmethod
    async def _resolve(
        value: Resolvable,
        data: dict[str, Any],
        manager: DialogManager,
    ) -> Any:
        if isinstance(value, TextWidget):
            return await value.render_text(data, manager)
        if isinstance(value, MagicFilter):
            return value.resolve(data)
        return value
