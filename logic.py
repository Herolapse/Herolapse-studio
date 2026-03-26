import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Tuple, Callable, Optional
from PIL import Image
from PIL.ExifTags import TAGS

class TimelapseLogic:
    CACHE_FILE = "timelapse_cache.json"
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}

    def __init__(self, source_dir: str):
        self.source_dir = source_dir
        self.cache_path = os.path.join(source_dir, self.CACHE_FILE)
        self.cache: Dict[str, str] = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        """Carica la cache esistente dal file JSON."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        """Salva la cache corrente nel file JSON."""
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=4)

    def get_exif_date(self, filepath: str) -> Optional[datetime]:
        """Estrae la data di scatto dai metadati EXIF o dalla data di modifica."""
        try:
            img = Image.open(filepath)
            exif_data = img._getexif()
            if exif_data:
                for tag, value in exif_data.items():
                    tag_name = TAGS.get(tag, tag)
                    if tag_name == 'DateTimeOriginal':
                        return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
        except Exception:
            pass
        
        # Fallback alla data di modifica del file
        mtime = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mtime)

    def scan_directory(self, progress_callback: Callable[[int, int], None]) -> int:
        """
        Scansiona la directory sorgente per nuove immagini.
        Aggiorna la cache in modo incrementale.
        """
        files = [f for f in os.listdir(self.source_dir) 
                 if os.path.splitext(f)[1].lower() in self.IMAGE_EXTENSIONS]
        total_files = len(files)
        new_entries = 0

        for i, filename in enumerate(files):
            if filename not in self.cache:
                filepath = os.path.join(self.source_dir, filename)
                dt = self.get_exif_date(filepath)
                if dt:
                    self.cache[filename] = dt.strftime('%Y-%m-%d %H:%M:%S')
                    new_entries += 1
            
            # Notifica progresso ogni 10 file per non sovraccaricare la UI
            if i % 10 == 0 or i == total_files - 1:
                progress_callback(i + 1, total_files)

        if new_entries > 0:
            self._save_cache()
        
        return total_files

    def filter_images(self, 
                      start_date: datetime, end_date: datetime,
                      start_time: str, end_time: str,
                      allowed_days: List[int]) -> List[Tuple[str, datetime]]:
        """
        Filtra le immagini basandosi sui criteri forniti.
        allowed_days: List[int] dove 0=Lunedì, 6=Domenica.
        """
        filtered_list = []
        
        # Parsing orari (formato HH:MM)
        st_h, st_m = map(int, start_time.split(':'))
        et_h, et_m = map(int, end_time.split(':'))

        for filename, dt_str in self.cache.items():
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            
            # Filtro Data
            if not (start_date.date() <= dt.date() <= end_date.date()):
                continue
            
            # Filtro Giorno della settimana
            if dt.weekday() not in allowed_days:
                continue
                
            # Filtro Orario
            current_time_minutes = dt.hour * 60 + dt.minute
            start_minutes = st_h * 60 + st_m
            end_minutes = et_h * 60 + et_m
            
            if not (start_minutes <= current_time_minutes <= end_minutes):
                continue

            filtered_list.append((filename, dt))
            
        # Ordina per data per sicurezza
        filtered_list.sort(key=lambda x: x[1])
        return filtered_list

    def copy_files(self, 
                   files_to_copy: List[str], 
                   dest_dir: str, 
                   progress_callback: Callable[[int, int], None]):
        """Copia i file filtrati nella cartella di destinazione."""
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
            
        total = len(files_to_copy)
        for i, filename in enumerate(files_to_copy):
            src = os.path.join(self.source_dir, filename)
            dst = os.path.join(dest_dir, filename)
            
            # Evita sovrascritture se il file esiste già e ha stessa dimensione
            if os.path.exists(dst) and os.path.getsize(src) == os.path.getsize(dst):
                pass
            else:
                shutil.copy2(src, dst)
                
            if i % 5 == 0 or i == total - 1:
                progress_callback(i + 1, total)
