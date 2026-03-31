import threading
import os
from datetime import datetime
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox
import shutil
from typing import Callable


class SequenceBuilder(ctk.CTkFrame):
    """Tab 3: Preparazione sequenze per Adobe Premiere Pro."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.logic = SequenceBuilderLogic()
        self.input_dir = ""
        self.output_dir = ""
        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Rinomina sequenze per Adobe Premiere",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=20)

        # Selezione Cartelle
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.pack(pady=10, fill="x", padx=40)

        self.btn_in = ctk.CTkButton(
            folder_frame, text="Seleziona Cartella Input", command=self.select_input
        )
        self.btn_in.pack(pady=10)
        self.lbl_in = ctk.CTkLabel(
            folder_frame,
            text="Nessuna cartella",
            font=ctk.CTkFont(size=12, slant="italic"),
        )
        self.lbl_in.pack(pady=10)

        folder_frame_out = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame_out.pack(pady=10, fill="x", padx=40)

        self.btn_out = ctk.CTkButton(
            folder_frame_out,
            text="Seleziona Cartella Output",
            command=self.select_output,
        )
        self.btn_out.pack(pady=10)
        self.lbl_out = ctk.CTkLabel(
            folder_frame_out,
            text="Nessuna cartella",
            font=ctk.CTkFont(size=12, slant="italic"),
        )
        self.lbl_out.pack(pady=10)

        # Prefisso File
        prefix_frame = ctk.CTkFrame(self, fg_color="transparent")
        prefix_frame.pack(pady=20)
        ctk.CTkLabel(
            prefix_frame, text="Prefisso File:", font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=10)
        self.entry_prefix = ctk.CTkEntry(prefix_frame, width=200)
        self.entry_prefix.insert(0, "timelapse")
        self.entry_prefix.pack(side="left", padx=10)

        # Status e Progress Bar
        self.status_label = ctk.CTkLabel(
            self, text="Pronto per l'esportazione", font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(pady=(40, 5))

        self.progress_bar = ctk.CTkProgressBar(self, width=500)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)

        # Pulsante Avvia
        self.btn_start = ctk.CTkButton(
            self,
            text="AVVIA ESPORTAZIONE PREMIERE",
            height=60,
            command=self.start_export,
            fg_color="green",
            hover_color="darkgreen",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.btn_start.pack(pady=40)

    def select_input(self):
        path = filedialog.askdirectory()
        if path:
            self.input_dir = path
            self.lbl_in.configure(text=path)

    def select_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir = path
            self.lbl_out.configure(text=path)

    def start_export(self):
        if not self.input_dir or not self.output_dir:
            messagebox.showwarning(
                "Dati mancanti",
                "Seleziona sia la cartella di input che quella di output.",
            )
            return

        prefix = self.entry_prefix.get().strip()
        if not prefix:
            messagebox.showwarning(
                "Prefisso mancante", "Inserisci un prefisso per i file."
            )
            return

        self.btn_start.configure(state="disabled")
        threading.Thread(
            target=self._export_thread, args=(prefix,), daemon=True
        ).start()

    def _export_thread(self, prefix):
        def update_ui(curr, total, msg):
            # Aggiornamento thread-safe via after()
            self.after(0, lambda: self.progress_bar.set(curr / total))
            self.after(0, lambda: self.status_label.configure(text=f"{msg}"))

        try:
            self.logic.process_renaming(
                self.input_dir, self.output_dir, prefix, update_ui
            )
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Esportazione Completata",
                    "Le immagini sono state ordinate e rinominate con successo!",
                ),
            )
        except Exception as e:
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Errore", f"Si è verificato un errore: {str(e)}"
                ),
            )
        finally:
            self.after(0, lambda: self.btn_start.configure(state="normal"))
            self.after(
                0, lambda: self.status_label.configure(text="Pronto per l'esportazione")
            )


class SequenceBuilderLogic:
    """
    Logica per la rinominazione sequenziale delle immagini per Adobe Premiere
    """

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}

    def get_capture_date(self, filepath: str) -> datetime:
        """Estrae la data di scatto (EXIF) con fallback sulla data di modifica file."""
        try:
            with Image.open(filepath) as img:
                exif = img._getexif()
                if exif:
                    # 36867 è il tag ID per DateTimeOriginal
                    dt_str = exif.get(36867)
                    if dt_str:
                        return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass

        # Fallback sulla data di modifica se l'EXIF non è presente o è corrotto
        return datetime.fromtimestamp(os.path.getmtime(filepath))

    def process_renaming(
        self,
        input_dir: str,
        output_dir: str,
        prefix: str,
        progress_callback: Callable[[int, int, str], None],
    ):
        """Scansiona, ordina e copia le immagini rinominandole in modo sequenziale."""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 1. Scansione e Estrazione Date
        files = [
            f
            for f in os.listdir(input_dir)
            if os.path.splitext(f)[1].lower() in self.IMAGE_EXTENSIONS
        ]

        total_files = len(files)
        if total_files == 0:
            return

        image_data = []
        for i, filename in enumerate(files):
            filepath = os.path.join(input_dir, filename)
            capture_date = self.get_capture_date(filepath)
            image_data.append((filepath, capture_date))

            if i % 10 == 0 or i == total_files - 1:
                progress_callback(
                    i + 1, total_files, f"Analisi date: {i + 1}/{total_files}"
                )

        # 2. Ordinamento Cronologico
        image_data.sort(key=lambda x: x[1])

        # 3. Calcolo Padding Numerico
        # Se abbiamo 1000 foto, servono 4 cifre (0001-1000).
        # log10(1000) = 3, quindi floor(3) + 1 = 4.
        padding = len(str(total_files))

        # 4. Copia e Rinominazione
        for i, (src_path, _) in enumerate(image_data, start=1):
            ext = os.path.splitext(src_path)[1].lower()
            # Esempio: timelapse_0001.jpg
            new_filename = f"{prefix}_{i:0{padding}d}{ext}"
            dst_path = os.path.join(output_dir, new_filename)

            # Copia sicura mantenendo i metadati
            shutil.copy2(src_path, dst_path)

            if i % 10 == 0 or i == total_files:
                progress_callback(i, total_files, f"Copia in corso: {i}/{total_files}")
