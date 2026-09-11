# One image, four processes. The bot, the worker, the scheduler and the catalog
# seeder share a dependency set and differ only in the command, so building four
# images would mean four things to keep in step and four chances to deploy a
# mismatched pair.
#
#   docker build -t goldy:latest .
#   docker run --env-file .env goldy:latest                      # bot
#   docker run --env-file .env goldy:latest taskiq worker ...    # worker
#
# The default command is the bot; docker-compose.yaml overrides it per service.

FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# hatch-vcs shells out to git, so the binary has to exist in the stage that
# builds the package - .git in the build context is necessary and not enough.
# Builder stage only: the runtime image never sees it. safe.directory is the
# second half: the checkout is owned by the host user and the build runs as
# root, and git refuses to read a repository it considers foreign, which
# surfaces three steps later as an unexplained version error.
RUN apt-get update && apt-get install --no-install-recommends --yes git && rm -rf /var/lib/apt/lists/* && git config --global --add safe.directory /app

WORKDIR /app

# Dependencies resolve from the lock alone, in their own layer: application code
# changes on every deploy and the dependency set does not, so this layer stays
# cached across the builds that happen most often.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# .git comes with the context on purpose — hatch-vcs derives the version from it,
# and a build without it fails rather than guessing. See .dockerignore.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.14-slim AS runtime

# A numeric uid is what a mounted volume's ownership can be matched against on
# the host; a name-only user leaves that to whatever the base image assigned.
RUN groupadd --gid 1000 goldy \
    && useradd --uid 1000 --gid 1000 --create-home goldy

WORKDIR /app

COPY --from=builder --chown=goldy:goldy /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER goldy

CMD ["python", "-m", "goldy.telegram_bot"]
