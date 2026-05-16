import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# --- Model dosyaları ---
POSE_MODEL_PATH = os.path.join(MODELS_DIR, "pose_landmarker_lite.task")
FACE_MODEL_PATH = os.path.join(MODELS_DIR, "face_landmarker.task")

# --- Kamera ---
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# --- Postür Tespiti ---
# Boyun öne eğilme açısı eşiği (derece). Bu değerin üstü = kambur
NECK_ANGLE_THRESHOLD = 25
# Gövde eğilme açısı eşiği
TORSO_ANGLE_THRESHOLD = 15
# Kambur uyarısı gecikmesi (saniye) — bu süre boyunca kambur kalırsa uyar
POSTURE_WARNING_DELAY = 10

# --- Bakış / Çalışma Tespiti ---
# Baş dönüş açısı eşiği (yaw, derece)
GAZE_YAW_THRESHOLD = 25
# Baş eğilme açısı eşiği (pitch, derece)
GAZE_PITCH_THRESHOLD = 20
# Durum değişikliği gecikmesi (saniye) — anlık bakış kaymalarını filtreler
GAZE_STATUS_DELAY = 10

# --- Çoklu Kişi (Ofis Modu) ---
MAX_PERSONS = 6                    # Aynı anda takip edilecek max kişi
PERSON_DISAPPEAR_TIMEOUT = 5.0     # Kişi bu süre görünmezse listeden çıkar (sn)
PERSON_MATCH_THRESHOLD = 0.15      # Kişi eşleştirme mesafe eşiği (normalize)

# Kişi renkleri (BGR ve HEX çiftleri)
PERSON_COLORS = [
    {"bgr": (0, 200, 0),     "hex": "#00c800"},   # Yeşil
    {"bgr": (255, 165, 0),   "hex": "#ffa500"},   # Turuncu
    {"bgr": (255, 0, 255),   "hex": "#ff00ff"},   # Magenta
    {"bgr": (255, 255, 0),   "hex": "#ffff00"},   # Cyan
    {"bgr": (0, 128, 255),   "hex": "#ff8000"},   # Mavi-Turuncu
    {"bgr": (128, 0, 255),   "hex": "#ff0080"},   # Mor
]

# --- Arayüz ---
UI_UPDATE_MS = 66          # ~15 FPS
WINDOW_TITLE = "OfficeGuardian"
WINDOW_SIZE = "1100x680"

# --- Renkler ---
COLOR_GREEN = "#2ecc71"
COLOR_YELLOW = "#f39c12"
COLOR_RED = "#e74c3c"
COLOR_DARK_BG = "#1a1a2e"
COLOR_CARD_BG = "#16213e"
COLOR_TEXT = "#e0e0e0"
COLOR_ACCENT = "#0f3460"
