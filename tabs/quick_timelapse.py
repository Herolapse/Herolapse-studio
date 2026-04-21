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
import time
from typing import List, Tuple, Callable, Optional, Any

# Patch per evitare crash in ambienti senza supporto GUI (NixOS, Headless)
def _patch_opencv_gui():
    def noop(*args, **kwargs): pass
    for func in ['imshow', 'waitKey', 'destroyAllWindows', 'namedWindow', 'setWindowProperty']:
        setattr(cv2, func, noop)

_patch_opencv_gui()

from .hero_select import HeroSelect, HeroSelectLogic

class QuickTimelapse(HeroSelect):
    """Tab 4: Generazione rapida di timelapse video dai dati filtrati."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.video_dest_path = ""

    def _setup_ui(self):
        # Chiamiamo il setup UI di base (quello di HeroSelect)
        super()._setup_ui()

        # Rimuoviamo elementi non necessari in questa tab
        self.btn_copy.pack_forget()
        self.btn_dest.pack_forget()
        self.lbl_dest.pack_forget()
        self.entry_start_date.pack_forget()
        self.entry_end_date.pack_forget()
        
        # Nascondiamo le sezioni filtri nel left_panel
        for widget in self.left_panel.winfo_children():
            if widget in [self.btn_source, self.lbl_source, self.progress_label, self.progress_bar]:
                continue
            if isinstance(widget, ctk.CTkLabel) and widget.cget("text") == "Configurazione Filtri":
                widget.configure(text="Configurazione Video")
                continue
            widget.pack_forget()

        # Controlli Output Video
        self.lbl_output_title = ctk.CTkLabel(
            self.left_panel,
            text="Output Video",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.lbl_output_title.pack(pady=(10, 5))
        
        self.btn_video_dest = ctk.CTkButton(
            self.left_panel, text="Scegli Destinazione Video", command=self.select_video_dest
        )
        self.btn_video_dest.pack(pady=5, fill="x", padx=10)
        
        self.lbl_video_dest = ctk.CTkLabel(
            self.left_panel,
            text="Nessun file selezionato",
            font=ctk.CTkFont(size=10),
            wraplength=200,
        )
        self.lbl_video_dest.pack(pady=2)

        # Impostazioni Durata e FPS
        self.settings_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.settings_frame.pack(pady=10, fill="x", padx=5)
        self.settings_frame.grid_columnconfigure((0, 5), weight=1)

        ctk.CTkLabel(self.settings_frame, text="Durata (s):", font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=(2, 2), pady=2)
        self.entry_duration = ctk.CTkEntry(self.settings_frame, width=45)
        self.entry_duration.insert(0, "10")
        self.entry_duration.grid(row=0, column=2, padx=(0, 10), pady=2)

        ctk.CTkLabel(self.settings_frame, text="FPS:", font=ctk.CTkFont(size=11)).grid(row=0, column=3, padx=(2, 2), pady=2)
        self.combo_fps = ctk.CTkComboBox(self.settings_frame, values=["24", "25", "30", "60"], width=65)
        self.combo_fps.set("30")
        self.combo_fps.grid(row=0, column=4, padx=(0, 2), pady=2)

        # Checkbox Dissolvenza (Anti-Flicker)
        self.check_fade = ctk.CTkCheckBox(self.settings_frame, text="Dissolvenza (Anti-Flicker)", font=ctk.CTkFont(size=11))
        self.check_fade.select()
        self.check_fade.grid(row=1, column=1, columnspan=4, pady=(5, 0))

        # Ri-packiamo progress bar in fondo
        self.progress_label.pack(side="bottom", pady=(5, 0))
        self.progress_bar.pack(side="bottom", pady=10, fill="x", padx=10)

        # Pulizia colonna destra
        self.scroll_frame.pack_forget()
        self.page_frame.pack_forget()
        self.lbl_count.pack_forget()
        self.btn_apply.pack_forget()
        self.btn_cancel.pack_forget() # Lo riposizioniamo

        btn_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        btn_frame.pack(expand=True)

        self.btn_generate_video = ctk.CTkButton(
            btn_frame,
            text="Genera Timelapse Video",
            command=self.start_video_generation,
            fg_color="orange",
            text_color="black",
            font=ctk.CTkFont(weight="bold"),
            state="disabled",
            height=60
        )
        self.btn_generate_video.pack()

        self.btn_cancel.configure(text="ANNULLA", height=60, font=ctk.CTkFont(weight="bold"), state="normal")
        # Hidden initially

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
        self._check_ready_to_generate()

    def _check_ready_to_generate(self):
        if self.video_dest_path and self.source_dir:
            self.btn_generate_video.configure(state="normal")
        else:
            self.btn_generate_video.configure(state="disabled")

    def start_video_generation(self):
        if not self.video_dest_path or not self.source_dir: return
        try:
            duration = float(self.entry_duration.get())
            fps = float(self.combo_fps.get())
        except ValueError:
            messagebox.showerror("Errore", "Dati non validi (Durata e FPS devono essere numeri).")
            return

        self.is_cancelled = False
        self.btn_generate_video.pack_forget()
        self.btn_cancel.pack()
        threading.Thread(target=self._video_generation_thread, args=(duration, fps), daemon=True).start()

    def _video_generation_thread(self, duration: float, fps: float):
        try:
            # 1. Recupero i file ordinati per data EXIF
            if not self.logic: self.logic = HeroSelectLogic(self.source_dir)
            with sqlite3.connect(self.logic.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT filename FROM photos ORDER BY date_taken ASC")
                all_files = [row[0] for row in cursor.fetchall()]

            if len(all_files) == 0:
                all_files = sorted([f for f in os.listdir(self.source_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.bmp'))])
            
            N = len(all_files)
            if N == 0:
                self.after(0, lambda: messagebox.showwarning("Attenzione", "Nessuna foto trovata nella cartella."))
                return

            # 2. Campionamento Frame
            use_fade = self.check_fade.get() == 1
            K = int(duration * fps)
            
            if use_fade:
                K_photos = int(K / 2) + 1
                sampled_indices = [round(i * (N - 1) / (max(1, K_photos - 1))) for i in range(min(N, K_photos))] if N > 1 else [0]
                total_frames = max(0, 2 * len(sampled_indices) - 1)
            else:
                sampled_indices = [round(i * (N - 1) / (max(1, K - 1))) for i in range(min(N, K))] if N > 1 else [0]
                total_frames = len(sampled_indices)

            # 3. Rendering Video
            out = cv2.VideoWriter(self.video_dest_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (1920, 1080))

            prev_frame_fade = None
            count = 0
            for idx in sampled_indices:
                if self.is_cancelled:
                    break
                img = cv2.imread(os.path.join(self.source_dir, all_files[idx]))
                if img is None: continue
                img = cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_LANCZOS4)
                
                # Effetto Dissolvenza (Anti-Flicker)
                if use_fade and prev_frame_fade is not None:
                    fade_frame = cv2.addWeighted(prev_frame_fade, 0.5, img, 0.5, 0)
                    out.write(fade_frame)
                    count += 1
                    self.after(0, lambda c=count, n=total_frames: self.progress_bar.set(c/n))

                out.write(img)
                count += 1
                self.after(0, lambda c=count, n=total_frames: self.progress_bar.set(c/n))
                prev_frame_fade = img.copy()
                
            out.release()
            
            if self.is_cancelled:
                if os.path.exists(self.video_dest_path):
                    try: os.remove(self.video_dest_path)
                    except: pass
                self.after(0, lambda: messagebox.showwarning("Annullato", "Generazione video annullata."))
            else:
                time.sleep(0.5) # Sicurezza per il lock del file su Windows
                self.after(0, lambda: messagebox.showinfo("Successo", "Video generato correttamente!"))
        except Exception as e:
            self.after(0, lambda err=e: messagebox.showerror("Errore", f"Errore durante il rendering: {err}"))
        finally:
            self.after(0, lambda: self.btn_cancel.pack_forget())
            self.after(0, lambda: self.btn_generate_video.pack())
            self.after(0, lambda: self.btn_generate_video.configure(state="normal"))
            self.after(0, lambda: self.progress_label.configure(text="Pronto"))
            self.after(0, lambda: self.progress_bar.set(0))
