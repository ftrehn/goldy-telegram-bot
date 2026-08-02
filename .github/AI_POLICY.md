# AI Policy

AI assistants are used on this repository, and that is fine. The rules exist so
that a reviewer can trust a diff without having to guess how it was produced.

## For contributors

- **You own the diff.** Whether you typed it or generated it, you are the author
  and you answer for it in review.
- **Run it.** This codebase has produced several bugs that typed clean and read
  fine: a DI graph that failed only at container build, a locales directory that
  became a package and stopped loading, a `/start` that worked in private chats
  and not in groups. `just linter`, `just static-analysis` and the test suite are
  the minimum bar.
- **Report what actually happened.** If tests fail, say so and show the output.
  If a part is unverified — no Docker, no bot token, no database — say which
  part. Nothing under `presentation/` has automated coverage yet, so a handler,
  dialog or middleware change is unverified by definition. The pull request
  template has a section for exactly this.
- **Do not paste secrets into a model.** `.env` files, bot tokens and production
  connection strings stay out of prompts. The config loaders mark secret fields
  so a startup failure does not log them; do not undo that by hand.
- Disclosure of AI assistance is welcome but not required. Unrunnable or
  unreviewed generated code is not, regardless of disclosure.

## For agents

Agent configuration is checked in and is the source of truth:

- [`AGENTS.md`](../AGENTS.md) — layers, the user model, authorization, wiring,
  testing rules, mandatory commands. Shared by every agent.
- [`CONTEXT.md`](../CONTEXT.md) — the glossary. Use its words; do not invent
  synonyms.
- [`CLAUDE.md`](../CLAUDE.md) — what is specific to working here interactively.
- [`docs/adr/`](../docs/adr/) — decisions that are expensive to reverse, and why.
- `.claude/` — permissions, skills and subagents.

An agent that changes behaviour should update the relevant document in the same
pull request. In particular, a new class of bug belongs in the "Things that have
bitten us" section of `AGENTS.md` — that section is how the next agent avoids
repeating it, and every entry in it is there because somebody already paid for
it once.

## Automated review

CodeRabbit reviews pull requests (`.coderabbit.yaml`). Its comments are advice,
not an approval: a human code owner still reviews and merges.
