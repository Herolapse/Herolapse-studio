import os
import json
import shutil
import math
import piexif
from datetime import datetime
from typing import Dict, List, Tuple, Callable, Optional, Union, Any
from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS

class TimelapseLogic:
    CACHE_FILE = "timelapse_cache.json"
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}

    def __init__(self, source_dir: str):
        self.source_dir = source_dir
        self.cache_path = os.path.join(source_dir, self.CACHE_FILE)
        self.cache: Dict[str, Any] = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Verifica se la cache è nel vecchio formato (stringa invece di dizionario)
                    # Se sì, la resettiamo per forzare la nuova scansione corretta
                    if data and isinstance(next(iter(data.values())), str):
                        return {}
                    return data
            except (json.JSONDecodeError, IOError, StopIteration):
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=4)

    def _convert_to_float(self, ratio: Any) -> float:
        """Converte tuple EXIF (numeratore, denominatore) in float."""
        if isinstance(ratio, (tuple, list)) and len(ratio) == 2:
            if ratio[1] == 0: return 0.0
            return float(ratio[0]) / float(ratio[1])
        try:
            return float(ratio)
        except (ValueError, TypeError):
            return 0.0

    def get_full_exif_data(self, filepath: str) -> Dict[str, Any]:
        """Estrae Date, ISO, Aperture, Shutter e calcola EV100."""
        res = {"date": None, "iso": None, "aperture": None, "shutter": None, "ev": None}
        try:
            with Image.open(filepath) as img:
                exif = img._getexif()
                if not exif: return res
                
                # Mappatura tag EXIF
                tags = {TAGS.get(tag, tag): value for tag, value in exif.items()}
                
                # 1. Data
                dt_str = tags.get("DateTimeOriginal")
                if dt_str:
                    res["date"] = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                else:
                    res["date"] = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S')

                # 2. Parametri per EV
                iso = tags.get("ISOSpeedRatings")
                aperture = self._convert_to_float(tags.get("FNumber"))
                shutter = self._convert_to_float(tags.get("ExposureTime"))

                res["iso"] = iso
                res["aperture"] = aperture
                res["shutter"] = shutter

                # 3. Calcolo EV100
                # Formula: EV = log2(N^2 / t) - log2(ISO / 100)
                if aperture > 0 and shutter > 0 and iso and iso > 0:
                    ev = math.log2(aperture**2 / shutter) - math.log2(iso / 100.0)
                    res["ev"] = round(ev, 2)
        except Exception as e:
            print(f"Errore EXIF in {filepath}: {e}")
        return res

    def scan_directory(self, progress_callback: Callable[[int, int], None]) -> int:
        from concurrent.futures import ThreadPoolExecutor
        all_files = [f for f in os.listdir(self.source_dir) 
                     if os.path.splitext(f)[1].lower() in self.IMAGE_EXTENSIONS]
        
        to_scan = [f for f in all_files if f not in self.cache]
        total_files = len(all_files)
        total_to_scan = len(to_scan)
        
        if total_to_scan == 0:
            progress_callback(total_files, total_files)
            return total_files

        def process_single_file(filename):
            filepath = os.path.join(self.source_dir, filename)
            data = self.get_full_exif_data(filepath)
            return filename, data

        processed_count = 0
        with ThreadPoolExecutor(max_workers=os.cpu_count() * 2) as executor:
            results = executor.map(process_single_file, to_scan)
            for filename, data in results:
                self.cache[filename] = data
                processed_count += 1
                if processed_count % 50 == 0 or processed_count == total_to_scan:
                    progress_callback(len(all_files) - total_to_scan + processed_count, total_files)

        self._save_cache()
        return total_files

    def get_ev_range(self) -> Tuple[Optional[float], Optional[float]]:
        """Restituisce il range Min/Max di EV rilevato nella cache."""
        ev_values = [v["ev"] for v in self.cache.values() if v.get("ev") is not None]
        if not ev_values: return None, None
        return min(ev_values), max(ev_values)

    def filter_images(self, 
                      start_date: datetime, end_date: datetime,
                      start_time: str, end_time: str,
                      allowed_days: List[int],
                      min_ev: float, max_ev: float) -> List[Tuple[str, datetime]]:
        filtered_list = []
        st_h, st_m = map(int, start_time.split(':'))
        et_h, et_m = map(int, end_time.split(':'))

        for filename, data in self.cache.items():
            if not data.get("date"): continue
            dt = datetime.strptime(data["date"], '%Y-%m-%d %H:%M:%S')
            
            # 1. Filtro Data/Ora/Giorni
            if not (start_date.date() <= dt.date() <= end_date.date()): continue
            if dt.weekday() not in allowed_days: continue
            
            current_time_minutes = dt.hour * 60 + dt.minute
            if not (st_h * 60 + st_m <= current_time_minutes <= et_h * 60 + et_m): continue
            
            # 2. Filtro EV
            ev = data.get("ev")
            if ev is None:
                # Se l'EV manca, saltiamo la foto e logghiamo
                print(f"Skipping {filename}: EV non calcolabile (EXIF mancanti)")
                continue
            
            if not (min_ev <= ev <= max_ev):
                continue

            filtered_list.append((filename, dt))
            
        filtered_list.sort(key=lambda x: x[1])
        return filtered_list

    def copy_files(self, files_to_copy: List[str], dest_dir: str, progress_callback: Callable[[int, int], None]):
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        total = len(files_to_copy)
        for i, filename in enumerate(files_to_copy):
            src = os.path.join(self.source_dir, filename)
            dst = os.path.join(dest_dir, filename)
            if not (os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst)):
                shutil.copy2(src, dst)
            if i % 5 == 0 or i == total - 1:
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
                    try:
                        font = ImageFont.load_default(size=200)
                    except TypeError:
                        font = ImageFont.load_default()

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
