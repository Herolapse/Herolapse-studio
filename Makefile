APP_NAME_LINUX = Herolapse_Studio_Linux
APP_NAME_WIN = Herolapse_Studio
DOCKER_IMAGE_LINUX = herolapse-builder-linux
DOCKER_IMAGE_WIN = tobix/pywine:3.11

.PHONY: all build-linux build-windows clean run-nixos

all: build-linux build-windows

# --- RUN NIXOS ---
run-nixos:
	@echo "Esecuzione su NixOS con dipendenze grafiche..."
	nix-shell -p libxcb libx11 libxext libGL --run "export LD_LIBRARY_PATH=\$$LD_LIBRARY_PATH:\$$(nix-build '<nixpkgs>' -A libxcb -o /tmp/xcb)/lib; ./dist/$(APP_NAME_LINUX)"

# --- BUILD LINUX ---
build-linux:
	@echo "Costruzione immagine Docker per Linux..."
	docker build -t $(DOCKER_IMAGE_LINUX) .
	@echo "Compilazione eseguibile Linux..."
	docker run --rm -v "$(shell pwd)/dist:/app/dist" $(DOCKER_IMAGE_LINUX)
	@echo "Fatto! Eseguibile Linux disponibile in ./dist/$(APP_NAME_LINUX)"

# --- BUILD WINDOWS ---
build-windows:
	@echo "Compilazione .exe per Windows (via Wine/Docker)..."
	docker run --rm \
		-v "$(shell pwd):/src" \
		-w /src \
		$(DOCKER_IMAGE_WIN) \
		sh -c "wine python -m pip install --upgrade pip && wine pip install --upgrade pyinstaller && wine pip install -r requirements.txt && wine pyinstaller --noconsole --onefile --collect-all customtkinter --hidden-import PIL._tkinter_finder --name Herolapse_Studio --icon=assets/herolapse.ico --add-data \"assets/herolapse.ico;assets\" main.py"
	@echo "Fatto! Eseguibile Windows disponibile in ./dist/windows/Herolapse_Studio.exe"

# --- DEBUG WINDOWS (con console visibile per vedere errori) ---
debug-windows:
	@echo "Compilazione .exe di DEBUG per Windows (con console)..."
	docker run --rm \
		-v "$(shell pwd):/src" \
		$(DOCKER_IMAGE_WIN) \
		"python -m pip install --upgrade pip && pip install --upgrade pyinstaller && pip install -r requirements.txt && pyinstaller --onefile --collect-all customtkinter --hidden-import PIL._tkinter_finder --name $(APP_NAME_WIN)_Debug main.py"
	@echo "Fatto! Eseguibile di debug disponibile in ./dist/windows/$(APP_NAME_WIN)_Debug.exe"

# --- PULIZIA ---
clean:
	@echo "Pulizia cartelle build e dist..."
	rm -rf build/ dist/ *.spec
	@echo "Pulizia completata."

# --- HELP ---
help:
	@echo "Comandi disponibili:"
	@echo "  make build-linux    : Genera l'eseguibile per Linux"
	@echo "  make build-windows  : Genera l'eseguibile .exe per Windows"
	@echo "  make all            : Genera entrambi"
	@echo "  make clean          : Rimuove i file di build temporanei"
