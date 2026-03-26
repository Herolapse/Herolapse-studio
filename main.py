import os
import threading
from datetime import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox
from logic import TimelapseLogic

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TimelapseApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TimelapsePrep - Expert Photo Selector")
        self.geometry("1000x700")

        self.logic = None
        self.filtered_images = []
        self.source_dir = ""
        self.dest_dir = ""

        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # --- COLONNA SINISTRA (CONTROLLI) ---
        self.left_panel = ctk.CTkFrame(self, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(self.left_panel, text="Configurazione", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)

        # Selezione Cartelle
        self.btn_source = ctk.CTkButton(self.left_panel, text="Seleziona Sorgente", command=self.select_source)
        self.btn_source.pack(pady=5, fill="x", padx=10)
        self.lbl_source = ctk.CTkLabel(self.left_panel, text="Nessuna cartella", wraplength=250, font=ctk.CTkFont(size=10))
        self.lbl_source.pack(pady=2)

        self.btn_dest = ctk.CTkButton(self.left_panel, text="Seleziona Destinazione", command=self.select_dest)
        self.btn_dest.pack(pady=5, fill="x", padx=10)
        self.lbl_dest = ctk.CTkLabel(self.left_panel, text="Nessuna cartella", wraplength=250, font=ctk.CTkFont(size=10))
        self.lbl_dest.pack(pady=2)

        # Filtri Date
        ctk.CTkLabel(self.left_panel, text="Filtri Date (YYYY-MM-DD)", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 0))
        self.entry_start_date = ctk.CTkEntry(self.left_panel, placeholder_text="Inizio (es: 2024-01-01)")
        self.entry_start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entry_start_date.pack(pady=2, fill="x", padx=10)
        self.entry_end_date = ctk.CTkEntry(self.left_panel, placeholder_text="Fine (es: 2024-12-31)")
        self.entry_end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entry_end_date.pack(pady=2, fill="x", padx=10)

        # Filtri Orari
        ctk.CTkLabel(self.left_panel, text="Filtri Orari (HH:MM)", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 0))
        self.entry_start_time = ctk.CTkEntry(self.left_panel, placeholder_text="08:00")
        self.entry_start_time.insert(0, "08:00")
        self.entry_start_time.pack(pady=2, fill="x", padx=10)
        self.entry_end_time = ctk.CTkEntry(self.left_panel, placeholder_text="18:00")
        self.entry_end_time.insert(0, "18:00")
        self.entry_end_time.pack(pady=2, fill="x", padx=10)

        # Checkbox Giorni
        ctk.CTkLabel(self.left_panel, text="Giorni della Settimana", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 0))
        self.days_vars = []
        days_names = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
        days_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        days_frame.pack(pady=5)
        for i, day in enumerate(days_names):
            var = ctk.IntVar(value=1 if i < 5 else 0) # Preimposta Lun-Ven
            cb = ctk.CTkCheckBox(days_frame, text=day, variable=var, width=50)
            cb.grid(row=i//3, column=i%3, padx=2, pady=2)
            self.days_vars.append(var)

        # Progress Bar e Status
        self.progress_label = ctk.CTkLabel(self.left_panel, text="Pronto")
        self.progress_label.pack(pady=(20, 0))
        self.progress_bar = ctk.CTkProgressBar(self.left_panel)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10, fill="x", padx=10)

        # --- COLONNA DESTRA (RISULTATI) ---
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.log_textbox = ctk.CTkTextbox(self.right_panel)
        self.log_textbox.pack(pady=10, padx=10, fill="both", expand=True)

        self.lbl_count = ctk.CTkLabel(self.right_panel, text="Foto filtrate: 0 / 0 totali", font=ctk.CTkFont(size=14))
        self.lbl_count.pack(pady=5)

        self.btn_apply = ctk.CTkButton(self.right_panel, text="1. Filtra Risultati", command=self.apply_filters, fg_color="green", hover_color="#006400")
        self.btn_apply.pack(pady=5, fill="x", padx=20)

        self.btn_copy = ctk.CTkButton(self.right_panel, text="2. COPIA FOTO FILTRATE", command=self.start_copy, state="disabled", height=50, font=ctk.CTkFont(size=16, weight="bold"))
        self.btn_copy.pack(pady=10, fill="x", padx=20)

    # --- AZIONI ---

    def select_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_dir = path
            self.lbl_source.configure(text=path)
            self.logic = TimelapseLogic(path)
            self.log_message(f"Cartella sorgente impostata. Avvio scansione cache...")
            threading.Thread(target=self._scan_thread, daemon=True).start()

    def select_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_dir = path
            self.lbl_dest.configure(text=path)

    def _scan_thread(self):
        def update_progress(curr, total):
            self.after(0, lambda: self.progress_bar.set(curr / total))
            self.after(0, lambda: self.progress_label.configure(text=f"Scansione: {curr}/{total}"))

        total = self.logic.scan_directory(update_progress)
        self.after(0, lambda: self.log_message(f"Scansione completata. {total} immagini in cache."))
        self.after(0, lambda: self.lbl_count.configure(text=f"Foto filtrate: 0 / {total} totali"))

    def apply_filters(self):
        if not self.logic:
            messagebox.showwarning("Attenzione", "Seleziona prima una cartella sorgente.")
            return

        try:
            start_date = datetime.strptime(self.entry_start_date.get(), "%Y-%m-%d")
            end_date = datetime.strptime(self.entry_end_date.get(), "%Y-%m-%d")
            start_time = self.entry_start_time.get()
            end_time = self.entry_end_time.get()
            allowed_days = [i for i, v in enumerate(self.days_vars) if v.get() == 1]

            self.filtered_images = self.logic.filter_images(start_date, end_date, start_time, end_time, allowed_days)
            
            self.log_textbox.delete("1.0", "end")
            for name, dt in self.filtered_images:
                self.log_textbox.insert("end", f"[{dt}] {name}\n")
            
            self.lbl_count.configure(text=f"Foto filtrate: {len(self.filtered_images)} / {len(self.logic.cache)} totali")
            
            if self.filtered_images:
                self.btn_copy.configure(state="normal")
            else:
                self.btn_copy.configure(state="disabled")

        except ValueError as e:
            messagebox.showerror("Errore Formato", f"Verifica il formato di date e ore.\n{e}")

    def start_copy(self):
        if not self.dest_dir:
            messagebox.showwarning("Attenzione", "Seleziona una cartella di destinazione.")
            return
        
        if not self.filtered_images:
            return

        self.btn_copy.configure(state="disabled")
        threading.Thread(target=self._copy_thread, daemon=True).start()

    def _copy_thread(self):
        def update_progress(curr, total):
            self.after(0, lambda: self.progress_bar.set(curr / total))
            self.after(0, lambda: self.progress_label.configure(text=f"Copia in corso: {curr}/{total}"))

        filenames = [x[0] for x in self.filtered_images]
        self.logic.copy_files(filenames, self.dest_dir, update_progress)
        
        self.after(0, lambda: self.log_message(f"Copia completata con successo in {self.dest_dir}"))
        self.after(0, lambda: messagebox.showinfo("Fatto", "Copia completata!"))
        self.after(0, lambda: self.btn_copy.configure(state="normal"))

    def log_message(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_textbox.insert("end", f"[{timestamp}] SYSTEM: {msg}\n")
        self.log_textbox.see("end")

if __name__ == "__main__":
    app = TimelapseApp()
    app.mainloop()
