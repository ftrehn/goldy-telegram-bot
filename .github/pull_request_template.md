## Summary

<!-- What does this PR do, and why? -->

## Motivation / context

<!-- Link issues; explain the design choice if it is not obvious from the diff. -->

## Changes

-

## Checklist

- [ ] `just linter` is clean (ruff format, ruff check, codespell)
- [ ] `just static-analysis` is clean (mypy, bandit, semgrep, import-linter)
- [ ] `uv run --active pytest tests/unit -q` is green — state how many tests ran
- [ ] New behaviour is tested: unit tests for domain / application, integration
      tests for anything crossing a process boundary
- [ ] Fixtures live in `conftest.py`, builders in `tests/unit/factories/`,
      stubs in `tests/unit/stubs/`
- [ ] Integration tests resolve **ports** from the container, never adapters
- [ ] Dependency rule preserved: `presentation → application → domain`, and
      `infrastructure` does not import `setup`
- [ ] Vocabulary follows `CONTEXT.md` — no new synonym for an existing term
- [ ] Every new Fluent string has a key in `common/text_keys.py`, in **both**
      `ru` and `en`, and no literal key at a call site
- [ ] Every new domain error is rendered in `handlers/errors.py`
- [ ] A schema change ships with an alembic revision, and `just migrate` applies
      cleanly from scratch
- [ ] A new class of bug is recorded under "Things that have bitten us" in
      `AGENTS.md`
- [ ] PR title follows Conventional Commits

## What I did not verify

<!-- No Docker, no bot token, no database — say which part is unverified rather
     than implying it works. Nothing under `presentation/` has automated
     coverage yet: if you changed a handler, a dialog or a middleware, that work
     is unverified by definition until integration tests exist. Say so. -->
