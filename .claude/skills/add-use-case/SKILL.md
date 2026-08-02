---
name: add-use-case
description: Add a command or query end to end — request, handler, ports, DI registration, mediator registration and tests. Use when asked to add a new command, query, or background operation to goldy.
---

# Adding a use case

A use case is only finished when it is **reachable**. Half of it — a handler
with no registration, a port with no adapter, a command nothing dispatches —
looks done and is not. Work top to bottom and check the last section before
reporting.

## 1. Command or query

| | Command | Query |
|---|---|---|
| Marker | `Command[TResponse]` | `Query[TResponse]` |
| Pipelines | transaction + events | **none** |
| Handler base | `CommandHandler` | `QueryHandler` |
| Gateway | `UserCommandGateway` (aggregates) | `UserQueryGateway` (views) |

A query must not mutate. If it needs a transaction, it is a command.

## 2. Domain first, if the concept is new

Add value objects, aggregate methods and errors under `domain/users/` before
touching the application layer. Use the words `CONTEXT.md` defines; if the
concept is genuinely new, add it there and say so.

Decide where the behaviour belongs:

- **Aggregate method** if it is decidable from the aggregate's own fields. It
  records its own event.
- **Domain service** only if it needs something the aggregate lacks — a
  generator, or a second aggregate.

Value objects inherit `ValueObject`, implement `_validate` with `@override`, and
raise a `DomainFieldError` subclass from `domain/users/errors.py`.

If a constructor ends up with more than five parameters, `PLR0913` will fire.
Reach for a parameter object — `Registration` is the precedent — not a `noqa`.

## 3. The use case

```
application/commands/users/<use_case>/
  __init__.py    empty
  command.py     the request dataclass, and its response if it is not a view
  handler.py     the handler
```

- Collaborators in `__init__`, stored as `Final`.
- `handle()` with `@override`.
- Catch `AppError`, never `Exception`.
- Never catch-and-return-success: the transaction pipeline would commit
  partially applied work.

Authorization is two steps and both are needed:

```python
self._access_service.authorize(CanManageSubordinate(), context=...)
target.block(reason)
```

Missing ports go in `application/common/ports/` as a `Protocol` with
`@abstractmethod`.

## 4. Wire it — every place

Forgetting one produces a use case that fails only at runtime.

1. **Adapter** for every new port, in `infrastructure/adapters/`.
2. **`handlers_provider.py`** — add the handler to the right group.
   `bootstrap_handlers_provider` for anything nobody issues;
   `user_handlers_provider` for anything needing an `IdentityProvider`;
   `outbox_handlers_provider` for anything needing a broker. Putting it in the
   wrong group makes a container refuse to build — which is the point.
3. **`gateways_provider.py`** — bind each new port to its adapter.
4. **`mediator_provider.py`** — `registry.add_request_handler(TheCommand, TheHandler)`.

## 5. Expose it

An ordinary command gets a handler in `presentation/telegram/handlers/`;
anything with screens gets an aiogram-dialog. See the `add-telegram-screen`
skill.

Add any new domain error to `ERROR_TEXTS` in
`presentation/telegram/handlers/errors.py`, and its message to **both**
`.ftl` files. An unmapped error falls through to the generic message.

## 6. Tests

- Unit: `tests/unit/application/commands/test_<use_case>.py` against the
  in-memory stubs. Cover the success path, each refusal, and idempotency if the
  operation can be repeated.
- Fixtures in the nearest `conftest.py`; builders in `tests/unit/factories/`;
  stubs in `tests/unit/stubs/`.

## 7. Before reporting

```sh
just lint && just mypy && just pre-commit-all
uv run --active pytest tests/unit -q
```

Say how many tests ran, and name anything you could not verify.
