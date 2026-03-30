import os
import sqlite3
import shutil
import math
import cv2
import numpy as np
import piexif
import io
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
        """Inizializza il database SQLite e aggiunge colonne mancanti."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS photos (
                        filename TEXT PRIMARY KEY,
                        date_taken TEXT,
                        iso INTEGER,
                        aperture REAL,
                        shutter REAL,
                        ev100 REAL,
                        sharpness_score REAL,
                        thumbnail BLOB
                    )
                """)
                # Verifica se la colonna thumbnail esiste (per migrazione DB esistenti)
                cursor.execute("PRAGMA table_info(photos)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'thumbnail' not in columns:
                    cursor.execute("ALTER TABLE photos ADD COLUMN thumbnail BLOB")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON photos(date_taken)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ev ON photos(ev100)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sharpness ON photos(sharpness_score)")
                conn.commit()
        except sqlite3.Error as e:
            print(f"Errore inizializzazione DB: {e}")

    def _convert_to_float(self, ratio: Any) -> float:
        if isinstance(ratio, (tuple, list)) and len(ratio) == 2:
            return float(ratio[0]) / float(ratio[1]) if ratio[1] != 0 else 0.0
        try: return float(ratio)
        except (ValueError, TypeError): return 0.0

    def process_image_data(self, filepath: str) -> Tuple[float, bytes]:
        """Calcola sharpness (gray) e genera thumbnail a colori (300x300)."""
        try:
            # Caricamento a colori per la miniatura
            img_color = cv2.imread(filepath, cv2.IMREAD_COLOR)
            if img_color is None: return 0.0, b""
            
            # 1. Calcolo Sharpness (su versione grigia temporanea)
            img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
            h, w = img_gray.shape[:2]
            scale = min(500/w, 500/h)
            img_resized_gray = cv2.resize(img_gray, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
            sharpness = cv2.Laplacian(img_resized_gray, cv2.CV_64F).var()

            # 2. Generazione Thumbnail con Aspect Ratio Originale
            # Altezza fissa a 300px, larghezza proporzionale
            img_rgb = cv2.cvtColor(img_color, cv2.COLOR_BGR2RGB)
            h_orig, w_orig = img_rgb.shape[:2]
            
            target_h = 300
            target_w = int(w_orig * (target_h / h_orig))
            thumb_size = (target_w, target_h)
            
            img_thumb = cv2.resize(img_rgb, thumb_size, interpolation=cv2.INTER_AREA)
            
            # Compressione JPEG in memoria
            is_success, buffer = cv2.imencode('.jpg', cv2.cvtColor(img_thumb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 75])
            return sharpness, buffer.tobytes()
        except Exception:
            return 0.0, b""

    def get_full_exif_data(self, filename: str) -> Tuple[str, Optional[str], Optional[int], Optional[float], Optional[float], Optional[float], float, bytes]:
        """Estrae EXIF, Sharpness e Thumbnail per un file."""
        filepath = os.path.join(self.source_dir, filename)
        res = [filename, None, None, None, None, None, 0.0, b""]
        try:
            # Calcolo Sharpness e Thumbnail
            res[6], res[7] = self.process_image_data(filepath)

            with Image.open(filepath) as img:
                exif = img._getexif()
                if exif:
                    tags = {TAGS.get(tag, tag): value for tag, value in exif.items()}
                    dt_str = tags.get("DateTimeOriginal")
                    res[1] = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S') if dt_str else \
                             datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S')
                    res[2] = tags.get("ISOSpeedRatings")
                    res[3] = self._convert_to_float(tags.get("FNumber"))
                    res[4] = self._convert_to_float(tags.get("ExposureTime"))
                    if res[3] and res[4] and res[2] and res[2] > 0:
                        ev = math.log2(res[3]**2 / res[4]) - math.log2(res[2] / 100.0)
                        res[5] = round(ev, 2)
        except Exception: pass
        return tuple(res)

    def scan_directory(self, progress_callback: Callable[[int, int], None]) -> int:
        all_files = [f for f in os.listdir(self.source_dir) 
                     if os.path.splitext(f)[1].lower() in self.IMAGE_EXTENSIONS]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Seleziona i file che hanno già una thumbnail valida (lunghezza > 0)
            cursor.execute("SELECT filename FROM photos WHERE thumbnail IS NOT NULL AND length(thumbnail) > 0")
            db_files = {row[0] for row in cursor.fetchall()}

        to_scan = [f for f in all_files if f not in db_files]
        total_files = len(all_files)
        total_to_scan = len(to_scan)

        if total_to_scan == 0:
            progress_callback(total_files, total_files)
            return total_files

        batch_data = []
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=max(1, os.cpu_count() - 1)) as executor:
            results = executor.map(self.get_full_exif_data, to_scan)
            for data in results:
                batch_data.append(data)
                processed_count += 1
                if len(batch_data) >= 200: # Batch più piccoli per gestire i BLOB in memoria
                    self._insert_batch(batch_data)
                    batch_data = []
                if processed_count % 10 == 0 or processed_count == total_to_scan:
                    progress_callback(len(all_files) - total_to_scan + processed_count, total_files)

        if batch_data:
            self._insert_batch(batch_data)
        return total_files

    def _insert_batch(self, data: List[tuple]):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany("INSERT OR REPLACE INTO photos VALUES (?, ?, ?, ?, ?, ?, ?, ?)", data)
                conn.commit()
        except sqlite3.Error as e:
            print(f"Errore inserimento batch: {e}")

    def get_total_count(self) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM photos")
                return cursor.fetchone()[0]
        except sqlite3.Error: return 0

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

    def get_sharpness_stats(self) -> Tuple[float, float]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT sharpness_score FROM photos WHERE sharpness_score > 0")
                scores = [r[0] for r in cursor.fetchall()]
                if not scores: return 0.0, 0.0
                return round(float(np.mean(scores)), 2), round(float(np.percentile(scores, 15)), 2)
        except Exception: return 0.0, 0.0

    def count_filtered_images(self, 
                             start_date: datetime, end_date: datetime,
                             min_ev: float, max_ev: float,
                             exclude_blur: bool, sharpness_threshold: float,
                             allowed_days: List[int]) -> int:
        """Restituisce il conteggio totale delle foto che corrispondono ai filtri."""
        sql_days = [0 if d == 6 else d + 1 for d in allowed_days]
        days_placeholder = ",".join(map(str, sql_days))
        blur_filter = f"AND sharpness_score > {sharpness_threshold}" if exclude_blur else ""
        
        query = f"SELECT COUNT(*) FROM photos WHERE date(date_taken) BETWEEN ? AND ? AND ev100 BETWEEN ? AND ? AND CAST(strftime('%w', date_taken) AS INTEGER) IN ({days_placeholder}) {blur_filter}"
        params = (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), min_ev, max_ev)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchone()[0]
        except sqlite3.Error: return 0

    def filter_images(self, 
                      start_date: datetime, end_date: datetime,
                      start_time: str, end_time: str,
                      allowed_days: List[int],
                      min_ev: float, max_ev: float,
                      exclude_blur: bool = False,
                      sharpness_threshold: float = 0.0) -> List[Tuple[str, datetime, bytes]]:
        """Filtraggio con LIMIT 150 per visualizzazione UI."""
        sql_days = [0 if d == 6 else d + 1 for d in allowed_days]
        days_placeholder = ",".join(map(str, sql_days))
        blur_filter = f"AND sharpness_score > {sharpness_threshold}" if exclude_blur else ""

        query = f"""
            SELECT filename, date_taken, thumbnail FROM photos
            WHERE date(date_taken) BETWEEN ? AND ?
            AND ev100 BETWEEN ? AND ?
            AND time(date_taken) BETWEEN ? AND ?
            AND CAST(strftime('%w', date_taken) AS INTEGER) IN ({days_placeholder})
            {blur_filter}
            ORDER BY date_taken ASC
            LIMIT 150
        """
        
        params = (
            start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'),
            min_ev, max_ev, f"{start_time}:00", f"{end_time}:59"
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                return [(r[0], datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S'), r[2]) for r in results]
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
