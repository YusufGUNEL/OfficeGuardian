"""Postür (Kamburluk) Analiz Modülü

Bu modül, kameradan alınan görüntüyü MediaPipe PoseLandmarker modeli ile
analiz ederek kişinin postürü hakkında bilgi üretir.

Çalışma Prensibi:
    1. Kameradan alınan her frame (görüntü karesi) MediaPipe modeline verilir
    2. Model, vücutta 33 anahtar nokta (landmark) tespit eder
    3. Bu noktalardan kulak, omuz ve kalça seçilir
    4. Omuz → kulak vektörü ile dikey eksen arasındaki açı = boyun eğilme açısı
    5. Kalça → omuz vektörü ile dikey eksen arasındaki açı = gövde eğilme açısı
    6. Açılar eşik değerlerini aşarsa KAMBUR olarak işaretlenir

Eşik Değerleri (config.py'den):
    - Boyun açısı > 25 derece → kambur
    - Gövde açısı > 15 derece → kambur

Skor Hesabı:
    - 0-100 arası postür skoru üretilir
    - Ağırlık: boyun %70, gövde %30
"""

import math
import time
from dataclasses import dataclass, field

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    PoseLandmarker,
    PoseLandmarkerOptions,
    PoseLandmarksConnections,
    RunningMode,
    drawing_utils,
)
from mediapipe.tasks.python.vision.drawing_utils import DrawingSpec

import config


@dataclass
class PostureResult:
    """Tek bir kişi için postür analiz sonucu.

    Alanlar:
        neck_angle  : Boyun öne eğilme açısı (derece). 0 = tam dik, 25+ = kambur
        torso_angle : Gövde eğilme açısı (derece). 0 = tam dik, 15+ = kambur
        is_good     : Postür iyi mi? (True = dik, False = kambur)
        score       : 0-100 arası postür kalite skoru
        landmarks   : MediaPipe NormalizedLandmark listesi (iskelet çizimi için)
        centroid    : Kişinin merkez noktası (normalize x, y). Kişi eşleştirme için
        nose_pos    : Burun konumu (normalize x, y). Yüz-vücut eşleştirmesi için
    """
    neck_angle: float       # Boyun öne eğilme açısı (derece)
    torso_angle: float      # Gövde eğilme açısı (derece)
    is_good: bool           # Postür iyi mi?
    score: int              # 0-100 arası postür skoru
    landmarks: list         # NormalizedLandmark listesi (çizim için)
    centroid: tuple = (0.0, 0.0)    # Normalize (x, y) merkez noktası
    nose_pos: tuple = (0.0, 0.0)    # Normalize burun konumu (eşleştirme için)


class PostureAnalyzer:
    """MediaPipe PoseLandmarker (Task API) ile kamburluk tespiti.

    Bu sınıf, video modunda çalışan bir PoseLandmarker modeli oluşturur
    ve her frame için postür analizi yapar.

    Kişisel mod için max_persons=1 (hızlı),
    ofis modu için max_persons=6 (çoklu kişi) olarak başlatılır.

    Kullanım:
        analyzer = PostureAnalyzer(neck_threshold=25, torso_threshold=15)
        sonuc = analyzer.analyze(frame_rgb)
        if sonuc and not sonuc.is_good:
            print("Kambur duruyorsun!")
    """

    def __init__(self, neck_threshold: float = 25, torso_threshold: float = 15,
                 max_persons: int = 1):
        """PostureAnalyzer oluşturur.

        Parametreler:
            neck_threshold  : Boyun açısı eşik değeri (derece). Üstü = kambur
            torso_threshold : Gövde açısı eşik değeri (derece). Üstü = kambur
            max_persons     : Aynı anda tespit edilecek max kişi sayısı
        """
        self.neck_threshold = neck_threshold
        self.torso_threshold = torso_threshold
        # Zaman sayacı: MediaPipe VIDEO modunda her frame için artan zaman damgası gerektirir
        self._start_time = time.monotonic()

        # MediaPipe PoseLandmarker modelini yükle
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=config.POSE_MODEL_PATH),
            running_mode=RunningMode.VIDEO,  # Video modu: frame'ler arası takip yapar
            num_poses=max_persons,            # Aynı anda kaç kişi tespit edilsin
            min_pose_detection_confidence=0.6,  # %60 algılama güveni eşiği
            min_pose_presence_confidence=0.5,   # %50 varlık güveni eşiği
            min_tracking_confidence=0.5,        # %50 takip güveni eşiği
        )
        self._landmarker = PoseLandmarker.create_from_options(options)
        # PoseLandmark enum'unu kolay erişim için sakla
        self._PL = mp.tasks.vision.PoseLandmark

    def analyze(self, frame_rgb: np.ndarray) -> PostureResult | None:
        """Tek kişi için postür analizi yapar.

        Parametreler:
            frame_rgb: RGB formatında görüntü (numpy dizisi, shape: H x W x 3)

        Döner:
            PostureResult nesnesi (kişi tespit edildiyse) veya None
        """
        results = self.analyze_all(frame_rgb)
        return results[0] if results else None

    def analyze_all(self, frame_rgb: np.ndarray) -> list[PostureResult]:
        """Tüm tespit edilen kişiler için postür analizi yapar.

        Frame içindeki tüm kişileri tespit eder ve her biri için
        ayrı PostureResult nesnesi döner.

        Parametreler:
            frame_rgb: RGB formatında görüntü (numpy dizisi)

        Döner:
            PostureResult listesi (boş liste = hiç kişi tespit edilemedi)
        """
        # MediaPipe VIDEO modunda artan zaman damgası gerekli
        timestamp_ms = int((time.monotonic() - self._start_time) * 1000)
        # Frame'i MediaPipe formatına çevir
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        # Modeli çalıştır ve sonuçları al
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        # Hiç kişi tespit edilmediyse boş liste dön
        if not result.pose_landmarks:
            return []

        results = []
        PL = self._PL

        # Her tespit edilen kişi için analiz yap
        for lm in result.pose_landmarks:
            # Anahtar vücut noktalarını seç
            l_ear = lm[PL.LEFT_EAR]          # Sol kulak
            r_ear = lm[PL.RIGHT_EAR]          # Sağ kulak
            l_shoulder = lm[PL.LEFT_SHOULDER]  # Sol omuz
            r_shoulder = lm[PL.RIGHT_SHOULDER] # Sağ omuz
            l_hip = lm[PL.LEFT_HIP]            # Sol kalça
            r_hip = lm[PL.RIGHT_HIP]           # Sağ kalça
            nose = lm[PL.NOSE]                  # Burun (eşleştirme için)

            # Sol ve sağın ortasını hesapla (simetri için)
            ear_mid = self._midpoint(l_ear, r_ear)
            shoulder_mid = self._midpoint(l_shoulder, r_shoulder)
            hip_mid = self._midpoint(l_hip, r_hip)

            # Boyun eğilme açısı: omuz ortası → kulak ortası vektörünün dikey ile açısı
            neck_vec = (ear_mid[0] - shoulder_mid[0], ear_mid[1] - shoulder_mid[1])
            neck_angle = self._angle_with_vertical(neck_vec)

            # Gövde eğilme açısı: kalça ortası → omuz ortası vektörünün dikey ile açısı
            torso_vec = (shoulder_mid[0] - hip_mid[0], shoulder_mid[1] - hip_mid[1])
            torso_angle = self._angle_with_vertical(torso_vec)

            # Karar ver: iki açı de eşiğin altındaysa postür iyi
            is_good = neck_angle < self.neck_threshold and torso_angle < self.torso_threshold

            # Postür skoru hesapla (0-100)
            # 0 = en kötü, 100 = tam dik
            # Boyun ağırlık: %70, gövde ağırlık: %30
            neck_ratio = max(0, 1 - neck_angle / (self.neck_threshold * 2))
            torso_ratio = max(0, 1 - torso_angle / (self.torso_threshold * 2))
            score = int((neck_ratio * 0.7 + torso_ratio * 0.3) * 100)

            # Kişinin merkez noktası (omuz ve kalça ortası)
            # Kişi eşleştirme için kullanılır (ofis modunda)
            cx = (shoulder_mid[0] + hip_mid[0]) / 2
            cy = (shoulder_mid[1] + hip_mid[1]) / 2

            results.append(PostureResult(
                neck_angle=round(neck_angle, 1),
                torso_angle=round(torso_angle, 1),
                is_good=is_good,
                score=score,
                landmarks=lm,
                centroid=(cx, cy),
                nose_pos=(nose.x, nose.y),
            ))

        return results

    def draw_landmarks(self, frame: np.ndarray, landmarks: list,
                       color: tuple = (0, 255, 0)) -> np.ndarray:
        """Görüntü üzerine iskelet (vücut noktalarını ve bağlantıları) çizer.

        Parametreler:
            frame     : BGR formatında görüntü (OpenCV)
            landmarks : MediaPipe NormalizedLandmark listesi
            color     : İskelet rengi (BGR). Varsayılan yeşil

        Döner:
            Üzerine çizim yapılmış frame
        """
        drawing_utils.draw_landmarks(
            image=frame,
            landmark_list=landmarks,
            connections=PoseLandmarksConnections.POSE_LANDMARKS,
            landmark_drawing_spec=DrawingSpec(color=color, thickness=2, circle_radius=2),
            connection_drawing_spec=DrawingSpec(color=(200, 200, 200), thickness=1, circle_radius=1),
        )
        return frame

    def close(self):
        """MediaPipe modelini serbest bırakır. Uygulama kapanırken çağrılmalıdır."""
        self._landmarker.close()

    # ── Dahili Yardımcı Metodlar ──────────────────────────────

    @staticmethod
    def _midpoint(a, b) -> tuple[float, float]:
        """İki nokta arasındaki orta noktayı hesaplar.
        a ve b: MediaPipe NormalizedLandmark nesneleri (.x, .y alanları var)
        """
        return ((a.x + b.x) / 2, (a.y + b.y) / 2)

    @staticmethod
    def _angle_with_vertical(vec: tuple[float, float]) -> float:
        """Bir vektörün dikey eksenle yaptığı açıyı derece cinsinden hesaplar.

        Dikey referans: yukarı yön (0, -1)
        Görüntü koordinatlarında y ekseni aşağı doğru artar,
        bu yüzden "yukarı" yönü (0, -1) olarak tanımlanır.

        Formül:
            cos(açı) = (A . B) / (|A| * |B|)
            A = verilen vektör, B = (0, -1)
            A . B = -Ay (çünkü Bx=0)

        Parametreler:
            vec: (vx, vy) şeklinde 2D vektör

        Döner:
            Derece cinsinden açı (0 = tam dik, 90 = tam yatay)
        """
        vx, vy = vec
        # Dikey referans (0, -1) ile nokta çarpımı: 0*vx + (-1)*vy = -vy
        dot = -vy
        # Vektörün büyüklüğü
        mag_v = math.sqrt(vx ** 2 + vy ** 2)
        if mag_v < 1e-6:
            return 0.0
        # Açıyı hesapla (güvenli aralık: -1 ile 1 arası)
        cos_angle = max(-1.0, min(1.0, dot / mag_v))
        return math.degrees(math.acos(cos_angle))
