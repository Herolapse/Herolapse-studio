import os
import json
import shutil
import piexif
from datetime import datetime
from typing import Dict, List, Tuple, Callable, Optional
from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS

class TimelapseLogic:
    CACHE_FILE = "timelapse_cache.json"
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}

    def __init__(self, source_dir: str):
        self.source_dir = source_dir
        self.cache_path = os.path.join(source_dir, self.CACHE_FILE)
        self.cache: Dict[str, str] = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=4)

    def get_exif_date(self, filepath: str) -> Optional[datetime]:
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
        
        mtime = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mtime)

    def scan_directory(self, progress_callback: Callable[[int, int], None]) -> int:
        """
        Scansiona la directory in parallelo per una velocità massima.
        """
        from concurrent.futures import ThreadPoolExecutor
        
        all_files = [f for f in os.listdir(self.source_dir) 
                     if os.path.splitext(f)[1].lower() in self.IMAGE_EXTENSIONS]
        
        # Filtriamo solo i file non ancora in cache
        to_scan = [f for f in all_files if f not in self.cache]
        total_files = len(all_files)
        total_to_scan = len(to_scan)
        
        if total_to_scan == 0:
            progress_callback(total_files, total_files)
            return total_files

        # Funzione helper per il thread
        def process_single_file(filename):
            filepath = os.path.join(self.source_dir, filename)
            dt = self.get_exif_date(filepath)
            return filename, dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None

        # Usiamo un pool di thread (il numero ottimale è solitamente 2x-4x i core per I/O)
        processed_count = 0
        with ThreadPoolExecutor(max_workers=os.cpu_count() * 2) as executor:
            results = executor.map(process_single_file, to_scan)
            
            for filename, dt_str in results:
                if dt_str:
                    self.cache[filename] = dt_str
                
                processed_count += 1
                # Aggiorniamo la UI (mostrando il totale complessivo)
                if processed_count % 50 == 0 or processed_count == total_to_scan:
                    progress_callback(len(all_files) - total_to_scan + processed_count, total_files)

        if total_to_scan > 0:
            self._save_cache()
        return total_files

    def filter_images(self, 
                      start_date: datetime, end_date: datetime,
                      start_time: str, end_time: str,
                      allowed_days: List[int]) -> List[Tuple[str, datetime]]:
        filtered_list = []
        st_h, st_m = map(int, start_time.split(':'))
        et_h, et_m = map(int, end_time.split(':'))

        for filename, dt_str in self.cache.items():
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            if not (start_date.date() <= dt.date() <= end_date.date()):
                continue
            if dt.weekday() not in allowed_days:
                continue
            current_time_minutes = dt.hour * 60 + dt.minute
            start_minutes = st_h * 60 + st_m
            end_minutes = et_h * 60 + et_m
            if not (start_minutes <= current_time_minutes <= end_minutes):
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
        """Aggiunge il watermark EXIF alla singola immagine."""
        try:
            with Image.open(image_path) as img:
                # Caricamento EXIF con piexif per estrarre la data precisa
                exif_data_raw = img.info.get("exif")
                if not exif_data_raw:
                    # Se mancano i raw exif, non possiamo procedere come richiesto dallo script
                    return False
                
                exif_dict = piexif.load(exif_data_raw)
                date_raw = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)

                if date_raw:
                    date_str = date_raw.decode("utf-8")
                    date_part, time_part = date_str.split(" ")
                    formatted_date = date_part.replace(":", "/") + "\n" + time_part
                    
                    # Logica di disegno (SPOSTATA ALL'INTERNO DEL CONTEXT MANAGER)
                    draw = ImageDraw.Draw(img)
                    img_width, img_height = img.size
                    
                    # Coordinata dinamica basata sulla dimensione immagine se possibile,
                    # altrimenti usiamo quelle fornite nello script originale (adatte a risoluzioni alte)
                    x, y = 3900, 3200
                    
                    # Font handling - Cerchiamo di usare un font caricabile o default
                    try:
                        # In alcune versioni di Pillow load_default non accetta size
                        font = ImageFont.load_default(size=200)
                    except TypeError:
                        font = ImageFont.load_default()

                    draw.text((x, y), formatted_date, font=font, fill="red")
                    
                    # Salvataggio preservando i metadati EXIF originali
                    img.save(output_path, "jpeg", exif=exif_data_raw, quality=95)
                    return True
        except Exception as e:
            print(f"Errore nel processare {image_path}: {e}")
            return False
        return False

    def process_directory(self, input_dir: str, output_dir: str, progress_callback: Callable[[int, int, str], None]):
        """Cicla tutti i file JPG della cartella di input."""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.jpg', '.jpeg'))]
        total = len(files)
        
        for i, filename in enumerate(files):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            
            success = self.add_date_label(input_path, output_path)
            
            status_msg = f"Processata {filename}" if success else f"Errore su {filename} (Nessun EXIF)"
            progress_callback(i + 1, total, status_msg)
