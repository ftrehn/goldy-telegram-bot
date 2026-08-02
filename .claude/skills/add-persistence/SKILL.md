---
name: add-persistence
description: Map a domain type to the database — TypeDecorator, table, imperative mapping, gateway and migration. Use when asked to persist a new aggregate, add a column, or change the schema in goldy.
---

# Adding persistence

The domain never learns about the ORM. Everything here is imperative mapping in
`infrastructure/persistence/`.

## 1. Types for the value objects

`persistence/models/types.py` — one `TypeDecorator` per value object, with
`cache_ok = True` and `@override` on both directions.

Rebuild through the **constructor**, not a normalising factory. A row holding
something we no longer accept should fail loudly on load rather than quietly
becoming the default — `LocaleType` and `PhoneNumberType` both say so.

Enums are plain text columns, not native database enums, so adding a value is a
code change rather than a migration.

## 2. The table

`persistence/models/<name>.py` — a `Table` with a docstring saying what one row
is and why the keys are what they are.

Prefer a natural key when one exists. `messenger_accounts` is keyed by
`(platform, external_id)`: it makes an account belong to exactly one person for
free, and it is an index seek for the lookup the bot does on every update.

Cross-aggregate rules that the domain cannot enforce belong here as unique
indexes. Say so in the docstring.

## 3. The mapping

```python
def map_<name>_table() -> None:
    mapper_registry.map_imperatively(TheClass, the_table, properties={...})
```

- **`composite` column order must match the dataclass field order.** Composites
  are rebuilt positionally; swapping two columns swaps the values silently.
- Value objects mapped as a composite must not be `kw_only`.
- Anything the ORM assigns to on load must be a mutable dataclass — a frozen
  value object cannot be mapped as an entity.
- Fields that are not columns are left unset on load. `events_collection` is the
  example, and the gateway injects it on every read.

Register it in `models/__init__.py` and in `setups/database_setup.py`. That
function must run exactly once per process.

## 4. The gateway

`infrastructure/adapters/persistence/` — the command gateway hands back whole
aggregates; the query gateway returns views and never aggregates.

Wrap `SQLAlchemyError` in `RepoError`. Flush in `add()` and translate
`IntegrityError` into a meaningful application error, so the caller can tell a
losing race from a broken database.

Filtering on a value-object column needs a cast — the column would otherwise
hand a bare string to the type decorator as though it were one.

## 5. The migration

```sh
just migration "what changed"
just migrate
```

Autogenerate needs a live database. Without one, compile the DDL off the
metadata and transcribe it, then say plainly that it is unverified:

```python
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
print(CreateTable(users_table).compile(dialect=postgresql.dialect()))
```

Revisions live in dated subdirectories; `recursive_version_locations = true` is
what makes alembic find them.

## 6. Before reporting

```sh
just lint && just mypy && just pre-commit-all
```

Then compile the DDL and check it against the migration by eye. Say whether you
ran the migration against a real database.
