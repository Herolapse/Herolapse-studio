import threading
import io
import os
from datetime import datetime
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox
import sqlite3
import shutil
import math
import cv2
import numpy as np
from typing import List, Tuple, Callable, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from PIL.ExifTags import TAGS


class HeroSelect(ctk.CTkFrame):
    """Tab 1: Logica di filtraggio con anteprime visive."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.logic = None
        self.filtered_images = []
        self.source_dir = ""
        self.dest_dir = ""
        self.thumbnails_labels = []  # Per gestire il cleanup della memoria

        # Stato Paginazione
        self.current_page = 0
        self.page_size = 50
        self.total_filtered = 0

        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        # Colonna Sinistra: Filtri
        left_panel = ctk.CTkFrame(self, corner_radius=0)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(
            left_panel,
            text="Configurazione Filtri",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=10)

        self.btn_source = ctk.CTkButton(
            left_panel, text="Sorgente", command=self.select_source
        )
        self.btn_source.pack(pady=5, fill="x", padx=10)
        self.lbl_source = ctk.CTkLabel(
            left_panel,
            text="Nessuna cartella",
            font=ctk.CTkFont(size=10),
            wraplength=200,
        )
        self.lbl_source.pack(pady=2)

        self.btn_dest = ctk.CTkButton(
            left_panel, text="Destinazione", command=self.select_dest
        )
        self.btn_dest.pack(pady=5, fill="x", padx=10)
        self.lbl_dest = ctk.CTkLabel(
            left_panel,
            text="Nessuna cartella",
            font=ctk.CTkFont(size=10),
            wraplength=200,
        )
        self.lbl_dest.pack(pady=2)

        ctk.CTkLabel(
            left_panel, text="Date (YYYY-MM-DD)", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(10, 0))
        self.entry_start_date = ctk.CTkEntry(left_panel)
        self.entry_start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entry_start_date.pack(pady=2, fill="x", padx=10)
        self.entry_end_date = ctk.CTkEntry(left_panel)
        self.entry_end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entry_end_date.pack(pady=2, fill="x", padx=10)

        ctk.CTkLabel(
            left_panel, text="Orari (HH:MM)", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(10, 0))
        self.entry_start_time = ctk.CTkEntry(left_panel)
        self.entry_start_time.insert(0, "08:00")
        self.entry_start_time.pack(pady=2, fill="x", padx=10)
        self.entry_end_time = ctk.CTkEntry(left_panel)
        self.entry_end_time.insert(0, "18:00")
        self.entry_end_time.pack(pady=2, fill="x", padx=10)

        # Giorni della Settimana
        ctk.CTkLabel(
            left_panel, text="Giorni della Settimana", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(10, 0))
        self.days_vars = []
        days_names = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
        days_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        days_frame.pack(pady=5, fill="x")
        for i in range(len(days_names)):
            days_frame.grid_columnconfigure(i, weight=1)
        for i, day in enumerate(days_names):
            var = ctk.IntVar(value=1 if i < 5 else 0)
            cb = ctk.CTkCheckBox(
                days_frame,
                text=day,
                variable=var,
                width=40,
                font=ctk.CTkFont(size=9),
                checkbox_width=18,
                checkbox_height=18,
            )
            cb.grid(row=0, column=i, padx=1, pady=2)
            self.days_vars.append(var)

        # --- SEZIONE EV100 ---
        ctk.CTkLabel(
            left_panel,
            text="Filtro Esposizione (EV100)",
            font=ctk.CTkFont(weight="bold"),
        ).pack(pady=(15, 0))
        self.lbl_ev_detected = ctk.CTkLabel(
            left_panel,
            text="Range rilevato: --",
            font=ctk.CTkFont(size=11, slant="italic"),
        )
        self.lbl_ev_detected.pack()
        ev_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        ev_frame.pack(pady=5)
        self.entry_min_ev = ctk.CTkEntry(ev_frame, placeholder_text="Min", width=60)
        self.entry_min_ev.insert(0, "-20.0")
        self.entry_min_ev.pack(side="left", padx=5)
        ctk.CTkLabel(ev_frame, text="to").pack(side="left", padx=2)
        self.entry_max_ev = ctk.CTkEntry(ev_frame, placeholder_text="Max", width=60)
        self.entry_max_ev.insert(0, "20.0")
        self.entry_max_ev.pack(side="left", padx=5)

        # --- SEZIONE CONTROLLO QUALITÀ ---
        ctk.CTkLabel(
            left_panel, text="Controllo Qualità", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(15, 0))
        self.check_blur = ctk.CTkCheckBox(
            left_panel, text="Escludi foto sfocate/nebbia"
        )
        self.check_blur.select()
        self.check_blur.pack(pady=5, padx=10, anchor="w")
        blur_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        blur_frame.pack(pady=2, fill="x", padx=10)
        ctk.CTkLabel(
            blur_frame, text="Soglia Nitidezza:", font=ctk.CTkFont(size=11)
        ).pack(side="left")
        self.entry_sharpness = ctk.CTkEntry(blur_frame, width=70)
        self.entry_sharpness.pack(side="right")
        self.lbl_sharpness_info = ctk.CTkLabel(
            left_panel,
            text="Media dataset: -- | Consigliata: --",
            font=ctk.CTkFont(size=10, slant="italic"),
        )
        self.lbl_sharpness_info.pack(pady=2)

        # Progress Section
        self.progress_label = ctk.CTkLabel(left_panel, text="Pronto")
        self.progress_label.pack(side="bottom", pady=(5, 0))
        self.progress_bar = ctk.CTkProgressBar(left_panel)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="bottom", pady=10, fill="x", padx=10)

        # Colonna Destra: Griglia Anteprime
        right_panel = ctk.CTkFrame(self)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.scroll_frame = ctk.CTkScrollableFrame(right_panel)
        self.scroll_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Configurazione colonne griglia (impostate a 2 per gestire immagini larghe mantenendo l'aspect ratio)
        self.num_cols = 3
        for i in range(self.num_cols):
            self.scroll_frame.grid_columnconfigure(i, weight=1)

        # Pagination Controls
        self.page_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        self.page_frame.pack(pady=5, fill="x")

        self.btn_prev = ctk.CTkButton(
            self.page_frame,
            text="< Indietro",
            width=100,
            command=self.prev_page,
            state="disabled",
        )
        self.btn_prev.pack(side="left", padx=20)

        self.lbl_page = ctk.CTkLabel(
            self.page_frame, text="Pagina 1 di 1", font=ctk.CTkFont(weight="bold")
        )
        self.lbl_page.pack(side="left", expand=True)

        self.btn_next = ctk.CTkButton(
            self.page_frame,
            text="Avanti >",
            width=100,
            command=self.next_page,
            state="disabled",
        )
        self.btn_next.pack(side="right", padx=20)

        self.btn_copy = ctk.CTkButton(
            right_panel,
            text="Copia Foto Filtrate",
            command=self.start_copy,
            state="disabled",
            height=50,
        )
        self.btn_copy.pack(side="bottom", pady=10, fill="x", padx=20)

        self.btn_apply = ctk.CTkButton(
            right_panel,
            text="Applica Filtri",
            command=self.apply_filters,
            fg_color="green",
        )
        self.btn_apply.pack(side="bottom", pady=5, fill="x", padx=20)

        self.lbl_count = ctk.CTkLabel(
            right_panel,
            text="Foto filtrate: 0 / 0",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.lbl_count.pack(side="bottom", pady=5)

    def select_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_dir = path
            self.lbl_source.configure(text=path)
            self.logic = HeroSelectLogic(path)
            threading.Thread(target=self._scan_thread, daemon=True).start()

    def select_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_dir = path
            self.lbl_dest.configure(text=path)

    def _scan_thread(self):
        def update_ui(curr, total):
            if total > 0:
                self.after(0, lambda: self.progress_bar.set(curr / total))
            self.after(
                0,
                lambda: self.progress_label.configure(
                    text=f"Scansione: {curr}/{total}"
                ),
            )

        total = self.logic.scan_directory(update_ui)
        min_ev, max_ev = self.logic.get_ev_range()
        min_date, max_date = self.logic.get_date_range()
        avg_sharp, threshold_sharp = self.logic.get_sharpness_stats()

        def finalize_ui():
            self.lbl_count.configure(text=f"Foto filtrate: 0 / {total}")
            if min_ev is not None:
                self.lbl_ev_detected.configure(
                    text=f"Range rilevato: {min_ev} - {max_ev}"
                )
                self.entry_min_ev.delete(0, "end")
                self.entry_min_ev.insert(0, str(min_ev))
                self.entry_max_ev.delete(0, "end")
                self.entry_max_ev.insert(0, str(max_ev))
            if avg_sharp > 0:
                self.lbl_sharpness_info.configure(
                    text=f"Media dataset: {avg_sharp} | Consigliata: {threshold_sharp}"
                )
                self.entry_sharpness.delete(0, "end")
                self.entry_sharpness.insert(0, str(threshold_sharp))
            if min_date and max_date:
                self.entry_start_date.delete(0, "end")
                self.entry_start_date.insert(0, min_date)
                self.entry_end_date.delete(0, "end")
                self.entry_end_date.insert(0, max_date)

        self.after(0, finalize_ui)

    def apply_filters(self):
        if not self.logic:
            return
        self.current_page = 0  # Reset alla prima pagina
        self._load_current_page()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._load_current_page()

    def next_page(self):
        total_pages = (self.total_filtered + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._load_current_page()

    def _load_current_page(self):
        """Carica la pagina corrente basata sullo stato di paginazione."""
        try:
            start_date = datetime.strptime(self.entry_start_date.get(), "%Y-%m-%d")
            end_date = datetime.strptime(self.entry_end_date.get(), "%Y-%m-%d")
            allowed_days = [i for i, v in enumerate(self.days_vars) if v.get() == 1]
            try:
                min_ev = float(self.entry_min_ev.get())
                max_ev = float(self.entry_max_ev.get())
            except ValueError:
                min_ev, max_ev = -100.0, 100.0
            exclude_blur = self.check_blur.get() == 1
            try:
                sharp_thresh = float(self.entry_sharpness.get())
            except ValueError:
                sharp_thresh = 0.0

            # Conteggio totale reale via SQL
            self.total_filtered = self.logic.count_filtered_images(
                start_date,
                end_date,
                self.entry_start_time.get(),
                self.entry_end_time.get(),
                min_ev,
                max_ev,
                exclude_blur,
                sharp_thresh,
                allowed_days,
            )

            # Calcolo Offset
            offset = self.current_page * self.page_size

            # Caricamento immagini limitato alla pagina
            self.filtered_images = self.logic.filter_images(
                start_date,
                end_date,
                self.entry_start_time.get(),
                self.entry_end_time.get(),
                allowed_days,
                min_ev,
                max_ev,
                exclude_blur,
                sharp_thresh,
                limit=self.page_size,
                offset=offset,
            )

            self._render_grid(self.total_filtered)
            self._update_pagination_ui()

            self.btn_copy.configure(
                state="normal" if self.total_filtered > 0 else "disabled"
            )
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _update_pagination_ui(self):
        """Aggiorna lo stato dei bottoni e la label della pagina."""
        total_pages = max(
            1, (self.total_filtered + self.page_size - 1) // self.page_size
        )
        self.lbl_page.configure(text=f"Pagina {self.current_page + 1} di {total_pages}")

        self.btn_prev.configure(state="normal" if self.current_page > 0 else "disabled")
        self.btn_next.configure(
            state="normal" if self.current_page < total_pages - 1 else "disabled"
        )

    def _on_mouse_wheel(self, event):
        """Reindirizza lo scroll della rotella all'handler interno del frame scrollabile."""
        try:
            # Utilizziamo l'handler nativo di customtkinter che gestisce già le differenze tra OS
            self.scroll_frame._on_mousewheel(event)
        except Exception:
            pass  # Evitiamo crash se il metodo interno dovesse cambiare in futuro

    def _render_grid(self, total_count):
        """Pulisce e popola la griglia di anteprime con conversione RGB."""
        # Cleanup
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.thumbnails_labels = []  # Svuota i vecchi riferimenti

        # Rendering
        for i, (name, dt, thumb_blob) in enumerate(self.filtered_images):
            if thumb_blob and len(thumb_blob) > 0:
                try:
                    # Conversione BLOB -> PIL -> RGB -> CTkImage
                    img_data = io.BytesIO(thumb_blob)
                    pil_img = Image.open(img_data)

                    # Forza la conversione in RGB (essenziale se l'originale è grayscale)
                    if pil_img.mode != "RGB":
                        pil_img = pil_img.convert("RGB")

                    # Calcola le dimensioni per avere un'altezza fissa di 300px mantenendo l'aspect ratio
                    w_orig, h_orig = pil_img.size
                    target_h = 300
                    target_w = int(w_orig * (target_h / h_orig))

                    ctk_img = ctk.CTkImage(
                        light_image=pil_img,
                        dark_image=pil_img,
                        size=(target_w, target_h),
                    )

                    self.thumbnails_labels.append(ctk_img)

                    # Layout: Griglia configurata nel setup
                    lbl = ctk.CTkLabel(
                        self.scroll_frame,
                        image=ctk_img,
                        text=f"{name[:20]}\n{dt.strftime('%d/%m/%Y %H:%M')}",
                        compound="top",  # Testo sotto l'immagine
                        font=ctk.CTkFont(size=11),
                        padx=5,
                        pady=5,
                    )
                    lbl.grid(
                        row=i // self.num_cols,
                        column=i % self.num_cols,
                        padx=10,
                        pady=10,
                    )

                    # BINDING PER LO SCROLL (Linux + Windows/macOS)
                    lbl.bind("<Button-4>", self._on_mouse_wheel)
                    lbl.bind("<Button-5>", self._on_mouse_wheel)
                    lbl.bind("<MouseWheel>", self._on_mouse_wheel)

                except Exception as e:
                    print(f"Errore rendering {name}: {e}")
                    continue

        shown = len(self.filtered_images)
        self.lbl_count.configure(
            text=f"Mostrando {shown} di {total_count} foto filtrate"
        )
        self.update()  # Refresh totale della finestra UI

    def start_copy(self):
        if not self.dest_dir:
            return
        self.btn_copy.configure(state="disabled")
        threading.Thread(target=self._copy_thread, daemon=True).start()

    def _copy_thread(self):
        def update_ui(curr, total):
            if total > 0:
                self.after(0, lambda: self.progress_bar.set(curr / total))
            self.after(
                0, lambda: self.progress_label.configure(text=f"Copia: {curr}/{total}")
            )

        # Recupero parametri filtri
        try:
            start_date = datetime.strptime(self.entry_start_date.get(), "%Y-%m-%d")
            end_date = datetime.strptime(self.entry_end_date.get(), "%Y-%m-%d")
            allowed_days = [i for i, v in enumerate(self.days_vars) if v.get() == 1]
            try:
                min_ev = float(self.entry_min_ev.get())
                max_ev = float(self.entry_max_ev.get())
            except ValueError:
                min_ev, max_ev = -100.0, 100.0
            exclude_blur = self.check_blur.get() == 1
            try:
                sharp_thresh = float(self.entry_sharpness.get())
            except ValueError:
                sharp_thresh = 0.0

            # Otteniamo TUTTI i nomi file filtrati (senza limite di pagina)
            all_filtered = self.logic.filter_images(
                start_date,
                end_date,
                self.entry_start_time.get(),
                self.entry_end_time.get(),
                allowed_days,
                min_ev,
                max_ev,
                exclude_blur,
                sharp_thresh,
                limit=self.total_filtered,
                offset=0
            )
            
            filenames = [x[0] for x in all_filtered]
            self.logic.copy_files(filenames, self.dest_dir, update_ui)
            self.after(0, lambda: messagebox.showinfo("Fine", "Copia completata"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Errore", f"Errore durante la copia: {e}"))
        finally:
            self.after(0, lambda: self.btn_copy.configure(state="normal"))


class HeroSelectLogic:
    DB_NAME = "herolapse_studio_cache.db"
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}

    def __init__(self, source_dir: str):
        self.source_dir = source_dir
        self.db_path = os.path.join(source_dir, self.DB_NAME)
        self._init_db()

    def _init_db(self):
        """Inizializza il database SQLite e aggiunge colonne mancanti."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS photos (
                        filename TEXT PRIMARY KEY,
                        date_taken TEXT,
                        iso INTEGER,
                        aperture REAL,
                        shutter REAL,
                        ev100 REAL,
                        sharpness_score REAL,
                        thumbnail BLOB,
                        homography_matrix TEXT
                    )
                """)
                # Verifica se la colonna thumbnail e homography_matrix esistono (per migrazione DB esistenti)
                cursor.execute("PRAGMA table_info(photos)")
                columns = [column[1] for column in cursor.fetchall()]
                if "thumbnail" not in columns:
                    cursor.execute("ALTER TABLE photos ADD COLUMN thumbnail BLOB")
                if "homography_matrix" not in columns:
                    cursor.execute("ALTER TABLE photos ADD COLUMN homography_matrix TEXT")

                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_date ON photos(date_taken)"
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ev ON photos(ev100)")
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sharpness ON photos(sharpness_score)"
                )
                conn.commit()
        except sqlite3.Error as e:
            print(f"Errore inizializzazione DB: {e}")

    def _convert_to_float(self, ratio: Any) -> float:
        if isinstance(ratio, (tuple, list)) and len(ratio) == 2:
            return float(ratio[0]) / float(ratio[1]) if ratio[1] != 0 else 0.0
        try:
            return float(ratio)
        except (ValueError, TypeError):
            return 0.0

    def process_image_data(self, filepath: str) -> Tuple[float, bytes]:
        """Calcola sharpness (gray) e genera thumbnail a colori (300x300)."""
        try:
            # Caricamento a colori per la miniatura
            img_color = cv2.imread(filepath, cv2.IMREAD_COLOR)
            if img_color is None:
                return 0.0, b""

            # 1. Calcolo Sharpness (su versione grigia temporanea)
            img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
            h, w = img_gray.shape[:2]
            scale = min(500 / w, 500 / h)
            img_resized_gray = cv2.resize(
                img_gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
            )
            sharpness = cv2.Laplacian(img_resized_gray, cv2.CV_64F).var()

            # 2. Generazione Thumbnail con Aspect Ratio Originale
            # Altezza fissa a 300px, larghezza proporzionale
            img_rgb = cv2.cvtColor(img_color, cv2.COLOR_BGR2RGB)
            h_orig, w_orig = img_rgb.shape[:2]

            target_h = 300
            target_w = int(w_orig * (target_h / h_orig))
            thumb_size = (target_w, target_h)

            img_thumb = cv2.resize(img_rgb, thumb_size, interpolation=cv2.INTER_AREA)

            # Compressione JPEG in memoria
            is_success, buffer = cv2.imencode(
                ".jpg",
                cv2.cvtColor(img_thumb, cv2.COLOR_RGB2BGR),
                [cv2.IMWRITE_JPEG_QUALITY, 75],
            )
            return sharpness, buffer.tobytes()
        except Exception:
            return 0.0, b""

    def get_full_exif_data(
        self, filename: str
    ) -> Tuple[
        str,
        Optional[str],
        Optional[int],
        Optional[float],
        Optional[float],
        Optional[float],
        float,
        bytes,
        Optional[str],
    ]:
        """Estrae EXIF, Sharpness e Thumbnail per un file."""
        filepath = os.path.join(self.source_dir, filename)
        res = [filename, None, None, None, None, None, 0.0, b"", None]
        try:
            # Calcolo Sharpness e Thumbnail
            res[6], res[7] = self.process_image_data(filepath)

            with Image.open(filepath) as img:
                exif = img._getexif()
                if exif:
                    tags = {TAGS.get(tag, tag): value for tag, value in exif.items()}
                    dt_str = tags.get("DateTimeOriginal")
                    res[1] = (
                        datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S").strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if dt_str
                        else datetime.fromtimestamp(
                            os.path.getmtime(filepath)
                        ).strftime("%Y-%m-%d %H:%M:%S")
                    )
                    res[2] = tags.get("ISOSpeedRatings")
                    res[3] = self._convert_to_float(tags.get("FNumber"))
                    res[4] = self._convert_to_float(tags.get("ExposureTime"))
                    if res[3] and res[4] and res[2] and res[2] > 0:
                        ev = math.log2(res[3] ** 2 / res[4]) - math.log2(res[2] / 100.0)
                        res[5] = round(ev, 2)
        except Exception:
            pass
        return tuple(res)

    def scan_directory(self, progress_callback: Callable[[int, int], None]) -> int:
        all_files = [
            f
            for f in os.listdir(self.source_dir)
            if os.path.splitext(f)[1].lower() in self.IMAGE_EXTENSIONS
        ]

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Seleziona i file che hanno già una thumbnail valida (lunghezza > 0)
            cursor.execute(
                "SELECT filename FROM photos WHERE thumbnail IS NOT NULL AND length(thumbnail) > 0"
            )
            db_files = {row[0] for row in cursor.fetchall()}

        to_scan = [f for f in all_files if f not in db_files]
        total_files = len(all_files)
        total_to_scan = len(to_scan)

        if total_to_scan == 0:
            progress_callback(total_files, total_files)
            return total_files

        batch_data = []
        processed_count = 0

        with ThreadPoolExecutor(max_workers=max(1, os.cpu_count() - 1)) as executor:
            results = executor.map(self.get_full_exif_data, to_scan)
            for data in results:
                batch_data.append(data)
                processed_count += 1
                if (
                    len(batch_data) >= 200
                ):  # Batch più piccoli per gestire i BLOB in memoria
                    self._insert_batch(batch_data)
                    batch_data = []
                if processed_count % 10 == 0 or processed_count == total_to_scan:
                    progress_callback(
                        len(all_files) - total_to_scan + processed_count, total_files
                    )

        if batch_data:
            self._insert_batch(batch_data)
        return total_files

    def _insert_batch(self, data: List[tuple]):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    "INSERT OR REPLACE INTO photos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    data,
                )
                conn.commit()
        except sqlite3.Error as e:
            print(f"Errore inserimento batch: {e}")

    def get_total_count(self) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM photos")
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    def get_ev_range(self) -> Tuple[Optional[float], Optional[float]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MIN(ev100), MAX(ev100) FROM photos WHERE ev100 IS NOT NULL"
            )
            return cursor.fetchone()

    def get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MIN(date(date_taken)), MAX(date(date_taken)) FROM photos"
            )
            return cursor.fetchone()

    def get_sharpness_stats(self) -> Tuple[float, float]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT sharpness_score FROM photos WHERE sharpness_score > 0"
                )
                scores = [r[0] for r in cursor.fetchall()]
                if not scores:
                    return 0.0, 0.0
                return round(float(np.mean(scores)), 2), round(
                    float(np.percentile(scores, 15)), 2
                )
        except Exception:
            return 0.0, 0.0

    def count_filtered_images(
        self,
        start_date: datetime,
        end_date: datetime,
        start_time: str,
        end_time: str,
        min_ev: float,
        max_ev: float,
        exclude_blur: bool,
        sharpness_threshold: float,
        allowed_days: List[int],
    ) -> int:
        """Restituisce il conteggio totale delle foto che corrispondono ESATTAMENTE a tutti i filtri."""
        sql_days = [0 if d == 6 else d + 1 for d in allowed_days]
        days_placeholder = ",".join(map(str, sql_days))
        blur_filter = (
            f"AND sharpness_score > {sharpness_threshold}" if exclude_blur else ""
        )

        query = f"""
            SELECT COUNT(*) FROM photos 
            WHERE date(date_taken) BETWEEN ? AND ? 
            AND ev100 BETWEEN ? AND ? 
            AND time(date_taken) BETWEEN ? AND ?
            AND CAST(strftime('%w', date_taken) AS INTEGER) IN ({days_placeholder}) 
            {blur_filter}
        """
        params = (
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            min_ev,
            max_ev,
            f"{start_time}:00",
            f"{end_time}:59",
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    def filter_images(
        self,
        start_date: datetime,
        end_date: datetime,
        start_time: str,
        end_time: str,
        allowed_days: List[int],
        min_ev: float,
        max_ev: float,
        exclude_blur: bool = False,
        sharpness_threshold: float = 0.0,
        limit: int = 150,
        offset: int = 0,
    ) -> List[Tuple[str, datetime, bytes]]:
        """Filtraggio con paginazione SQL (LIMIT/OFFSET)."""
        sql_days = [0 if d == 6 else d + 1 for d in allowed_days]
        days_placeholder = ",".join(map(str, sql_days))
        blur_filter = (
            f"AND sharpness_score > {sharpness_threshold}" if exclude_blur else ""
        )

        query = f"""
            SELECT filename, date_taken, thumbnail FROM photos
            WHERE date(date_taken) BETWEEN ? AND ?
            AND ev100 BETWEEN ? AND ?
            AND time(date_taken) BETWEEN ? AND ?
            AND CAST(strftime('%w', date_taken) AS INTEGER) IN ({days_placeholder})
            {blur_filter}
            ORDER BY date_taken ASC
            LIMIT ? OFFSET ?
        """

        params = (
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            min_ev,
            max_ev,
            f"{start_time}:00",
            f"{end_time}:59",
            limit,
            offset,
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                return [
                    (r[0], datetime.strptime(r[1], "%Y-%m-%d %H:%M:%S"), r[2])
                    for r in results
                ]
        except sqlite3.Error as e:
            print(f"Errore query filtraggio: {e}")
            return []

    def copy_files(
        self,
        files_to_copy: List[str],
        dest_dir: str,
        progress_callback: Callable[[int, int], None],
    ):
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        total = len(files_to_copy)
        for i, filename in enumerate(files_to_copy):
            src = os.path.join(self.source_dir, filename)
            dst = os.path.join(dest_dir, filename)
            if not (
                os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst)
            ):
                shutil.copy2(src, dst)
            if i % 10 == 0 or i == total - 1:
                progress_callback(i + 1, total)
