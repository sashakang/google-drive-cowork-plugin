FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ server/

# Mount config and credentials at runtime:
#   docker run -v ~/.config/gdocs-mcp:/root/.config/gdocs-mcp gdocs-mcp

CMD ["python3", "-m", "server.main"]
