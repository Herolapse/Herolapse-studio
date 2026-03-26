# --- Dockerfile per Build Linux ---
FROM python:3.11-slim AS linux-builder

# Installazione dipendenze di sistema per GUI e PyInstaller
RUN apt-get update && apt-get install -y \
    binutils \
    python3-tk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installazione dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pyinstaller

# Copia sorgenti
COPY main.py logic.py .

# Comando di default per la build Linux
# --noconsole nasconde il terminale all'avvio dell'app
# --onefile impacchetta tutto in un unico eseguibile
CMD ["pyinstaller", "--noconsole", "--onefile", "--name", "TimelapsePrep_Linux", "main.py"]

# --- ISTRUZIONI PER WINDOWS (DA ESEGUIRE VIA DOCKER RUN) ---
# Poiché configurare Wine da zero in un Dockerfile è complesso e prono a errori,
# si raccomanda l'uso dell'immagine specializzata cdrx/pyinstaller-windows
