# --- Dockerfile per Build Linux ---
FROM python:3.11-slim AS linux-builder

# Python settings
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Installazione dipendenze di sistema per GUI e PyInstaller
RUN apt-get update && apt-get install -y \
    binutils \
    python3-tk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pyinstaller

# Copia sorgenti
COPY main.py logic.py .

# Comando di default per la build Linux
CMD ["pyinstaller", "--noconsole", "--onefile", "--collect-all", "customtkinter", "--hidden-import", "PIL._tkinter_finder", "--name", "TimelapsePrep_Linux", "main.py"]
