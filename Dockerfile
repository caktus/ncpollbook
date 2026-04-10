# Build Python dependencies in a separate stage so build tools never land in the
# final runtime image. Only the compiled /venv directory is carried forward.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS python-builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV VIRTUAL_ENV=/venv

WORKDIR /code/
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    set -ex \
    && BUILD_DEPS="build-essential libpq-dev" \
    && apt-get update && apt-get install -y --no-install-recommends $BUILD_DEPS \
    && uv venv $VIRTUAL_ENV \
    && uv sync --active --locked --no-install-project --no-dev \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false $BUILD_DEPS \
    && rm -rf /var/lib/apt/lists/*


FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS base

WORKDIR /code/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV VIRTUAL_ENV=/venv

# Save commit SHA so it can be referenced later
ARG CONTAINER_IMAGE_TAG=unknown
ENV CONTAINER_IMAGE_TAG=$CONTAINER_IMAGE_TAG

ENV POSTGRESQL_CLIENT_VERSION="18"
RUN set -ex \
    && RUN_DEPS="mime-support postgresql-client-${POSTGRESQL_CLIENT_VERSION} vim curl" \
    && seq 1 8 | xargs -I{} mkdir -p /usr/share/man/man{} \
    && apt-get update \
    && apt-get -y install wget gnupg2 lsb-release \
    && sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list' \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - \
    && apt-get update \
    && apt-get install -y --no-install-recommends $RUN_DEPS \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from the builder stage
COPY --from=python-builder /venv /venv

ENV PATH="/venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"

COPY . /code/

FROM base AS deploy

ARG APP_USER=appuser
ARG APP_USER_UID=999
RUN groupadd -r -g ${APP_USER_UID} ${APP_USER} && useradd --no-log-init -r -u ${APP_USER_UID} -g ${APP_USER} ${APP_USER}

EXPOSE 8000

ENV DJANGO_SETTINGS_MODULE=config.settings

RUN DATABASE_URL='' DJANGO_SECRET_KEY='dummy' python manage.py collectstatic --noinput -c

USER ${APP_USER}:${APP_USER}

ENTRYPOINT ["/code/docker-entrypoint.sh"]

CMD ["python", "manage.py", "runbolt", "--host", "0.0.0.0", "--port", "8000"]
