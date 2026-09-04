# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS test-stage

ARG PIP_VERSION=26.2.1
ARG SETUPTOOLS_VERSION=84.0.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=testing \
    DEBUG=False

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade \
        pip==${PIP_VERSION} setuptools==${SETUPTOOLS_VERSION} \
    && python -m pip install --no-cache-dir -r requirements.txt

RUN addgroup --gid 10001 testgroup \
    && adduser --uid 10001 --gid 10001 --disabled-password --gecos '' testuser \
    && mkdir -p /app/data \
    && chown -R testuser:testgroup /app

COPY --chown=testuser:testgroup . .
USER 10001:10001

RUN python -m pytest test_app.py -q


FROM python:3.11-slim AS production

ARG PIP_VERSION=26.2.1
ARG SETUPTOOLS_VERSION=84.0.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app

COPY requirements-prod.txt .
RUN python -m pip install --no-cache-dir --upgrade \
        pip==${PIP_VERSION} setuptools==${SETUPTOOLS_VERSION} \
    && python -m pip install --no-cache-dir -r requirements-prod.txt

RUN addgroup --gid 10001 appgroup \
    && adduser --uid 10001 --gid 10001 --disabled-password --gecos '' appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appgroup /app

COPY --from=test-stage --chown=appuser:appgroup /app/app.py /app/wsgi.py ./
COPY --from=test-stage --chown=appuser:appgroup /app/cruciverba/ ./cruciverba/
COPY --from=test-stage --chown=appuser:appgroup /app/templates/ ./templates/
COPY --from=test-stage --chown=appuser:appgroup /app/static/ ./static/

USER 10001:10001
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/healthz', timeout=3)"]

CMD ["gunicorn", "--bind=0.0.0.0:5000", "--workers=2", "--threads=2", "--timeout=30", "--graceful-timeout=30", "--worker-tmp-dir=/tmp", "--no-control-socket", "--access-logfile=-", "--error-logfile=-", "--preload", "wsgi:application"]
