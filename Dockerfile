FROM node:22-bookworm-slim AS ui-builder

WORKDIR /build/ui
RUN corepack enable
COPY ui/package.json ui/pnpm-lock.yaml ui/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY ui/ ./
RUN pnpm build

FROM python:3.12-slim-bookworm AS runtime

RUN useradd --create-home --uid 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    FILINGSCOPE_ENVIRONMENT=production \
    FILINGSCOPE_DATA_DIR=/home/user/app/data \
    FILINGSCOPE_UI_DIR=/home/user/app/ui-out
WORKDIR /home/user/app

COPY --chown=user:user pyproject.toml README.md ./
COPY --chown=user:user src ./src
COPY --chown=user:user app ./app
COPY --chown=user:user tests/fixtures/sec ./fixtures/sec
COPY --from=ui-builder --chown=user:user /build/ui/out ./ui-out
RUN mkdir -p /home/user/app/data && chown -R user:user /home/user/app/data

USER user
RUN python -m pip install --no-cache-dir . && \
    filingscope-offline-run --fixtures fixtures/sec --data-dir data

EXPOSE 7860
CMD ["uvicorn", "app.hosting:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers"]
