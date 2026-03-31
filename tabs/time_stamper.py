import threading
import os
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox
import piexif
from typing import Callable
from PIL import ImageDraw, ImageFont


class TimeStamper(ctk.CTkFrame):
    """
    Aggiunge i timestamp direttamente sulle foto (EXIF Data)
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.logic = TimeStamperLogic()
        self.input_dir = ""
        self.output_dir = ""
        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Aggiunge i timestamp direttamente sulle foto",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=20)

        self.btn_in = ctk.CTkButton(
            self, text="Seleziona Cartella Input", command=self.select_input
        )
        self.btn_in.pack(pady=10)
        self.lbl_in = ctk.CTkLabel(self, text="Nessuna cartella")
        self.lbl_in.pack()

        self.btn_out = ctk.CTkButton(
            self, text="Seleziona Cartella Output", command=self.select_output
        )
        self.btn_out.pack(pady=10)
        self.lbl_out = ctk.CTkLabel(self, text="Nessuna cartella")
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


class TimeStamperLogic:
    @staticmethod
    def add_date_label(image_path: str, output_path: str):
        try:
            with Image.open(image_path) as img:
                exif_data_raw = img.info.get("exif")
                if not exif_data_raw:
                    return False
                exif_dict = piexif.load(exif_data_raw)
                date_raw = exif_dict.get("Exif", {}).get(
                    piexif.ExifIFD.DateTimeOriginal
                )
                if date_raw:
                    date_str = date_raw.decode("utf-8")
                    date_part, time_part = date_str.split(" ")
                    formatted_date = date_part.replace(":", "/") + "\n" + time_part
                    draw = ImageDraw.Draw(img)
                    try:
                        font = ImageFont.load_default(size=200)
                    except TypeError:
                        font = ImageFont.load_default()
                    draw.text((3900, 3200), formatted_date, font=font, fill="red")
                    img.save(output_path, "jpeg", exif=exif_data_raw, quality=95)
                    return True
        except Exception:
            return False
        return False

    def process_directory(
        self,
        input_dir: str,
        output_dir: str,
        progress_callback: Callable[[int, int, str], None],
    ):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        files = [
            f for f in os.listdir(input_dir) if f.lower().endswith((".jpg", ".jpeg"))
        ]
        total = len(files)
        for i, filename in enumerate(files):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            success = self.add_date_label(input_path, output_path)
            status_msg = (
                f"Processata {filename}" if success else f"Errore su {filename}"
            )
            progress_callback(i + 1, total, status_msg)
