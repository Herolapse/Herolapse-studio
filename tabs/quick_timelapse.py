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

        # Modifichiamo il bottone "Copia Foto Filtrate" che non ci serve in questa tab
        # o meglio, lo nascondiamo e aggiungiamo i controlli video.
        self.btn_copy.pack_forget()

        # Pannello Controlli Video (aggiunto in fondo al left_panel)
        # Recuperiamo il left_panel (sappiamo che è il primo figlio di self)
        # In realtà è meglio ricostruire un po' il layout per inserire i nuovi controlli.
        
        # Cerchiamo il left_panel tra i figli
        left_panel = None
        for child in self.winfo_children():
            if isinstance(child, ctk.CTkFrame) and child.grid_info().get("column") == 0:
                left_panel = child
                break
        
        if left_panel:
            # Rimuoviamo la progress bar e label vecchie per riposizionarle sotto i nuovi controlli
            self.progress_bar.pack_forget()
            self.progress_label.pack_forget()

            ctk.CTkLabel(
                left_panel,
                text="Output Video",
                font=ctk.CTkFont(size=16, weight="bold"),
            ).pack(pady=(20, 10))

            self.btn_video_dest = ctk.CTkButton(
                left_panel, text="Scegli Destinazione Video", command=self.select_video_dest
            )
            self.btn_video_dest.pack(pady=5, fill="x", padx=10)
            
            self.lbl_video_dest = ctk.CTkLabel(
                left_panel,
                text="Nessun file selezionato",
                font=ctk.CTkFont(size=10),
                wraplength=200,
            )
            self.lbl_video_dest.pack(pady=2)

            # Durata e FPS
            settings_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
            settings_frame.pack(pady=5, fill="x", padx=10)
            
            ctk.CTkLabel(settings_frame, text="Durata (s):", font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="w")
            self.entry_duration = ctk.CTkEntry(settings_frame, width=60)
            self.entry_duration.insert(0, "10")
            self.entry_duration.grid(row=0, column=1, padx=5, pady=2)

            ctk.CTkLabel(settings_frame, text="FPS:", font=ctk.CTkFont(size=12)).grid(row=1, column=0, sticky="w")
            self.combo_fps = ctk.CTkComboBox(settings_frame, values=["24", "25", "30", "60"], width=70)
            self.combo_fps.set("30")
            self.combo_fps.grid(row=1, column=1, padx=5, pady=2)

            # Bottone Genera
            self.btn_generate_video = ctk.CTkButton(
                left_panel,
                text="Genera Timelapse Video",
                command=self.start_video_generation,
                fg_color="orange",
                text_color="black",
                font=ctk.CTkFont(weight="bold"),
                state="disabled"
            )
            self.btn_generate_video.pack(pady=10, fill="x", padx=10)

            # Riposizioniamo progress bar e label
            self.progress_label.pack(side="bottom", pady=(5, 0))
            self.progress_bar.pack(side="bottom", pady=10, fill="x", padx=10)

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
