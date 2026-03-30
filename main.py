import os
import threading
import io
import tkinter
from datetime import datetime
from PIL import Image, ImageTk
import customtkinter as ctk
from tkinter import filedialog, messagebox
from logic import TimelapseLogic, WatermarkLogic

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class TimelapseFilterFrame(ctk.CTkFrame):
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
        self.page_size = 150
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

        self.scroll_frame = ctk.CTkScrollableFrame(
            right_panel, label_text="Anteprime Filtrate (Limite 150)"
        )
        self.scroll_frame.pack(pady=10, padx=10, fill="both", expand=True)
        # Configurazione colonne griglia (impostate a 4)
        for i in range(4):
            self.scroll_frame.grid_columnconfigure(i, weight=1)

        # Pagination Controls
        self.page_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        self.page_frame.pack(pady=5, fill="x")
        
        self.btn_prev = ctk.CTkButton(self.page_frame, text="< Indietro", width=100, command=self.prev_page, state="disabled")
        self.btn_prev.pack(side="left", padx=20)
        
        self.lbl_page = ctk.CTkLabel(self.page_frame, text="Pagina 1 di 1", font=ctk.CTkFont(weight="bold"))
        self.lbl_page.pack(side="left", expand=True)
        
        self.btn_next = ctk.CTkButton(self.page_frame, text="Avanti >", width=100, command=self.next_page, state="disabled")
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
            self.logic = TimelapseLogic(path)
            threading.Thread(target=self._scan_thread, daemon=True).start()

    def select_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_dir = path
            self.lbl_dest.configure(text=path)

    def _scan_thread(self):
        def update_ui(curr, total):
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

                    # Usa le dimensioni reali dell'immagine (già ridimensionata a target_h=300)
                    w_disp, h_disp = pil_img.size
                    ctk_img = ctk.CTkImage(
                        light_image=pil_img, dark_image=pil_img, size=(w_disp, h_disp)
                    )

                    self.thumbnails_labels.append(ctk_img)

                    # Layout: Griglia a 4 colonne
                    lbl = ctk.CTkLabel(
                        self.scroll_frame,
                        image=ctk_img,
                        text=f"{name[:20]}\n{dt.strftime('%d/%m/%Y %H:%M')}",
                        compound="top",  # Testo sotto l'immagine
                        font=ctk.CTkFont(size=11),
                        padx=5,
                        pady=5,
                    )
                    lbl.grid(row=i // 4, column=i % 4, padx=10, pady=10, sticky="nsew")

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
            self.after(0, lambda: self.progress_bar.set(curr / total))
            self.after(
                0, lambda: self.progress_label.configure(text=f"Copia: {curr}/{total}")
            )

        filenames = [x[0] for x in self.filtered_images]
        self.logic.copy_files(filenames, self.dest_dir, update_ui)
        self.after(0, lambda: messagebox.showinfo("Fine", "Copia completata"))
        self.after(0, lambda: self.btn_copy.configure(state="normal"))


class WatermarkFrame(ctk.CTkFrame):
    """Tab 2: Nuova logica Watermark."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.logic = WatermarkLogic()
        self.input_dir = ""
        self.output_dir = ""
        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Watermark Foto (EXIF Data)",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=20)

        self.btn_in = ctk.CTkButton(
            self, text="Seleziona Cartella Input", command=self.select_input
        )
        self.btn_in.pack(pady=10)
        self.lbl_in = ctk.CTkLabel(self, text="Non selezionata")
        self.lbl_in.pack()

        self.btn_out = ctk.CTkButton(
            self, text="Seleziona Cartella Output", command=self.select_output
        )
        self.btn_out.pack(pady=10)
        self.lbl_out = ctk.CTkLabel(self, text="Non selezionata")
        self.lbl_out.pack()

        self.status_label = ctk.CTkLabel(self, text="Pronto", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=(30, 5))

        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)

        self.btn_start = ctk.CTkButton(
            self,
            text="AVVIA WATERMARK",
            height=50,
            command=self.start_processing,
            fg_color="blue",
        )
        self.btn_start.pack(pady=30)

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

    def start_processing(self):
        if not self.input_dir or not self.output_dir:
            messagebox.showwarning("Mancano Dati", "Seleziona entrambe le cartelle.")
            return

        self.btn_start.configure(state="disabled")
        # Avvio in thread separato per non bloccare la UI
        threading.Thread(target=self._work_thread, daemon=True).start()

    def _work_thread(self):
        def update_progress(curr, total, msg):
            # Aggiornamento thread-safe della UI
            self.after(0, lambda: self.progress_bar.set(curr / total))
            self.after(
                0, lambda: self.status_label.configure(text=f"{msg} ({curr}/{total})")
            )

        self.logic.process_directory(self.input_dir, self.output_dir, update_progress)

        self.after(
            0,
            lambda: messagebox.showinfo(
                "Completato", "Tutte le foto sono state processate!"
            ),
        )
        self.after(0, lambda: self.btn_start.configure(state="normal"))


class TimelapseApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TimelapsePrep Multi-Tool")
        self.geometry("1100x750")

        # Widget Tabview Principale
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(padx=20, pady=20, fill="both", expand=True)

        self.tab_view.add("Timelapse Filter")
        self.tab_view.add("Watermark Foto")

        # Inserimento dei frame nelle Tab
        self.filter_frame = TimelapseFilterFrame(self.tab_view.tab("Timelapse Filter"))
        self.filter_frame.pack(fill="both", expand=True)

        self.watermark_frame = WatermarkFrame(self.tab_view.tab("Watermark Foto"))
        self.watermark_frame.pack(fill="both", expand=True)


if __name__ == "__main__":
    app = TimelapseApp()
    app.mainloop()
