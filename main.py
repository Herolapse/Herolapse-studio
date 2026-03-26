import os
import threading
from datetime import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox
from logic import TimelapseLogic, WatermarkLogic

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TimelapseFilterFrame(ctk.CTkFrame):
    """Tab 1: Logica originale di filtraggio e copia."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.logic = None
        self.filtered_images = []
        self.source_dir = ""
        self.dest_dir = ""
        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # Colonna Sinistra
        left_panel = ctk.CTkFrame(self, corner_radius=0)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(left_panel, text="Configurazione Filtri", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        self.btn_source = ctk.CTkButton(left_panel, text="Sorgente", command=self.select_source)
        self.btn_source.pack(pady=5, fill="x", padx=10)
        self.lbl_source = ctk.CTkLabel(left_panel, text="Nessuna cartella", font=ctk.CTkFont(size=10), wraplength=200)
        self.lbl_source.pack(pady=2)

        self.btn_dest = ctk.CTkButton(left_panel, text="Destinazione", command=self.select_dest)
        self.btn_dest.pack(pady=5, fill="x", padx=10)
        self.lbl_dest = ctk.CTkLabel(left_panel, text="Nessuna cartella", font=ctk.CTkFont(size=10), wraplength=200)
        self.lbl_dest.pack(pady=2)

        ctk.CTkLabel(left_panel, text="Date (YYYY-MM-DD)", font=ctk.CTkFont(weight="bold")).pack(pady=(10,0))
        self.entry_start_date = ctk.CTkEntry(left_panel)
        self.entry_start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entry_start_date.pack(pady=2, fill="x", padx=10)
        self.entry_end_date = ctk.CTkEntry(left_panel)
        self.entry_end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entry_end_date.pack(pady=2, fill="x", padx=10)

        ctk.CTkLabel(left_panel, text="Orari (HH:MM)", font=ctk.CTkFont(weight="bold")).pack(pady=(10,0))
        self.entry_start_time = ctk.CTkEntry(left_panel)
        self.entry_start_time.insert(0, "08:00")
        self.entry_start_time.pack(pady=2, fill="x", padx=10)
        self.entry_end_time = ctk.CTkEntry(left_panel)
        self.entry_end_time.insert(0, "18:00")
        self.entry_end_time.pack(pady=2, fill="x", padx=10)

        # Ripristino Checkbox Giorni
        ctk.CTkLabel(left_panel, text="Giorni della Settimana", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 0))
        self.days_vars = []
        days_names = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
        days_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        days_frame.pack(pady=5)
        for i, day in enumerate(days_names):
            var = ctk.IntVar(value=1 if i < 5 else 0) # Preimposta Lun-Ven
            cb = ctk.CTkCheckBox(days_frame, text=day, variable=var, width=50, font=ctk.CTkFont(size=10))
            cb.grid(row=i//3, column=i%3, padx=2, pady=2)
            self.days_vars.append(var)

        self.progress_label = ctk.CTkLabel(left_panel, text="Pronto")
        self.progress_label.pack(pady=(10,0))
        self.progress_bar = ctk.CTkProgressBar(left_panel)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10, fill="x", padx=10)

        # --- SEZIONE EV100 ---
        ctk.CTkLabel(left_panel, text="Filtro Esposizione (EV100)", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 0))
        self.lbl_ev_detected = ctk.CTkLabel(left_panel, text="Range rilevato: --", font=ctk.CTkFont(size=11, slant="italic"))
        self.lbl_ev_detected.pack()

        ev_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        ev_frame.pack(pady=5, fill="x", padx=10)
        
        self.entry_min_ev = ctk.CTkEntry(ev_frame, placeholder_text="Min EV", width=70)
        self.entry_min_ev.insert(0, "-20.0")
        self.entry_min_ev.grid(row=0, column=0, padx=5)
        
        ctk.CTkLabel(ev_frame, text="to").grid(row=0, column=1)
        
        self.entry_max_ev = ctk.CTkEntry(ev_frame, placeholder_text="Max EV", width=70)
        self.entry_max_ev.insert(0, "20.0")
        self.entry_max_ev.grid(row=0, column=2, padx=5)

        # Colonna Destra
        right_panel = ctk.CTkFrame(self)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.log_textbox = ctk.CTkTextbox(right_panel)
        self.log_textbox.pack(pady=10, padx=10, fill="both", expand=True)

        self.lbl_count = ctk.CTkLabel(right_panel, text="Foto filtrate: 0 / 0")
        self.lbl_count.pack(pady=5)

        self.btn_apply = ctk.CTkButton(right_panel, text="Applica Filtri", command=self.apply_filters, fg_color="green")
        self.btn_apply.pack(pady=5, fill="x", padx=20)

        self.btn_copy = ctk.CTkButton(right_panel, text="Copia Foto Filtrate", command=self.start_copy, state="disabled")
        self.btn_copy.pack(pady=10, fill="x", padx=20)

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
            self.after(0, lambda: self.progress_bar.set(curr/total))
            self.after(0, lambda: self.progress_label.configure(text=f"Scansione: {curr}/{total}"))
        
        total = self.logic.scan_directory(update_ui)
        
        # Dopo la scansione, recuperiamo il range EV per aiutare l'utente
        min_ev, max_ev = self.logic.get_ev_range()
        
        def finalize_ui():
            self.lbl_count.configure(text=f"Foto filtrate: 0 / {total}")
            if min_ev is not None:
                self.lbl_ev_detected.configure(text=f"Range rilevato: {min_ev} - {max_ev}")
                # Opzionale: pre-compila con i valori rilevati per comodità
                self.entry_min_ev.delete(0, "end")
                self.entry_min_ev.insert(0, str(min_ev))
                self.entry_max_ev.delete(0, "end")
                self.entry_max_ev.insert(0, str(max_ev))
            else:
                self.lbl_ev_detected.configure(text="Nessun dato EV trovato")

        self.after(0, finalize_ui)

    def apply_filters(self):
        if not self.logic: return
        try:
            start_date = datetime.strptime(self.entry_start_date.get(), "%Y-%m-%d")
            end_date = datetime.strptime(self.entry_end_date.get(), "%Y-%m-%d")
            
            # Legge i giorni selezionati (0=Lun, 6=Dom)
            allowed_days = [i for i, v in enumerate(self.days_vars) if v.get() == 1]
            
            # Legge i valori EV
            try:
                min_ev = float(self.entry_min_ev.get())
                max_ev = float(self.entry_max_ev.get())
            except ValueError:
                min_ev, max_ev = -100.0, 100.0 # Fallback se vuoto o non valido

            self.filtered_images = self.logic.filter_images(
                start_date, 
                end_date, 
                self.entry_start_time.get(), 
                self.entry_end_time.get(), 
                allowed_days,
                min_ev,
                max_ev
            )
            self.log_textbox.delete("1.0", "end")
            for name, dt in self.filtered_images:
                self.log_textbox.insert("end", f"[{dt}] {name}\n")
            self.lbl_count.configure(text=f"Filtrate: {len(self.filtered_images)} / {len(self.logic.cache)}")
            self.btn_copy.configure(state="normal" if self.filtered_images else "disabled")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def start_copy(self):
        if not self.dest_dir: return
        self.btn_copy.configure(state="disabled")
        threading.Thread(target=self._copy_thread, daemon=True).start()

    def _copy_thread(self):
        def update_ui(curr, total):
            self.after(0, lambda: self.progress_bar.set(curr/total))
            self.after(0, lambda: self.progress_label.configure(text=f"Copia: {curr}/{total}"))
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
        
        ctk.CTkLabel(self, text="Watermark Foto (EXIF Data)", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)

        self.btn_in = ctk.CTkButton(self, text="Seleziona Cartella Input", command=self.select_input)
        self.btn_in.pack(pady=10)
        self.lbl_in = ctk.CTkLabel(self, text="Non selezionata")
        self.lbl_in.pack()

        self.btn_out = ctk.CTkButton(self, text="Seleziona Cartella Output", command=self.select_output)
        self.btn_out.pack(pady=10)
        self.lbl_out = ctk.CTkLabel(self, text="Non selezionata")
        self.lbl_out.pack()

        self.status_label = ctk.CTkLabel(self, text="Pronto", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=(30, 5))

        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)

        self.btn_start = ctk.CTkButton(self, text="AVVIA WATERMARK", height=50, command=self.start_processing, fg_color="blue")
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
            self.after(0, lambda: self.status_label.configure(text=f"{msg} ({curr}/{total})"))

        self.logic.process_directory(self.input_dir, self.output_dir, update_progress)
        
        self.after(0, lambda: messagebox.showinfo("Completato", "Tutte le foto sono state processate!"))
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
