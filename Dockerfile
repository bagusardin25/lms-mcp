FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.11.11

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --create-home app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["lms-mcp", "serve", "--http"]
