---
name: add-telegram-screen
description: Add a Telegram command handler or an aiogram-dialog screen, with locales, routing and the auth gate. Use when asked to add a bot command, a dialog, a button or a message to goldy.
---

# Adding a Telegram screen

## 1. Handler or dialog

A command with no state is an ordinary handler. Anything with screens,
pagination or multi-step input is an aiogram-dialog.

```
handlers/<feature>/
  __init__.py    re-export the router and the dialog
  handler.py     the command that opens it
  states.py      StatesGroup
  getters.py     window data
  callbacks.py   button and input handlers
  dialogs.py     the windows
```

## 2. The auth gate already ran

By the time any handler runs, `AuthMiddleware` has put the person in the update
data. Declare it and use it:

```python
async def handle_something(message: Message, i18n: I18nContext, user: UserView) -> None:
```

No `| None` — the gate lets nothing but `/start` and a shared contact past
without a user. Only the registration flow needs the optional form.

Dialog getters receive the same data, so `user: UserView` works there too. Do
not cache the user in `dialog_data`: it is reloaded per update, which is what
makes a change made two screens ago visible when the hub comes back.

## 3. Text

Every Fluent key goes in `common/text_keys.py` as a constant, and its message in
**both** `locales/ru/LC_MESSAGES/common.ftl` and `locales/en/.../common.ftl`.
Never write a key as a literal at the call site.

Windows render text with `I18NFormat`, not `Format`:

```python
I18NFormat(text_keys.ME_PROFILE, name=Format("{name}"))
```

Use a Fluent selector for anything enumerable — roles, statuses, languages — so
the words live with the translations instead of a lookup table in Python.

## 4. Replying

Use `common/replying.py::answer_update` when you have an `Update` rather than a
`Message`. It answers a callback query as a callback: the message behind a
button may be an `InaccessibleMessage`, and writing into one fails at runtime.

## 5. Routing

Add the router to `ROUTERS` and any dialog to `DIALOGS` in `handlers/routers.py`.
Order matters at the end: `fallback_router` matches everything, so anything
after it never runs, and `errors_router` sits last.

Staff-only features filter on the router:

```python
router.message.filter(ChatTypeFilter(...), IsStaffFilter())
```

That is convenience, not security — a customer gets "unknown command" instead of
a refusal that confirms the feature exists. The real check is in the handler,
against the aggregate.

## 6. Errors

Do not `try/except` in a handler. Let the domain error propagate; map it in
`handlers/errors.py` and add the message to both locales.

## 7. Before reporting

```sh
just lint && just mypy && just pre-commit-all
```

Then load the locales, because a missing key fails at render time and nothing
else catches it:

```python
core = setup_telegram_bot_i18n_core(TelegramConfig(bot_token="1:x"))
await core.startup()
core.get("your-new-key", "ru")
```

`presentation/` has no automated coverage. Say plainly that the screen is
unverified unless you actually ran the bot.
