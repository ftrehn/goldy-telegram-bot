# Contributing

Thanks for taking the time. This document covers the mechanics; the
architecture, the layer rules and the vocabulary live in
[AGENTS.md](../AGENTS.md) and [CONTEXT.md](../CONTEXT.md) — read both before
writing code.

## Setup

Requires Python 3.14, [uv](https://docs.astral.sh/uv/) and
[just](https://just.systems/). Docker is needed only for integration tests and
for the backing services.

```sh
uv sync --group dev
uv run prek install --install-hooks   # lint + conventional commit-msg hooks
cp .env.example .env        # then fill in TELEGRAM_BOT_TOKEN and POSTGRES_PASSWORD
just migrate
```

Running the bot needs a token, Postgres, Redis and RabbitMQ. Three processes,
three entry points:

```sh
python -m goldy.telegram_bot
taskiq worker goldy.worker_app:create_worker_taskiq_app
taskiq scheduler goldy.scheduler_app:create_scheduler_taskiq_app
```

## The loop

```sh
just linter            # ruff format + ruff check + codespell
just static-analysis   # mypy + bandit + semgrep + import-linter
uv run --active pytest tests/unit -q     # fast, no Docker
uv run --active pytest -q                # everything, needs Docker
just pre-commit-all                      # everything the hooks run
```

All of it must be clean before a PR. `just test-ci` reproduces exactly what CI
runs, including the coverage report.

## Conventions worth knowing up front

- **Verify by running, not by reading.** Several bugs here typed clean and read
  fine: a DI graph that failed only at container build, a locales directory that
  became a package and stopped loading, a `/start` that worked in private chats
  and not in groups.
- **No `from __future__ import annotations`.** PEP 649 handles it, and dishka and
  adaptix resolve constructor annotations at runtime — moving a parameter type
  under `if TYPE_CHECKING` breaks the container at startup. `TC001`/`TC002`/
  `TC003` are disabled deliberately; do not "fix" them.
- **Accept ruff's autofixes; do not silence a rule.** A signature that trips
  `PLR0913` usually wants a parameter object, which is why `User.register` takes
  a `Registration`. If a rule is genuinely wrong for a whole class of files, add
  a scoped `per-file-ignores` entry with a comment saying why.
- **Use the words in `CONTEXT.md`.** A *user* is a person, not an account; the
  phone number is the identity; an *external id* never identifies a user on its
  own.
- **Fixtures live only in `conftest.py`.** Builders go in
  `tests/unit/factories/`, stubs in `tests/unit/stubs/`.
- **Integration tests name ports, never implementations.** A test that
  constructs `SqlAlchemyUserCommandGateway(session)` is a test of SQLAlchemy and
  breaks the day the technology does.
- **Do not test libraries.** Building a dishka container to assert dishka wires
  it is a test of dishka. Test the decisions we made.
- **Every Fluent string gets a key in `common/text_keys.py`**, in both `ru` and
  `en`. No literal keys at call sites — two literals spelled differently is how
  one starts pointing at a message nobody wrote.
- **Every new domain error must be rendered in `handlers/errors.py`.**

Before touching an area, read its entry under "Things that have bitten us" in
`AGENTS.md`. Every entry there is a bug somebody already paid for.

## Commits and pull requests

Commit messages and PR titles follow
[Conventional Commits](https://www.conventionalcommits.org/) — enforced by the
`conventional-pre-commit` hook locally and by the PR Title workflow on GitHub.

```
feat: adding dialog for user
fix: stop comparing message text to "/start"
test: adding config loader and registration tests
```

Fill in the pull request template, including the "What I did not verify"
section. Reporting that something is untested is useful; implying it works is
not — and nothing under `presentation/` has automated coverage yet.

## Migrations

```sh
just migration "add orders table"   # autogenerate
just migrate                        # apply
```

Revisions live in dated subdirectories, which is why `alembic.ini` sets
`recursive_version_locations = true` — without it alembic silently finds none.
Check the generated revision by hand: imperative mappings and autogenerate do
not always agree, and a `composite` whose column order drifts swaps two values
with nothing failing until somebody reads a profile.
