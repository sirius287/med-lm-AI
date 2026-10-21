FROM ghcr.io/astral-sh/uv:0.11.6 AS uv
FROM python:3.13.15-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY services/api/medlm_api ./services/api/medlm_api
COPY packages/backend_domain/medlm_domain ./packages/backend_domain/medlm_domain
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/services/api:/app/packages/backend_domain" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN useradd --system --uid 10001 medlm
USER 10001
EXPOSE 8000
# Proxy headers are intentionally untrusted; see deployment gate for per-IP throttling.
CMD ["uvicorn", "medlm_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
