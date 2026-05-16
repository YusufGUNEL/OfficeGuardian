"""MediaPipe model dosyalarını indirir. İlk kurulumda bir kez çalıştırılmalıdır."""

import os
import urllib.request

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

MODELS = {
    "pose_landmarker_lite.task": (
        "https://storage.googleapis.com/mediapipe-models/"
        "pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    ),
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/"
        "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
    ),
}


def download_models():
    os.makedirs(MODELS_DIR, exist_ok=True)
    for filename, url in MODELS.items():
        path = os.path.join(MODELS_DIR, filename)
        if os.path.exists(path):
            print(f"  [OK] {filename} zaten mevcut")
            continue
        print(f"  [..] {filename} indiriliyor...")
        urllib.request.urlretrieve(url, path)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  [OK] {filename} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    print("MediaPipe modelleri indiriliyor...\n")
    download_models()
    print("\nTamamlandı!")
