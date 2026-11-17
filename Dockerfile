FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.3

# Dependencies first for layer caching; the lockfile pins every version.
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# The pod runs as this user and mounts its data volume at /data.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin tracklist \
    && mkdir /data && chown 10001:10001 /data
USER 10001
ENV STRAVA_TRACKLIST_DATA_DIR=/data \
    STRAVA_TRACKLIST_HOST=0.0.0.0

ENTRYPOINT ["strava-tracklist"]
