# CLAUDE.md

Project instructions live in **[AGENTS.md](AGENTS.md)** — read it before writing
any code. It is the single source of truth for architecture, conventions and
tooling, shared by every agent working on this repository.

This file adds only what is specific to working here interactively.

## Before you start

- `AGENTS.md` — layers, the user model, authorization, wiring, testing rules,
  mandatory commands, and the list of things that have already bitten us.
- `CONTEXT.md` — the glossary. Use its words; do not invent synonyms.
- `docs/adr/` — decisions that are expensive to reverse, and why.

## Working agreements

- **Verify by running, not by reading.** Several bugs here typed clean and read
  fine: a DI graph that failed only at container build, a locales directory that
  became a package and stopped loading, a `/start` that worked in private chats
  and not in groups. Run the thing.
- **Report what actually happened.** If tests fail, say so and show the output.
  If something is unverified — no Docker, no bot token, no database — say which
  part is unverified rather than implying it works.
- **Prefer finishing over starting.** A port with no adapter, a command with no
  caller, or a handler missing from the registry is worse than not having built
  it, because it looks done.
- **Push back when the design is wrong.** Several improvements in this codebase
  came from refusing the first idea: the parameter object instead of a `noqa`,
  the flat identity provider instead of a template-method base, deleting a
  wrapper class rather than keeping it to satisfy a container key.
- When a change touches an area under "Things that have bitten us", re-read that
  entry first.

## Running things

Unit tests need nothing. Integration tests need Docker. Running the bot needs a
token, Postgres, Redis and RabbitMQ.

```sh
uv run --active pytest tests/unit -q     # fast, no Docker
uv run --active pytest tests/integration -q
just pre-commit-all                      # everything CI runs
```

Three processes, three entry points:

```sh
python -m goldy.telegram_bot
taskiq worker goldy.worker_app:create_worker_taskiq_app
taskiq scheduler goldy.scheduler_app:create_scheduler_taskiq_app
```

Scratch scripts go in the session scratchpad directory, never in the repo.

## Reviewing your own work

Before saying a task is done:

1. `just lint` — clean
2. `just mypy` — clean
3. `just import-linter` — 4 contracts kept, if you moved a module
4. `just pre-commit-all` — exit 0
5. `uv run --active pytest tests/unit -q` — green, and say how many ran
6. State plainly what you did **not** verify

Nothing in `presentation/` has automated coverage yet. If you changed a handler,
a dialog or a middleware, say so — that work is unverified by definition until
integration tests exist.
