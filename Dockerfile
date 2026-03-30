# --- Dockerfile per Build Linux ---
FROM python:3.13-slim AS linux-builder

# Python settings
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# UV settings
ENV UV_COMPILE_BYTECODE=1
ENV UV_PROJECT_ENVIRONMENT=/usr/local/

# Installazione dipendenze di sistema per GUI e PyInstaller
RUN apt-get update && apt-get install -y \
    binutils \
    python3-tk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install python requirements
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copia sorgenti
COPY main.py logic.py .

# Comando di default per la build Linux
CMD ["pyinstaller", "--noconsole", "--onefile", "--collect-all", "customtkinter", "--hidden-import", "PIL._tkinter_finder", "--name", "TimelapsePrep_Linux", "main.py"]
