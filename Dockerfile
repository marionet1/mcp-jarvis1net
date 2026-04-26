# MCP stdio server (Python). Run with stdio attached, e.g.:
#   docker build -t mcp-jarvis1net .
#   docker run --rm -i -e MCP_ALLOWED_ROOTS=/workspace -v "$PWD/data:/workspace:rw" mcp-jarvis1net
FROM python:3.12-alpine
WORKDIR /app

COPY pyproject.toml ./
COPY README.md ./
COPY src ./src
RUN python -m pip install .

ENTRYPOINT ["python", "/app/src/server.py"]
