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
        self.is_cancelled = False
        self._setup_ui()

    def cancel_operation(self):
        self.is_cancelled = True
        self.status_label.configure(text="Annullamento in corso...")

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
        self.folder_frame_out = folder_frame_out

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

        # Operazione in loco
        self.in_place_var = ctk.BooleanVar(value=False)
        self.check_in_place = ctk.CTkCheckBox(
            self, 
            text="Operazione in loco (Rinomina file originali)", 
            variable=self.in_place_var,
            command=self._toggle_in_place,
            font=ctk.CTkFont(weight="bold")
        )
        self.check_in_place.pack(pady=10)

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
        self.status_label.pack(pady=(20, 5))

        self.progress_bar = ctk.CTkProgressBar(self, width=500)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)

        # Pulsanti Controllo
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)

        self.btn_start = ctk.CTkButton(
            btn_frame,
            text="AVVIA ESPORTAZIONE PREMIERE",
            height=60,
            command=self.start_export,
            fg_color="green",
            hover_color="darkgreen",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.btn_start.pack()

        self.btn_cancel = ctk.CTkButton(
            btn_frame,
            text="ANNULLA",
            height=60,
            command=self.cancel_operation,
            fg_color="red",
            state="normal",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        # Hidden initially

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

    def _toggle_in_place(self):
        if self.in_place_var.get():
            self.folder_frame_out.pack_forget()
        else:
            # Ripristina la posizione originale rimpaccandolo prima del prefisso
            # Ma pack non ha "before", quindi usiamo un approccio semplice rimpaccando tutto
            # O meglio, pack_forget e pack in ordine.
            self.folder_frame_out.pack(pady=10, fill="x", padx=40, after=self.lbl_in.master) 
            # In CustomTkinter pack order matters. Let's just re-pack in order if needed
            # For simplicity, I'll just keep it packed and use pack_forget/pack.
            pass
        self._refresh_layout()

    def _refresh_layout(self):
        # Per mantenere l'ordine corretto rimpacchiamo gli elementi
        for widget in self.winfo_children():
            widget.pack_forget()
        
        # Redraw in order (Recupero l'ordine logico)
        # 1. Label Titolo
        for widget in self.winfo_children():
            if isinstance(widget, ctk.CTkLabel) and "Rinomina" in widget.cget("text"):
                widget.pack(pady=20)
                break
        
        # 2. Folder Input
        for widget in self.winfo_children():
            if hasattr(widget, "winfo_children") and any(isinstance(c, ctk.CTkButton) and "Sorgente" not in c.cget("text") and "Input" in c.cget("text") for c in widget.winfo_children()):
                widget.pack(pady=10, fill="x", padx=40)
                break
        
        # 3. Folder Output (solo se non in loco)
        if not self.in_place_var.get():
            self.folder_frame_out.pack(pady=10, fill="x", padx=40)
        
        # 4. Checkbox In Place
        self.check_in_place.pack(pady=10)
        
        # 5. Prefix Frame
        for widget in self.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and widget != self.folder_frame_out and not hasattr(widget, "btn_in") and any(isinstance(c, ctk.CTkEntry) for c in widget.winfo_children()):
                widget.pack(pady=20)
                break

        # 6. Status e Progress
        self.status_label.pack(pady=(20, 5))
        self.progress_bar.pack(pady=10)
        
        # 7. Action Frame
        for widget in self.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and any(isinstance(c, ctk.CTkButton) and "ESPORTAZIONE" in c.cget("text") for c in widget.winfo_children()):
                widget.pack(pady=20)
                break

    def start_export(self):
        if not self.input_dir:
            messagebox.showwarning("Dati mancanti", "Seleziona la cartella di input.")
            return
            
        if not self.in_place_var.get() and not self.output_dir:
            messagebox.showwarning(
                "Dati mancanti",
                "Seleziona la cartella di output.",
            )
            return

        prefix = self.entry_prefix.get().strip()
        if not prefix:
            messagebox.showwarning(
                "Prefisso mancante", "Inserisci un prefisso per i file."
            )
            return

        self.is_cancelled = False
        self.btn_start.pack_forget()
        self.btn_cancel.pack()
        threading.Thread(
            target=self._export_thread, args=(prefix,), daemon=True
        ).start()

    def _export_thread(self, prefix):
        def update_ui(curr, total, msg):
            # Aggiornamento thread-safe via after()
            self.after(0, lambda: self.progress_bar.set(curr / total))
            self.after(0, lambda: self.status_label.configure(text=f"{msg}"))

        try:
            in_place = self.in_place_var.get()
            dest = self.input_dir if in_place else self.output_dir
            
            self.logic.process_renaming(
                self.input_dir, dest, prefix, update_ui, 
                stop_check=lambda: self.is_cancelled,
                in_place=in_place
            )
            if self.is_cancelled:
                self.after(0, lambda: messagebox.showwarning("Annullato", "Operazione annullata."))
                self.after(0, lambda: self.status_label.configure(text="Annullato"))
            else:
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Esportazione Completata",
                        "Le immagini sono state ordinate e rinominate con successo!",
                    ),
                )
                self.after(0, lambda: self.status_label.configure(text="Completato"))
        except Exception as e:
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Errore", f"Si è verificato un errore: {str(e)}"
                ),
            )
        finally:
            self.after(0, lambda: self.btn_cancel.pack_forget())
            self.after(0, lambda: self.btn_start.pack())
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
        stop_check: Callable[[], bool] = lambda: False,
        in_place: bool = False,
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
            if stop_check():
                return
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
        padding = len(str(total_files))

        # 4. Copia o Rinominazione
        for i, (src_path, _) in enumerate(image_data, start=1):
            if stop_check():
                return
            ext = os.path.splitext(src_path)[1].lower()
            
            if in_place:
                # Per evitare collisioni (es: rinominare file_1 in file_2 quando file_2 esiste ancora)
                # usiamo un prefisso temporaneo univoco.
                temp_filename = f"TMP_RENAME_{i:0{padding}d}_{os.path.basename(src_path)}"
                temp_path = os.path.join(output_dir, temp_filename)
                os.rename(src_path, temp_path)
                image_data[i-1] = (temp_path, None) # Aggiorniamo il path per il secondo step
            else:
                new_filename = f"{prefix}_{i:0{padding}d}{ext}"
                dst_path = os.path.join(output_dir, new_filename)
                shutil.copy2(src_path, dst_path)

            if i % 10 == 0 or i == total_files:
                msg = "Rinominazione temporanea..." if in_place else "Copia in corso..."
                progress_callback(i, total_files, f"{msg}: {i}/{total_files}")

        if in_place:
            # Secondo passaggio per rimuovere il prefisso temporaneo
            for i, (tmp_path, _) in enumerate(image_data, start=1):
                if stop_check(): return
                ext = os.path.splitext(tmp_path)[1].lower()
                final_filename = f"{prefix}_{i:0{padding}d}{ext}"
                final_path = os.path.join(output_dir, final_filename)
                os.rename(tmp_path, final_path)
                
                if i % 10 == 0 or i == total_files:
                    progress_callback(i, total_files, f"Finalizzazione: {i}/{total_files}")
