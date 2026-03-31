import os
import sys
from PIL import Image, ImageTk
import customtkinter as ctk
from tabs import HeroSelect, TimeStamper, SequenceBuilder


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class HerolapseStudio(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Herolapse Studio")
        self.geometry("1100x750")

        # Caricamento Icona Cross-Platform
        try:
            icon_path = resource_path("assets/herolapse.ico")
            if sys.platform.startswith("win"):
                self.iconbitmap(icon_path)
            else:
                img = Image.open(icon_path)
                photo = ImageTk.PhotoImage(img)
                self.wm_iconphoto(True, photo)
                self._icon_photo = photo
        except Exception as e:
            print(f"Errore nel caricamento dell'icona: {e}")

        # Widget Tabview Principale
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(padx=20, pady=20, fill="both", expand=True)

        self.tab_view.add("Hero Select")
        self.tab_view.add("TimeStamper")
        self.tab_view.add("Sequence Builder")

        # Inserimento dei frame nelle Tab
        self.filter_frame = HeroSelect(self.tab_view.tab("Hero Select"))
        self.filter_frame.pack(fill="both", expand=True)

        self.watermark_frame = TimeStamper(self.tab_view.tab("TimeStamper"))
        self.watermark_frame.pack(fill="both", expand=True)

        self.renamer_frame = SequenceBuilder(self.tab_view.tab("Sequence Builder"))
        self.renamer_frame.pack(fill="both", expand=True)


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

if __name__ == "__main__":
    app = HerolapseStudio()
    app.mainloop()
