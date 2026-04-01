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
# VidStab a volte chiama cv2.destroyAllWindows() internamente.
def _patch_opencv_gui():
    def noop(*args, **kwargs):
        pass

    for func in [
        "imshow",
        "waitKey",
        "destroyAllWindows",
        "namedWindow",
        "setWindowProperty",
    ]:
        setattr(cv2, func, noop)


_patch_opencv_gui()

from .hero_select import HeroSelect, HeroSelectLogic

# Importiamo VidStab per la stabilizzazione
try:
    from vidstab import VidStab
except ImportError:
    VidStab = None


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

        # Rimuoviamo i filtri che l'utente farà nell'altra tab
        self.entry_start_date.pack_forget()
        self.entry_end_date.pack_forget()

        # Nascondiamo le sezioni filtri nel left_panel
        for widget in self.left_panel.winfo_children():
            # Teniamo solo Sorgente e Progress
            if widget in [
                self.btn_source,
                self.lbl_source,
                self.progress_label,
                self.progress_bar,
            ]:
                continue
            # Rinominiamo il titolo
            if (
                isinstance(widget, ctk.CTkLabel)
                and widget.cget("text") == "Configurazione Filtri"
            ):
                widget.configure(text="Configurazione Video")
                continue
            widget.pack_forget()

        # Inseriamo i controlli per l'output video nel left_panel
        self.lbl_output_title = ctk.CTkLabel(
            self.left_panel,
            text="Output Video",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.lbl_output_title.pack(pady=(10, 5))

        self.btn_video_dest = ctk.CTkButton(
            self.left_panel,
            text="Scegli Destinazione Video",
            command=self.select_video_dest,
        )
        self.btn_video_dest.pack(pady=5, fill="x", padx=10)

        self.lbl_video_dest = ctk.CTkLabel(
            self.left_panel,
            text="Nessun file selezionato",
            font=ctk.CTkFont(size=10),
            wraplength=200,
        )
        self.lbl_video_dest.pack(pady=2)

        # Durata e FPS
        self.settings_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.settings_frame.pack(pady=10, fill="x", padx=5)
        self.settings_frame.grid_columnconfigure((0, 5), weight=1)

        ctk.CTkLabel(
            self.settings_frame, text="Durata (s):", font=ctk.CTkFont(size=11)
        ).grid(row=0, column=1, padx=(2, 2), pady=2)
        self.entry_duration = ctk.CTkEntry(self.settings_frame, width=45)
        self.entry_duration.insert(0, "10")
        self.entry_duration.grid(row=0, column=2, padx=(0, 10), pady=2)

        ctk.CTkLabel(self.settings_frame, text="FPS:", font=ctk.CTkFont(size=11)).grid(
            row=0, column=3, padx=(2, 2), pady=2
        )
        self.combo_fps = ctk.CTkComboBox(
            self.settings_frame, values=["24", "25", "30", "60"], width=65
        )
        self.combo_fps.set("30")
        self.combo_fps.grid(row=0, column=4, padx=(0, 2), pady=2)

        # Checkbox Dissolvenza
        self.check_fade = ctk.CTkCheckBox(
            self.settings_frame,
            text="Dissolvenza (Anti-Flicker)",
            font=ctk.CTkFont(size=11),
        )
        self.check_fade.select()
        self.check_fade.grid(row=1, column=1, columnspan=4, pady=(5, 0))

        # Checkbox Stabilizzazione
        self.check_stabilize = ctk.CTkCheckBox(
            self.settings_frame,
            text="Stabilizza Video (VidStab)",
            font=ctk.CTkFont(size=11),
            fg_color="green",
        )
        self.check_stabilize.grid(row=2, column=1, columnspan=4, pady=(5, 0))

        # Ri-packiamo progress bar in fondo
        self.progress_label.pack(side="bottom", pady=(5, 0))
        self.progress_bar.pack(side="bottom", pady=10, fill="x", padx=10)

        # Pulizia colonna destra
        self.scroll_frame.pack_forget()
        self.page_frame.pack_forget()
        self.lbl_count.pack_forget()
        self.btn_apply.pack_forget()

        self.btn_generate_video = ctk.CTkButton(
            self.right_panel,
            text="Genera Timelapse",
            command=self.start_video_generation,
            fg_color="orange",
            text_color="black",
            font=ctk.CTkFont(weight="bold"),
            state="disabled",
            height=60,
        )
        self.btn_generate_video.pack(expand=True, padx=40)

    def select_video_dest(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("Video MP4", "*.mp4")],
            title="Salva Timelapse Video",
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
        if not self.video_dest_path or not self.source_dir:
            return
        try:
            duration = float(self.entry_duration.get())
            fps = float(self.combo_fps.get())
        except ValueError:
            messagebox.showerror("Errore", "Dati non validi.")
            return

        self.btn_generate_video.configure(state="disabled")
        threading.Thread(
            target=self._video_generation_thread, args=(duration, fps), daemon=True
        ).start()

    def _video_generation_thread(self, duration: float, fps: float):
        temp_unstable = "temp_unstable.mp4"
        try:
            # 1. Recupero i file dal database ordinati per data EXIF
            if not self.logic:
                self.logic = HeroSelectLogic(self.source_dir)

            with sqlite3.connect(self.logic.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT filename FROM photos ORDER BY date_taken ASC")
                all_files = [row[0] for row in cursor.fetchall()]

            N = len(all_files)
            if N == 0:
                all_files = sorted(
                    [
                        f
                        for f in os.listdir(self.source_dir)
                        if f.lower().endswith(
                            (".jpg", ".jpeg", ".png", ".tiff", ".bmp")
                        )
                    ]
                )
                N = len(all_files)
                if N == 0:
                    return

            # 2. Campionamento Matematico
            use_fade = self.check_fade.get() == 1
            should_stabilize = self.check_stabilize.get() == 1
            K = int(duration * fps)

            if use_fade:
                K_photos = int(K / 2) + 1
                sampled_indices = (
                    [
                        round(i * (N - 1) / (max(1, K_photos - 1)))
                        for i in range(min(N, K_photos))
                    ]
                    if N > 1
                    else [0]
                )
                total_frames = max(0, 2 * len(sampled_indices) - 1)
            else:
                sampled_indices = (
                    [round(i * (N - 1) / (max(1, K - 1))) for i in range(min(N, K))]
                    if N > 1
                    else [0]
                )
                total_frames = len(sampled_indices)

            # 3. Step 1: Generazione Video
            render_path = temp_unstable if should_stabilize else self.video_dest_path
            out = cv2.VideoWriter(
                render_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (1920, 1080)
            )

            prev_img = None
            count = 0
            for idx in sampled_indices:
                img = cv2.imread(os.path.join(self.source_dir, all_files[idx]))
                if img is None:
                    continue
                img_res = cv2.resize(
                    img, (1920, 1080), interpolation=cv2.INTER_LANCZOS4
                )

                if use_fade and prev_img is not None:
                    out.write(cv2.addWeighted(prev_img, 0.5, img_res, 0.5, 0))
                    count += 1
                    self.after(
                        0, lambda c=count: self.progress_bar.set(c / total_frames)
                    )

                out.write(img_res)
                count += 1
                self.after(0, lambda c=count: self.progress_bar.set(c / total_frames))
                prev_img = img_res

            out.release()

            # Delay per Windows lock
            time.sleep(0.5)

            # 4. Step 2: Stabilizzazione
            if should_stabilize and VidStab:
                self.after(
                    0, lambda: self.progress_label.configure(text="Stabilizzazione...")
                )
                stabilizer = VidStab()
                stabilizer.stabilize(
                    input_path=temp_unstable,
                    output_path=self.video_dest_path,
                    smoothing_window=30,
                    border_type="reflect",
                )

            self.after(0, lambda: messagebox.showinfo("Successo", "Video generato!"))
        except Exception as e:
            self.after(0, lambda err=e: messagebox.showerror("Errore", str(err)))
        finally:
            if os.path.exists(temp_unstable):
                time.sleep(0.5)
                try:
                    os.remove(temp_unstable)
                except:
                    pass
            self.after(0, lambda: self.btn_generate_video.configure(state="normal"))
            self.after(0, lambda: self.progress_label.configure(text="Pronto"))
            self.after(0, lambda: self.progress_bar.set(0))
