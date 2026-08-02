# Security Policy

## Supported versions

`goldy` is pre-1.0. Only the `master` branch receives security fixes.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Report it privately through GitHub's
[private vulnerability reporting](https://github.com/ftrehn/goldy-telegram-bot/security/advisories/new),
or by email to <dan.kovalev2013@gmail.com>.

Include, as far as you can:

- what an attacker can do, and what access they need to do it
- the affected component (bot command, dialog, worker task, adapter)
- a reproduction — a sequence of updates, or a failing test

You can expect an acknowledgement within 7 days and an assessment within 30.

## Scope

Especially relevant for this bot:

- **Account takeover through a shared contact.** Telegram lets a person forward
  somebody else's contact card, and registration links accounts by phone number.
  `contact.user_id == message.from_user.id` is the security boundary of the whole
  bot; anything that reaches registration without that check is in scope.
- **The authorization gate.** It is fail-closed: everything except `/start` and a
  shared contact stops there unless a user was found, and blocked users are
  stopped in the same place. A route that answers before the gate, or a blocked
  user who still gets a reply, is in scope.
- **Privilege escalation.** `ADMIN` appears in no one's subordinate set, so the
  role cannot be granted through the bot at all — the first administrators come
  only from `GOLDY_ADMIN_PHONE_NUMBERS`. Any path that grants or assumes a role
  outside `SUBORDINATE_ROLES` is in scope.
- **Personal data.** Phone numbers identify people here. A message, log line or
  error that discloses another person's number, name or order history to someone
  who is not them is in scope.
- **Credential exposure.** The Telegram token and the Postgres, Redis and
  RabbitMQ credentials are marked as secret fields in the config loaders
  precisely so a startup failure never logs them; a path that leaks one is in
  scope.
- **Error messages.** A failure rendered to a customer must not carry a host, a
  table name or a query.

Out of scope: findings that require an already-compromised host, denial of
service by volume alone, spam through Telegram's own rate limits, and reports
produced by a scanner without a demonstrated impact.
