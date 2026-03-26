import os
import sqlite3
import shutil
import math
import piexif
from datetime import datetime
from typing import Dict, List, Tuple, Callable, Optional, Union, Any
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS

class TimelapseLogic:
    DB_NAME = "timelapse_cache.db"
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}

    def __init__(self, source_dir: str):
        self.source_dir = source_dir
        self.db_path = os.path.join(source_dir, self.DB_NAME)
        self._init_db()

    def _init_db(self):
        """Inizializza il database SQLite e crea tabelle/indici."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Creazione Tabella
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS photos (
                        filename TEXT PRIMARY KEY,
                        date_taken TEXT,
                        iso INTEGER,
                        aperture REAL,
                        shutter REAL,
                        ev100 REAL
                    )
                """)
                # Creazione Indici per filtraggio istantaneo
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON photos(date_taken)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ev ON photos(ev100)")
                conn.commit()
        except sqlite3.Error as e:
            print(f"Errore inizializzazione DB: {e}")

    def _convert_to_float(self, ratio: Any) -> float:
        if isinstance(ratio, (tuple, list)) and len(ratio) == 2:
            return float(ratio[0]) / float(ratio[1]) if ratio[1] != 0 else 0.0
        try: return float(ratio)
        except (ValueError, TypeError): return 0.0

    def get_full_exif_data(self, filename: str) -> Tuple[str, Optional[str], Optional[int], Optional[float], Optional[float], Optional[float]]:
        """Estrae dati EXIF e calcola EV100 per un singolo file."""
        filepath = os.path.join(self.source_dir, filename)
        res = [filename, None, None, None, None, None]
        try:
            with Image.open(filepath) as img:
                exif = img._getexif()
                if exif:
                    tags = {TAGS.get(tag, tag): value for tag, value in exif.items()}
                    
                    # Data
                    dt_str = tags.get("DateTimeOriginal")
                    res[1] = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S') if dt_str else \
                             datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S')

                    # Parametri EV
                    res[2] = tags.get("ISOSpeedRatings") # ISO
                    res[3] = self._convert_to_float(tags.get("FNumber")) # Aperture
                    res[4] = self._convert_to_float(tags.get("ExposureTime")) # Shutter

                    # Calcolo EV100
                    if res[3] and res[4] and res[2] and res[2] > 0:
                        ev = math.log2(res[3]**2 / res[4]) - math.log2(res[2] / 100.0)
                        res[5] = round(ev, 2)
        except Exception: pass
        return tuple(res)

    def scan_directory(self, progress_callback: Callable[[int, int], None]) -> int:
        """Scansione parallela con inserimento in batch nel database."""
        all_files = [f for f in os.listdir(self.source_dir) 
                     if os.path.splitext(f)[1].lower() in self.IMAGE_EXTENSIONS]
        
        # Recupero file già presenti nel DB per evitare scansioni doppie
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT filename FROM photos")
            db_files = {row[0] for row in cursor.fetchall()}

        to_scan = [f for f in all_files if f not in db_files]
        total_files = len(all_files)
        total_to_scan = len(to_scan)

        if total_to_scan == 0:
            progress_callback(total_files, total_files)
            return total_files

        # Estrazione dati in parallelo
        batch_data = []
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=os.cpu_count() * 2) as executor:
            results = executor.map(self.get_full_exif_data, to_scan)
            
            for data in results:
                batch_data.append(data)
                processed_count += 1
                
                # Inserimento in batch ogni 1000 record per performance
                if len(batch_data) >= 1000:
                    self._insert_batch(batch_data)
                    batch_data = []
                
                if processed_count % 50 == 0 or processed_count == total_to_scan:
                    progress_callback(len(all_files) - total_to_scan + processed_count, total_files)

        # Ultimo batch rimasto
        if batch_data:
            self._insert_batch(batch_data)

        return total_files

    def _insert_batch(self, data: List[tuple]):
        """Inserimento atomico di un blocco di dati."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany("INSERT OR REPLACE INTO photos VALUES (?, ?, ?, ?, ?, ?)", data)
                conn.commit()
        except sqlite3.Error as e:
            print(f"Errore inserimento batch: {e}")

    def get_total_count(self) -> int:
        """Restituisce il numero totale di foto censite nel database."""
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
            cursor.execute("SELECT MIN(ev100), MAX(ev100) FROM photos WHERE ev100 IS NOT NULL")
            return cursor.fetchone()

    def get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MIN(date(date_taken)), MAX(date(date_taken)) FROM photos")
            return cursor.fetchone()

    def filter_images(self, 
                      start_date: datetime, end_date: datetime,
                      start_time: str, end_time: str,
                      allowed_days: List[int],
                      min_ev: float, max_ev: float) -> List[Tuple[str, datetime]]:
        """Filtraggio eseguito interamente via SQL per velocità massima."""
        
        # SQLite strftime %w: 0=Domenica, 1=Lunedì... 6=Sabato.
        # UI days_vars: 0=Lunedì, 1=Martedì... 6=Domenica.
        # Conversione per SQL:
        sql_days = []
        for d in allowed_days:
            sql_days.append(0 if d == 6 else d + 1)
        
        days_placeholder = ",".join(map(str, sql_days))

        query = f"""
            SELECT filename, date_taken FROM photos
            WHERE date(date_taken) BETWEEN ? AND ?
            AND ev100 BETWEEN ? AND ?
            AND time(date_taken) BETWEEN ? AND ?
            AND CAST(strftime('%w', date_taken) AS INTEGER) IN ({days_placeholder})
            ORDER BY date_taken ASC
        """
        
        params = (
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            min_ev, max_ev,
            f"{start_time}:00", f"{end_time}:59"
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                # Conversione date string -> datetime per compatibilità con UI
                return [(r[0], datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S')) for r in results]
        except sqlite3.Error as e:
            print(f"Errore query filtraggio: {e}")
            return []

    def copy_files(self, files_to_copy: List[str], dest_dir: str, progress_callback: Callable[[int, int], None]):
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        total = len(files_to_copy)
        for i, filename in enumerate(files_to_copy):
            src = os.path.join(self.source_dir, filename)
            dst = os.path.join(dest_dir, filename)
            if not (os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst)):
                shutil.copy2(src, dst)
            if i % 10 == 0 or i == total - 1:
                progress_callback(i + 1, total)

class WatermarkLogic:
    @staticmethod
    def add_date_label(image_path: str, output_path: str):
        try:
            with Image.open(image_path) as img:
                exif_data_raw = img.info.get("exif")
                if not exif_data_raw: return False
                exif_dict = piexif.load(exif_data_raw)
                date_raw = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
                if date_raw:
                    date_str = date_raw.decode("utf-8")
                    date_part, time_part = date_str.split(" ")
                    formatted_date = date_part.replace(":", "/") + "\n" + time_part
                    draw = ImageDraw.Draw(img)
                    try: font = ImageFont.load_default(size=200)
                    except TypeError: font = ImageFont.load_default()
                    draw.text((3900, 3200), formatted_date, font=font, fill="red")
                    img.save(output_path, "jpeg", exif=exif_data_raw, quality=95)
                    return True
        except Exception: return False
        return False

    def process_directory(self, input_dir: str, output_dir: str, progress_callback: Callable[[int, int, str], None]):
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.jpg', '.jpeg'))]
        total = len(files)
        for i, filename in enumerate(files):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            success = self.add_date_label(input_path, output_path)
            status_msg = f"Processata {filename}" if success else f"Errore su {filename}"
            progress_callback(i + 1, total, status_msg)
