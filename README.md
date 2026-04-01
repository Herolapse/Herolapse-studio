# Herolapse Studio

**Herolapse Studio** is a powerful Python-based desktop application designed for timelapse photographers and videographers. It streamlines the tedious process of filtering thousands of raw images, applying metadata-based watermarks, and preparing sequences for professional video editing software like Adobe Premiere Pro.

---

## 🚀 Key Features

### 1. Hero Select (Timelapse Filter)
The core engine of the app. It allows you to scan massive directories of images and filter them based on:
*   **Time & Date:** Select specific date ranges, hours of the day, or even specific days of the week (e.g., "Mondays to Fridays only").
*   **Exposure Control (EV100):** Automatically detects the exposure range and lets you filter out photos that are too dark or too bright.
*   **Quality Control:** Uses Laplacian variance to detect and exclude blurry photos or images affected by heavy fog/haze.
*   **Visual Preview:** High-performance thumbnail grid with pagination to review your selection before calling for action.

### 2. TimeStamper (Watermark Tool)
Automate the process of stamping information onto your photos:
*   **EXIF Data Integration:** Automatically extracts and burns metadata (like date/time or camera settings) onto the images.
*   **Batch Processing:** Fast, multi-threaded processing for large datasets.

### 3. Sequence Builder (Premiere Renamer)
Prepares your filtered images for a seamless "Image Sequence" import in Adobe Premiere Pro or other NLEs:
*   **Numerical Ordering:** Renames files into a continuous numerical sequence (e.g., `hero_0001.jpg`, `hero_0002.jpg`).
*   **Custom Prefixes:** Define your project name as a prefix for better organization.

### 4. Quick Timelapse (Video Generator)
A dedicated rendering engine to quickly create high-quality video previews from your filtered photos:
*   **Fast Rendering:** Uses OpenCV to compile images into a `.mp4` video directly.
*   **Chronological Ordering:** Automatically sorts photos by EXIF `date_taken` metadata to ensure a perfect timeline.
*   **Anti-Flicker (Fade):** Optional frame interpolation with 50% opacity blending to eliminate flickering and ensure smooth transitions.
*   **Customizable Settings:** Set the desired duration (seconds) and frame rate (FPS) for the final output.

---

## 🛠 Tech Stack
*   **UI Framework:** [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (Modern Dark Theme).
*   **Image & Video Processing:** OpenCV (cv2), Pillow (PIL).
*   **Database:** SQLite (used for high-speed metadata indexing).
*   **Packaging:** PyInstaller (with Docker/Wine for cross-platform builds).

---

## 📦 Installation & Usage

### Prerequisites
*   Python 3.10+
*   Dependencies listed in `requirements.txt`

### Running from source
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the app:
   ```bash
   python main.py
   ```

---

## 🔨 Building the Executable

The project includes a `Makefile` to automate the creation of standalone executables using Docker.

### For Windows (.exe)
Requires Docker. This uses a Wine-based container to compile a native Windows executable from Linux/macOS:
```bash
make build-windows
```
*Output: `dist/windows/Herolapse_Studio.exe`*

### For Linux
```bash
make build-linux
```
*Output: `dist/Herolapse_Studio_Linux`*

---

## 📂 Project Structure
*   `main.py`: The entry point and UI logic.
*   `tabs/`: Package containing UI frames and logic for each feature (Hero Select, TimeStamper, Sequence Builder, Quick Timelapse).
*   `assets/`: Icons and branding resources.
*   `Makefile`: Build automation scripts.
