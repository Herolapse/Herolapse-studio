import threading
import io
import os
from datetime import datetime
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox
import sqlite3
import cv2
import numpy as np
from typing import List, Tuple, Callable, Optional, Any
from .hero_select import HeroSelect, HeroSelectLogic


class QuickTimelapse(HeroSelect):
    """Tab 4: Generazione rapida di timelapse video dai dati filtrati."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.video_dest_path = ""

    def _setup_ui(self):
        # Chiamiamo il setup UI di base (quello di HeroSelect)
        super()._setup_ui()

        # Rimuoviamo il bottone "Copia Foto Filtrate" che non ci serve in questa tab
        self.btn_copy.pack_forget()

        # Rimuoviamo la selezione della cartella di destinazione (inutile qui)
        self.btn_dest.pack_forget()
        self.lbl_dest.pack_forget()

        # Inseriamo i controlli per l'output video nel left_panel
        # Li mettiamo sotto la sorgente per coerenza
        self.lbl_output_title = ctk.CTkLabel(
            self.left_panel,
            text="Output Video",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.lbl_output_title.pack(pady=(10, 5), after=self.lbl_source)
        
        self.btn_video_dest = ctk.CTkButton(
            self.left_panel, text="Scegli Destinazione Video", command=self.select_video_dest
        )
        # Lo packiamo dopo il titolo output
        self.btn_video_dest.pack(pady=5, fill="x", padx=10, after=self.lbl_output_title)
        
        self.lbl_video_dest = ctk.CTkLabel(
            self.left_panel,
            text="Nessun file selezionato",
            font=ctk.CTkFont(size=10),
            wraplength=200,
        )
        self.lbl_video_dest.pack(pady=2, after=self.btn_video_dest)

        # Durata e FPS (li mettiamo nel left_panel, sopra la progress bar)
        self.settings_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.settings_frame.pack(pady=10, fill="x", padx=5, before=self.progress_label)

        # Centriamo il contenuto della griglia
        self.settings_frame.grid_columnconfigure((0, 5), weight=1)

        ctk.CTkLabel(self.settings_frame, text="Durata (s):", font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=(2, 2), pady=2)
        self.entry_duration = ctk.CTkEntry(self.settings_frame, width=45)
        self.entry_duration.insert(0, "10")
        self.entry_duration.grid(row=0, column=2, padx=(0, 10), pady=2)

        ctk.CTkLabel(self.settings_frame, text="FPS:", font=ctk.CTkFont(size=11)).grid(row=0, column=3, padx=(2, 2), pady=2)
        self.combo_fps = ctk.CTkComboBox(self.settings_frame, values=["24", "25", "30", "60"], width=65)
        self.combo_fps.set("30")
        self.combo_fps.grid(row=0, column=4, padx=(0, 2), pady=2)

        # Bottone Genera (nel right_panel, sotto Applica Filtri)
        self.btn_generate_video = ctk.CTkButton(
            self.right_panel,
            text="Genera Timelapse Video",
            command=self.start_video_generation,
            fg_color="orange",
            text_color="black",
            font=ctk.CTkFont(weight="bold"),
            state="disabled",
            height=50
        )
        # Pack side="bottom" mette l'elemento in fondo. 
        # Dato che btn_apply è già packed con side="bottom", 
        # se packiamo btn_generate_video ORA con side="bottom", andrà SOTTO btn_apply?
        # In realtà andrà sopra se btn_apply è già lì.
        # Per averlo SOTTO, dobbiamo pack_forget btn_apply e poi packarli nell'ordine inverso.
        
        self.btn_apply.pack_forget()
        self.btn_generate_video.pack(side="bottom", pady=10, fill="x", padx=20)
        self.btn_apply.pack(side="bottom", pady=5, fill="x", padx=20)


    def select_video_dest(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("Video MP4", "*.mp4")],
            title="Salva Timelapse Video"
        )
        if path:
            self.video_dest_path = path
            self.lbl_video_dest.configure(text=os.path.basename(path))
            self._check_ready_to_generate()

    def _load_current_page(self):
        super()._load_current_page()
        self._check_ready_to_generate()

    def _check_ready_to_generate(self):
        if self.video_dest_path and self.total_filtered > 0:
            self.btn_generate_video.configure(state="normal")
        else:
            self.btn_generate_video.configure(state="disabled")

    def start_video_generation(self):
        if not self.video_dest_path or self.total_filtered == 0:
            return
        
        try:
            duration = float(self.entry_duration.get())
            fps = float(self.combo_fps.get())
        except ValueError:
            messagebox.showerror("Errore", "Durata e FPS devono essere numeri validi.")
            return

        self.btn_generate_video.configure(state="disabled")
        self.btn_apply.configure(state="disabled")
        
        threading.Thread(
            target=self._video_generation_thread,
            args=(duration, fps),
            daemon=True
        ).start()

    def _video_generation_thread(self, duration: float, fps: float):
        try:
            # 1. Recupero tutti i path delle foto filtrate (senza paginazione)
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

            # Prendiamo TUTTE le foto filtrate (limit=total_filtered)
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

            N = len(all_filtered)
            if N == 0:
                self.after(0, lambda: messagebox.showwarning("Attenzione", "Nessuna foto trovata con i filtri attuali."))
                return

            # 2. Campionamento Matematico
            K = int(duration * fps)
            if N <= K:
                sampled_indices = range(N)
                K = N # Ricalibriamo K se abbiamo meno foto del richiesto
            else:
                sampled_indices = [round(i * (N - 1) / (K - 1)) for i in range(K)]

            # 3. Configurazione VideoWriter
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(self.video_dest_path, fourcc, fps, (1920, 1080))

            # 4. Ciclo di Rendering
            for i, idx in enumerate(sampled_indices):
                filename, _, _ = all_filtered[idx]
                filepath = os.path.join(self.source_dir, filename)
                
                # Update UI
                self.after(0, lambda curr=i+1, total=K: self._update_render_progress(curr, total))
                
                img = cv2.imread(filepath)
                if img is not None:
                    img_resized = cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_LANCZOS4)
                    out.write(img_resized)
                
            out.release()
            
            self.after(0, lambda: messagebox.showinfo("Successo", f"Video generato con successo!\nSalvato in: {self.video_dest_path}"))
            
        except Exception as e:
            self.after(0, lambda err=e: messagebox.showerror("Errore Rendering", f"Si è verificato un errore: {err}"))
        finally:
            self.after(0, lambda: self.btn_generate_video.configure(state="normal"))
            self.after(0, lambda: self.btn_apply.configure(state="normal"))
            self.after(0, lambda: self.progress_label.configure(text="Pronto"))
            self.after(0, lambda: self.progress_bar.set(0))

    def _update_render_progress(self, curr, total):
        self.progress_bar.set(curr / total)
        self.progress_label.configure(text=f"Rendering frame {curr} di {total}...")
