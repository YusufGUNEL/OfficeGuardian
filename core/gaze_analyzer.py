"""
Bakış Yönü Analiz Modülü (Gaze Analyzer)
=========================================

Bu modül, kamera görüntüsünden kullanıcının baş pozisyonunu ve bakış yönünü
tespit etmek için kullanılır. Temel çalışma prensibi şu adımlara dayanır:

1. **MediaPipe FaceLandmarker ile Yüz Noktası Tespiti**:
   Google'ın MediaPipe kütüphanesinin Task API'si kullanılarak yüz üzerindeki
   468 adet 3D referans noktası (landmark) tespit edilir. Bu noktalar, yüzün
   burun ucu, göz köşeeleri, ağız köşeleri, çene gibi anatomik bölgelere
   karşılık gelir. FaceLandmarker, önceden eğitilmiş bir makine öğrenimi modeli
   kullanarak bu noktaları her video karesinde gerçek zamanlı olarak hesaplar.

2. **solvePnP ile 3D Poz Tahmini (Perspective-n-Point)**:
   OpenCV'nin cv2.solvePnP fonksiyonu, bilinen 3D model noktalarını (örneğin
   standart bir yüz modelinin burun, göz, ağız koordinatları) ile 2D görüntüdeki
   karşılık gelen piksel konumlarını eşleştirerek, kameranın yüz modeline göre
   rotasyon (dönüş) ve translasyon (öteleme) vektörlerini hesaplar. Bu işlem,
   "Perspektif n-Nokta" problemi olarak bilinir ve en az 4 nokta çifti ile
   çözülebilir. Bu modülde 6 adet referans noktası kullanılmaktadır:
     - Burun ucu (landmark 1)
     - Çene (landmark 152)
     - Sol göz dış köşe (landmark 33)
     - Sağ göz dış köşe (landmark 263)
     - Sol ağız köşesi (landmark 61)
     - Sağ ağız köşesi (landmark 291)

3. **Rodrigues Dönüşümü ve Euler Açıları**:
   solvePnP'den elde edilen rotasyon vektörü (rvec), cv2.Rodrigues ile 3x3'lük
   bir rotasyon matrisine (rmat) dönüştürülür. Ardından bu rotasyon matrisi,
   insanlar için anlamlı olan üç Euler açısına ayrıştırılır:
     - **Pitch (X ekseni)**: Başın yukarı/aşağı eğnme açısı. Pozitif değerler
       aşağı bakışı, negatif değerler yukarı bakışı gösterir.
     - **Yaw (Y ekseni)**: Başın sola/sağa dönüş açısı. Pozitif değerler sağa
       dönüşü, negatif değerler sola dönüşü gösterir.
     - **Roll (Z ekseni)**: Başın yana yatma (eğme) açısı. Pozitif değerler
       saat yönünde, negatif değerler saat yönünün tersine yatmayı gösterir.

   Euler açıları, atan2 fonksiyonu ile rotasyon matrisinin elemanlarından
   hesaplanır. Gimbal lock (tekil durum) kontrolü yapılarak, sy < 1e-6
   durumunda alternatif bir hesaplama yolu kullanılır.

4. **Ekrana Bakış Tespiti**:
   Hesaplanan yaw ve pitch açıları, belirlenen eşik değerleriyle (varsayılan
   olarak yaw için 25 derece, pitch için 20 derece) karşılaştırılır. Her iki
   açının mutlak değeri eşik değerinin altındaysa, kullanıcının ekrana baktığı
   kabul edilir.

Kullanım Örneği:
    >>> analyzer = GazeAnalyzer(yaw_threshold=25, pitch_threshold=20)
    >>> result = analyzer.analyze(frame_rgb)
    >>> if result and result.looking_at_screen:
    ...     print("Kullanıcı ekrana bakıyor")
    >>> analyzer.close()

Bağımlılıklar:
    - OpenCV (cv2): Görüntü işleme ve solvePnP hesaplamaları için
    - MediaPipe: Yüz noktası tespiti için (FaceLandmarker Task API)
    - NumPy: Matris ve vektör işlemleri için
"""

import math
import time
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    FaceLandmarksConnections,
    RunningMode,
    drawing_utils,
)
from mediapipe.tasks.python.vision.drawing_utils import DrawingSpec

import config


@dataclass
class GazeResult:
    """
    Bakış analizi sonucunu temsil eden veri sınıfı (dataclass).

    Bu sınıf, tek bir yüz için yapılan bakış yönü analizinin tüm sonuçlarını
    bir arada tutar. Her bir alan, başın 3 boyutlu uzaydaki konumunu ve
    kullanıcının ekrana bakıp bakmadığını belirtir.

    Alanlar:
        pitch (float):
            Başın yukarı/aşağı eğme açısı, derece cinsinden.
            Pozitif değer: baş aşağı eğik (örneğin telefona bakma).
            Negatif değer: baş yukarı kalkık (örneğin tavana bakma).
            Örnek: pitch=15.3 -> baş hafifçe aşağı eğik.

        yaw (float):
            Başın sola/sağa dönüş açısı, derece cinsinden.
            Pozitif değer: baş sağa dönük (kullanıcının perspektifinden).
            Negatif değer: baş sola dönük.
            Örnek: yaw=-30.2 -> baş belirgin şekilde sola dönük.

        roll (float):
            Başın yana yatma (eğme) açısı, derece cinsinden.
            Pozitif değer: baş saat yönünde eğik.
            Negatif değer: baş saat yönünün tersine eğik.
            Örnek: roll=5.0 -> baş hafifçe sağa yatık.

        looking_at_screen (bool):
            Kullanıcının ekrana bakıp bakmadığını gösteren bayrak.
            True: yaw ve pitch açıları belirlenen eşik değerlerinin altında,
                  yani kullanıcı büyük olasılıkla ekrana bakıyor.
            False: baş yeterince dönük veya eğik, kullanıcı başka yere bakıyor.

        face_landmarks (list):
            MediaPipe tarafından tespit edilen yüz referans noktaları
            (NormalizedLandmark) listesi. Bu liste, yüz üzerindeki 468 noktanın
            her birinin normalize edilmiş (0.0 - 1.0 arasında) x, y, z
            koordinatlarını içerir. Yüz çizimi (draw_landmarks) ve diğer
            görsel işlemler için kullanılır.

        nose_pos (tuple):
            Burun ucunun normalize edilmiş (x, y) konumu. Değerler 0.0 ile 1.0
            arasında olup, görüntünün sol üst köşesi (0,0) ve sağ alt köşesi
            (1,1) olarak kabul edilir. Bu konum, birden fazla yüz tespit
            edildiğnde yüzlerin eşleşmesi (tracking) için kullanılır.
            Varsayılan değer: (0.0, 0.0).
    """
    pitch: float            # Başın yukarı/aşağı eğme açısı (derece cinsinden)
    yaw: float              # Başın sola/sağa dönüş açısı (derece cinsinden)
    roll: float             # Başın yana yatma açısı (derece cinsinden)
    looking_at_screen: bool # Kullanıcının ekrana bakıp bakmadığını gösteren bayrak
    face_landmarks: list    # MediaPipe NormalizedLandmark listesi (görsel çizim için)
    nose_pos: tuple = (0.0, 0.0)  # Normalize burun konumu (yüz eşleştirme/takip için)


class GazeAnalyzer:
    """
    MediaPipe FaceLandmarker (Task API) ve OpenCV solvePnP kullanarak
    gerçek zamanlı bakış yönü analizi yapan sınıf.

    Bu sınıf, video karesindeki yüzleri tespit eder, 3D baş pozisyonunu
    hesaplar ve kullanıcının ekrana bakıp bakmadığını belirler.

    Çalışma Mantığı:
        1. MediaPipe FaceLandmarker ile yüz üzerindeki 468 referans noktası
           tespit edilir.
        2. Bu noktalardan 6 tanesi (burun, çene, gözler, ağız köşeleri)
           seçilerek 2D görüntü koordinatlarına dönüştürülür.
        3. OpenCV solvePnP fonksiyonu ile 3D model noktalarının 2D görüntü
           noktalarına projeksiyonu çözülerek rotasyon matrisi elde edilir.
        4. Rotasyon matrisinden Euler açıları (pitch, yaw, roll) hesaplanır.
        5. Bu açılar eşik değerleriyle karşılaştırılarak ekrana bakış durumu
           belirlenir.

    Kullanım Örneği:
        >>> from core.gaze_analyzer import GazeAnalyzer
        >>>
        >>> # Analizör oluştur (varsayılan eşik değerleri ile)
        >>> analyzer = GazeAnalyzer(yaw_threshold=25, pitch_threshold=20)
        >>>
        >>> # Kameradan alınan RGB formatındaki görüntü karesi
        >>> # frame_rgb = ...  # numpy dizisi, şekli: (yükseklik, genişlik, 3)
        >>>
        >>> # Tek yüz analizi (en yakın/büyük yüz)
        >>> result = analyzer.analyze(frame_rgb)
        >>> if result is not None:
        ...     print(f"Pitch: {result.pitch}, Yaw: {result.yaw}")
        ...     if result.looking_at_screen:
        ...         print("Kullanıcı ekrana bakıyor")
        ...     else:
        ...         print("Kullanıcı başka yere bakıyor")
        >>>
        >>> # Birden fazla yüz analizi
        >>> results = analyzer.analyze_all(frame_rgb)
        >>> for i, r in enumerate(results):
        ...     print(f"Yüz {i}: pitch={r.pitch}, yaw={r.yaw}")
        >>>
        >>> # Kaynakları serbest bırak
        >>> analyzer.close()

    Notlar:
        - Giriş görüntüsü RGB formatında olmalıdır (BGR değil). OpenCV ile
          okunan görüntüler varsayılan olarak BGR formatındadır, bu nedenle
          cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) ile dönüşüm yapılmalıdır.
        - close() metodu, MediaPipe kaynaklarını serbest bırakmak için
          kullanım sonrasında mutlaka çağrılmalıdır.
        - VIDEO modunda çalışır; her kare için artan bir zaman damgası
          (timestamp) gerektirir. Bu otomatik olarak yönetilir.
    """

    # -------------------------------------------------------------------------
    # solvePnP için 3 boyutlu yüz modeli referans noktaları.
    # Bu noktalar, standart bir insan yüzünün 3D koordinat sistemindeki
    # anatomik konumlarını temsil eder. Birim keyfi olup, önemli olan
    # noktaların birbirine göre orantısıdır.
    # Koordinat sistemi: X ekseni sağa, Y ekseni aşağı, Z ekseni içeri
    # (kameraya doğru) yönelir.
    # -------------------------------------------------------------------------
    _MODEL_POINTS = np.array([
        (0.0, 0.0, 0.0),            # Burun ucu - referans noktası (orijin)
        (0.0, -330.0, -65.0),        # Çene - burun ucunun altında ve hafifçe geride
        (-225.0, 170.0, -135.0),     # Sol göz dış köşe - solda, yukarda ve geride
        (225.0, 170.0, -135.0),      # Sağ göz dış köşe - sağda, yukarda ve geride
        (-150.0, -150.0, -125.0),    # Sol ağız köşesi - solda, aşağıda ve geride
        (150.0, -150.0, -125.0),     # Sağ ağız köşesi - sağda, aşağıda ve geride
    ], dtype=np.float64)

    # -------------------------------------------------------------------------
    # MediaPipe Face Mesh landmark indeksleri.
    # Yukarıdaki _MODEL_POINTS dizisindeki 3D noktalarla bire bir eşleşir.
    # MediaPipe, yüz üzerinde toplam 468 referans noktası üretir;
    # bunlardan sadece 6 tanesi solvePnP için seçilmiştir.
    # Sıralama: [burun_ucu, çene, sol_göz_dış, sağ_göz_dış, sol_ağız, sağ_ağız]
    # -------------------------------------------------------------------------
    _LANDMARK_IDS = [1, 152, 33, 263, 61, 291]

    def __init__(self, yaw_threshold: float = 25, pitch_threshold: float = 20,
                 max_faces: int = 1):
        """
        GazeAnalyzer sınıfını başlatır ve MediaPipe FaceLandmarker modelini yükler.

        Bu metot, bakış yönü analizinde kullanılacak eşik değerlerini ayarlar
        ve MediaPipe FaceLandmarker'ı belirtilen yapılandırma ile oluşturur.
        Model dosyası config.FACE_MODEL_PATH'ten yþklenir.

        Parametreler:
            yaw_threshold (float, varsayılan=25):
                Başın sola/sağa dönüş açısı için eşik değeri (derece cinsinden).
                Kullanıcının yaw açısının mutlak değeri bu eşik değerinden
                küçükse, yatay eksende ekrana baktığı kabul edilir.
                Örnek: yaw_threshold=25 ise, -25 ile +25 derece arasındaki
                yaw açıları "ekrana bakıyor" olarak değerlendirilir.
                Daha büyük değer -> daha geniş kabul aralığı (daha toleranslı).
                Daha küçük değer -> daha dar kabul aralığı (daha katı).

            pitch_threshold (float, varsayılan=20):
                Başın yukarı/aşağı eğme açısı için eşik değeri (derece cinsinden).
                Kullanıcının pitch açısının mutlak değeri bu eşik değerinden
                küçükse, dikey eksende ekrana baktığı kabul edilir.
                Örnek: pitch_threshold=20 ise, -20 ile +20 derece arasındaki
                pitch açıları "ekrana bakıyor" olarak değerlendirilir.
                Pitch eşiği genellikle yaw eşiğinden biraz daha küçüktür çünkü
                insanlar dikey eksende daha az hareket eder.

            max_faces (int, varsayılan=1):
                Aynı anda tespit edilecek maksimum yüz sayısı. Tek kullanıcı
                senaryolarında 1 yeterlidir. Birden fazla kullanıcıyı aynı
                anda izlemek için bu değer arttırılabilir. Daha yüksek değer
                daha fazla işlem gücü gerektirir.

        Başlatılan İç Değişkenler:
            self.yaw_threshold: Yaw eşik değeri (derece)
            self.pitch_threshold: Pitch eşik değeri (derece)
            self._start_time: Video zaman damgası hesabı için başlangıç zamanı
            self._landmarker: MediaPipe FaceLandmarker nesnesi

        Not:
            FaceLandmarker, RunningMode.VIDEO modunda oluşturulur. Bu mod,
            ardışık karelerin zamansal tutarlılığını koruyarak daha kararlı
            bir yüz takibi sağlar. Her kare için artan bir zaman damgası
            (timestamp_ms) gerektirir.
        """
        # Yatay (sola/sağa) bakış eşik değerini sakla
        self.yaw_threshold = yaw_threshold
        # Dikey (yukarı/aşağı) bakış eşik değerini sakla
        self.pitch_threshold = pitch_threshold
        # Video zaman damgası hesaplaması için başlangıç zamanını kaydet
        # time.monotonic() kullanılır çünkü sistem saatinden bağımsız,
        # sürekli artan bir saat sağlar
        self._start_time = time.monotonic()

        # MediaPipe FaceLandmarker yapılandırma seçeneklerini oluştur
        options = FaceLandmarkerOptions(
            # Önceden eğitilmiş yüz modeli dosyasının yolu
            base_options=BaseOptions(model_asset_path=config.FACE_MODEL_PATH),
            # VIDEO modu: ardışık kareler arasında zamansal tutarlılık sağlar
            running_mode=RunningMode.VIDEO,
            # Aynı anda tespit edilecek maksimum yüz sayısı
            num_faces=max_faces,
            # Yüz tespiti için minimum güven eşiği (0.0 - 1.0)
            # 0.6 = %60 güven gerekli, düşük değer daha fazla yanlış pozitif üretir
            min_face_detection_confidence=0.6,
            # Yüzün varlığını doğrulama için minimum güven eşiği
            # Tespit edilen bölgenin gerçekten bir yüz olduğunu onaylar
            min_face_presence_confidence=0.5,
            # Kareler arası yüz takibi için minimum güven eşiği
            # Düşük değer takip kaybına, yüksek değer gecikmeye neden olabilir
            min_tracking_confidence=0.5,
        )
        # Yapılandırma ile FaceLandmarker nesnesini oluştur ve hazır hale getir
        self._landmarker = FaceLandmarker.create_from_options(options)

    def analyze(self, frame_rgb: np.ndarray) -> GazeResult | None:
        """
        Tek bir RGB görüntü karesini analiz eder ve ilk tespit edilen yüz
        için bakış sonucu döner.

        Bu metot, analyze_all() metodunun bir kolaylık sarmalayıcısıdır (wrapper).
        Tek kullanıcı senaryolarında, birden fazla yüz işlemeye gerek olmadan
        doğrudan sonuç almak için kullanılır. Birden fazla yüz tespit edilmişse,
        yalnızca ilk yüzün sonucunu döner.

        Parametreler:
            frame_rgb (np.ndarray):
                RGB formatında görüntü karesi. Numpy dizisi olarak beklenir,
                şekli (yükseklik, genişlik, 3) olmalıdır.
                ÖNEMLİ: OpenCV varsayılan olarak BGR formatında okur, bu
                nedenle cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) ile dönüşüm
                yapılmalıdır.

        Dönüş Değeri:
            GazeResult | None:
                - GazeResult: Yüz tespit edildiyse, pitch, yaw, roll açıları
                  ve ekrana bakış durumunu içeren sonuç nesnesi.
                - None: Görüntüde hiçbir yüz tespit edilemediyse.

        Örnek:
            >>> result = analyzer.analyze(frame_rgb)
            >>> if result is not None:
            ...     print(f"Ekrana bakıyor: {result.looking_at_screen}")
        """
        # Tüm yüzleri analiz et ve sonuç listesini al
        results = self.analyze_all(frame_rgb)
        # Liste boş değilse ilk sonucu, boşsa None dön
        return results[0] if results else None

    def analyze_all(self, frame_rgb: np.ndarray) -> list[GazeResult]:
        """
        Bir RGB görüntü karesini analiz eder ve tespit edilen tüm yüzler
        için bakış sonuçlarını döner.

        Bu metot, modüldeki ana analiz işlev akışını içerir:
        1. Görüntü boyutlarını ve zaman damgasını hazırla
        2. MediaPipe ile yüz referans noktalarını tespit et
        3. Her yüz için kamera matrisi ile solvePnP uygula
        4. Rotasyon matrisinden Euler açıları hesapla
        5. Eşik değerleriyle karşılaştırarak ekrana bakış durumunu belirle

        Parametreler:
            frame_rgb (np.ndarray):
                RGB formatında görüntü karesi. Numpy dizisi olarak beklenir,
                şekli (yükseklik, genişlik, 3) olmalıdır.
                Piksel değerleri 0-255 arasında uint8 tipinde beklenir.

        Dönüş Değeri:
            list[GazeResult]:
                Tespit edilen her yüz için bir GazeResult nesnesi içeren liste.
                Hiçbir yüz tespit edilemediyse boş liste [] döner.
                Liste elemanları, MediaPipe'in tespit sırasına göredir.

        Teknik Detaylar:
            - Kamera matrisi yaklaşık olarak oluşturulur: odak uzaklığı olarak
              görüntü genişliği, optik merkez olarak görüntünün merkezi kullanılır.
              Bu yaklaşım çoğu web kamerası için yeterli doğrulukta sonuç verir.
            - Lens distorsiyon katsayıları sıfır kabul edilir (ideal kamera modeli).
            - solvePnP, ITERATIVE yöntemi ile çözülür; bu yöntem, küçük
              dönüş açıları için iyi yakınsaklık sağlar.

        Örnek:
            >>> results = analyzer.analyze_all(frame_rgb)
            >>> for i, r in enumerate(results):
            ...     durum = "bakıyor" if r.looking_at_screen else "bakmıyor"
            ...     print(f"Yüz {i}: {durum} (yaw={r.yaw}, pitch={r.pitch})")
        """
        # Görüntü boyutlarını al: h=yükseklik (satır), w=genişlik (sütun)
        h, w = frame_rgb.shape[:2]

        # MediaPipe VIDEO modunda her kare için artan bir zaman damgası gerektirir.
        # Başlangıç zamanından itibaren geçen süreyi milisaniye cinsinden hesapla
        timestamp_ms = int((time.monotonic() - self._start_time) * 1000)

        # Numpy dizisini MediaPipe'in Image formatına dönüştür
        # SRGB renk uzayı belirtilir (standart RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        # MediaPipe FaceLandmarker ile yüz referans noktalarını tespit et
        # detect_for_video, VIDEO modunda kullanılır ve zaman damgası gerektirir
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        # Hiçbir yüz tespit edilemediyse boş liste dön
        if not result.face_landmarks:
            return []

        # =====================================================================
        # Yaklaşık kamera iç parametre (intrinsic) matrisi oluştur.
        # Gerçek kamera kalibrasyonu yapılmadığı için, makul varsayımlar
        # kullanılır:
        # - Odak uzaklığı (focal length): Görüntünün piksel cinsinden genişliği
        #   kullanılır. Çoğu web kamerası için bu iyi bir yaklaşımdır.
        # - Optik merkez (principal point): Görüntünün tam merkezi kabul edilir.
        #
        # Kamera matrisi formati:
        #   | fx  0   cx |
        #   | 0   fy  cy |
        #   | 0   0   1  |
        # Burada fx=fy=focal_length, cx=w/2, cy=h/2
        # =====================================================================
        focal_length = float(w)
        center = (w / 2.0, h / 2.0)
        camera_matrix = np.array(
            [[focal_length, 0, center[0]],
             [0, focal_length, center[1]],
             [0, 0, 1]],
            dtype=np.float64,
        )
        # Lens distorsiyon katsayıları: sıfır vektörü (ideal kamera, bozulma yok)
        # 4 elemanlı vektör: [k1, k2, p1, p2] (radyal ve tanjansiyel distorsiyon)
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        # Tespit edilen her yüz için sonuçları toplayacak liste
        results = []
        for face in result.face_landmarks:
            # =================================================================
            # 2D görüntü noktalarını hesapla.
            # MediaPipe, landmark koordinatlarını 0.0 - 1.0 arasında normalize
            # edilmiş olarak döner. solvePnP piksel cinsinden koordinat
            # beklediğinden, normalize değerleri görüntü boyutlarıyla çarparız.
            # face[i].x * w = piksel cinsinden x koordinatı
            # face[i].y * h = piksel cinsinden y koordinatı
            # =================================================================
            image_points = np.array(
                [(face[i].x * w, face[i].y * h) for i in self._LANDMARK_IDS],
                dtype=np.float64,
            )

            # =================================================================
            # solvePnP: 3D model noktaları ile 2D görüntü noktaları arasındaki
            # geometrik ilişkiyi çözerek kameranın yüz modeline göre pozisyonunu
            # (rotasyon ve öteleme) hesaplar.
            #
            # Girişler:
            #   - _MODEL_POINTS: 3D referans yüz modeli noktaları
            #   - image_points: 2D görüntüdeki karşılık gelen piksel konumları
            #   - camera_matrix: Kamera iç parametre matrisi
            #   - dist_coeffs: Lens distorsiyon katsayıları
            #
            # Çıkışlar:
            #   - success: Çözüm başarılı mı? (bool)
            #   - rvec: 3x1 rotasyon vektörü (Rodrigues formatı)
            #   - tvec: 3x1 öteleme vektörü (kullanılmıyor)
            #
            # SOLVEPNP_ITERATIVE: Levenberg-Marquardt optimizasyonu ile
            # iteratif çözüm yöntemi. Küçük açılar için iyi yakınsaklık sağlar.
            # =================================================================
            success, rvec, tvec = cv2.solvePnP(
                self._MODEL_POINTS, image_points, camera_matrix, dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
            # solvePnP başarısız olduysa bu yüzü atla ve sonrakine geç
            if not success:
                continue

            # Rodrigues dönüşümü: 3x1 rotasyon vektörünü 3x3 rotasyon matrisine çevir.
            # Rotasyon matrisi, 3D uzayda yüzün kameraya göre yönelimini temsil eder.
            # Jacobian matrisi (_) kullanılmıyor, bu nedenle göz ardı ediliyor.
            rmat, _ = cv2.Rodrigues(rvec)

            # Rotasyon matrisinden Euler açıları (pitch, yaw, roll) hesapla
            # Dönen değerler derece cinsindendir
            pitch, yaw, roll = self._rotation_to_euler(rmat)

            # =================================================================
            # solvePnP, yüz doğrudan kameraya bakarken yaklaşık 180 derece
            # civarında bir pitch offset'i üretebilir. Bunun nedeni, 3D model
            # ile kamera koordinat sistemi arasındaki yön farkından kaynaklanır.
            # Bu durumu düzeltmek için 90 derecenin üzerindeki veya altındaki
            # pitch değerlerini normalize ediyoruz:
            # - pitch > 90  -> pitch -= 180 (örneğin 170 -> -10)
            # - pitch < -90 -> pitch += 180 (örneğin -170 -> 10)
            # Böylece pitch değeri -90 ile +90 arasında kalır.
            # =================================================================
            if pitch > 90:
                pitch -= 180
            elif pitch < -90:
                pitch += 180

            # Ekrana bakış kontrolü: hem yaw hem pitch eşik değerlerinin altında mı?
            # abs() ile mutlak değer alınır çünkü yön (sağ/sol, yukarı/aşağı) önemli değil,
            # yalnızca sapma miktarı önemlidir
            looking = abs(yaw) < self.yaw_threshold and abs(pitch) < self.pitch_threshold

            # Burun ucu konumunu al (landmark indeks 1).
            # Bu konum, birden fazla yüz tespit edildiğnde yüzlerin kareler
            # arasında eşleştirilmesi (tracking/matching) için kullanılır.
            # Normalize koordinatlar (0.0 - 1.0) doğrudan saklanır.
            nose = face[1]  # landmark 1 = burun ucu

            # Analiz sonucunu GazeResult nesnesi olarak oluştur ve listeye ekle
            # Açılar round() ile 1 ondalık basamağa yuvarlanır (görsel temizlik)
            results.append(GazeResult(
                pitch=round(pitch, 1),
                yaw=round(yaw, 1),
                roll=round(roll, 1),
                looking_at_screen=looking,
                face_landmarks=face,
                nose_pos=(nose.x, nose.y),
            ))

        return results

    def draw_landmarks(self, frame: np.ndarray, face_landmarks: list,
                       color: tuple = (0, 200, 200)) -> np.ndarray:
        """
        Tespit edilen yüz referans noktalarının dış hatlarını (contour)
        verilen görüntü karesi üzerine çizer.

        Bu metot, MediaPipe'in çizim yardımcı fonksiyonlarını kullanarak
        yüz çevresinin dış hatlarını (alın, yanaklar, çene hattı, göz
        çevresi vb.) çizgilerle görselleştirmesini sağlar. Yalnızca
        FACE_LANDMARKS_CONTOURS bağlantı seti kullanılır; bu set, yüzün
        dış sınırları ve önemli bölge kenarlıkları için tanımlanmış
        çizgileri içerir.

        Parametreler:
            frame (np.ndarray):
                Üzerine çizim yapılacak görüntü karesi. BGR formatında
                olmalıdır (OpenCV standardı). Çizim doğrudan bu dizinin
                üzerine yapılır (in-place).

            face_landmarks (list):
                MediaPipe tarafından tespit edilen yüz referans noktaları
                listesi. Genellikle GazeResult.face_landmarks alanından
                alınır. Her bir eleman, normalize edilmiş x, y, z
                koordinatlarına sahip bir NormalizedLandmark nesnesidir.

            color (tuple, varsayılan=(0, 200, 200)):
                Çizgi rengi, BGR (Mavi, Yeşil, Kırmızı) formatında.
                Varsayılan renk açık sarıdır (BGR: 0, 200, 200).
                Örnek: (255, 0, 0) = mavi, (0, 255, 0) = yeşil,
                       (0, 0, 255) = kırmızı.

        Dönüş Değeri:
            np.ndarray:
                Üzerine yüz hatları çizilmiş görüntü karesi. Not: çizim
                doğrudan giriş dizisi üzerine yapıldığı için (in-place),
                dönen referans aynı diziyi işaret eder.

        Örnek:
            >>> result = analyzer.analyze(frame_rgb)
            >>> if result is not None:
            ...     frame_bgr = analyzer.draw_landmarks(frame_bgr, result.face_landmarks)
            ...     cv2.imshow("Yüz Hatları", frame_bgr)
        """
        # MediaPipe çizim yardımcısı ile yüz hatlarını çiz
        drawing_utils.draw_landmarks(
            image=frame,                   # Çizim yapılacak görüntü
            landmark_list=face_landmarks,  # Yüz referans noktaları
            # CONTOURS bağlantı seti: yüzün dış hatlarını tanımlayan çizgiler
            connections=FaceLandmarksConnections.FACE_LANDMARKS_CONTOURS,
            # Nokta çizimi devre dışı (None) - yalnızca çizgiler gösterilsin
            landmark_drawing_spec=None,
            # Bağlantı çizgisi özellikleri: renk, kalınlık, daire yarıçapı
            # circle_radius=0 ile bağlantı noktalarında daire çizilmez
            connection_drawing_spec=DrawingSpec(color=color, thickness=1, circle_radius=0),
        )
        return frame

    def close(self):
        """
        MediaPipe FaceLandmarker kaynaklarını serbest bırakır.

        Bu metot, analizör ile işlem tamamlandığnda çağrılmalıdır.
        FaceLandmarker dahili olarak GPU/CPU kaynakları ve bellek
        tahsisi kullanır; bu kaynakların düzenli şekilde serbest
        bırakılması bellek sızıntısını önler.
        """
        # FaceLandmarker nesnesinin dahili kaynaklarını serbest bırak
        self._landmarker.close()

    @staticmethod
    def _rotation_to_euler(rmat: np.ndarray) -> tuple[float, float, float]:
        """
        3x3 rotasyon matrisini Euler açılarına (pitch, yaw, roll) dönüştürür.
        Sonuçlar derece cinsinden döndürülür.

        Matematiksel Açıklama:
            Bir 3x3 rotasyon matrisi R, üç ardışık rotasyonun bileşimi olarak
            ifade edilebilir (Tait-Bryan açıları, XYZ sırası):

            R = Rz(roll) * Ry(yaw) * Rx(pitch)

            Bu carpim acildiginda:
            R = | r00  r01  r02 |
                | r10  r11  r12 |
                | r20  r21  r22 |

            Buradan Euler açıları şu şekilde elde edilir:

            1. sy = sqrt(r00^2 + r10^2)
               Bu değer, yaw açısının kosinüsünün mutlak değeriyle orantılıdır.
               sy'nin sıfıra yakın olması "Gimbal Lock" durumunu gösterir.

            2. Gimbal Lock kontrolü (sy < 1e-6):
               Gimbal Lock, yaw açısı +/-90 dereceye yaklaştığında oluşan
               bir tekillik durumudur. Bu durumda pitch ve roll birbirinden
               ayırt edilemez hale gelir.

            3. Normal durum (Gimbal Lock yok):
               - pitch = atan2(r21, r22)
                 Açıklama: r21 = cos(yaw)*sin(pitch), r22 = cos(yaw)*cos(pitch)
                 atan2 ile bölüm yapmadan açıyı hesaplarız.

               - yaw = atan2(-r20, sy)
                 Açıklama: r20 = -sin(yaw), sy = cos(yaw)
                 İşaret düzeltmesi için -r20 kullanılır.

               - roll = atan2(r10, r00)
                 Açıklama: r10 = cos(yaw)*sin(roll), r00 = cos(yaw)*cos(roll)

            4. Tekil durum (Gimbal Lock):
               - pitch = atan2(-r12, r11)
                 Alternatif hesaplama yolu, çünkü r21 ve r22 güvenilir değil.
               - yaw = atan2(-r20, sy) (aynı formül)
               - roll = 0.0 (belirlenemez, sıfır kabul edilir)

            Not: atan2(y, x) fonksiyonu, y/x bölümünün ark tanjantını hesaplar
            ancak işaretleri doğru şekilde ele alarak -pi ile +pi arasında
            sonuç döner. Bu, atan(y/x)'e göre daha güvenilirdir çünkü sıfıra
            bölme hatası oluşturmaz ve tüm kadranları doğru işler.

        Parametreler:
            rmat (np.ndarray):
                3x3 boyutunda rotasyon matrisi. cv2.Rodrigues() fonksiyonunun
                çıktısı olarak elde edilir. Matrisin ortonormal olması beklenir
                (R * R^T = I, det(R) = 1).

        Dönüş Değeri:
            tuple[float, float, float]:
                (pitch, yaw, roll) şeklinde Euler açıları, derece cinsinden.
                - pitch: X ekseni etrafında dönüş (-180 ile +180 derece arası)
                - yaw: Y ekseni etrafında dönüş (-90 ile +90 derece arası)
                - roll: Z ekseni etrafında dönüş (-180 ile +180 derece arası)
        """
        # Gimbal Lock kontrolü için sy değerini hesapla.
        # sy, rotasyon matrisinin ilk sütununun ilk iki elemanının Öklid normudur.
        # Bu değer cos(yaw)'a karşılık gelir ve sıfıra yakın olması
        # yaw'ın +/-90 derece olduğunu (Gimbal Lock) gösterir.
        sy = math.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)

        # Tekil (Gimbal Lock) durumu kontrolü: sy çok küçükse (< 1e-6)
        # cos(yaw) ~ 0 demektir, yani yaw ~ +/-90 derece
        singular = sy < 1e-6

        if not singular:
            # Normal durum: Gimbal Lock yok, üç açı bağımsız olarak hesaplanabilir

            # Pitch (X ekseni etrafında dönüş): atan2(r21, r22)
            pitch = math.atan2(rmat[2, 1], rmat[2, 2])
            # Yaw (Y ekseni etrafında dönüş): atan2(-r20, sy)
            yaw = math.atan2(-rmat[2, 0], sy)
            # Roll (Z ekseni etrafında dönüş): atan2(r10, r00)
            roll = math.atan2(rmat[1, 0], rmat[0, 0])
        else:
            # Tekil durum (Gimbal Lock): yaw ~= +/-90 derece
            # Pitch ve roll birbirinden ayırt edilemez, alternatif formül kullan

            # Pitch için alternatif hesaplama: atan2(-r12, r11)
            pitch = math.atan2(-rmat[1, 2], rmat[1, 1])
            # Yaw aynı formül ile hesaplanır
            yaw = math.atan2(-rmat[2, 0], sy)
            # Roll belirlenemez, geleneksel olarak sıfır kabul edilir
            roll = 0.0

        # Radyandan dereceye çevir ve (pitch, yaw, roll) olarak dön
        return math.degrees(pitch), math.degrees(yaw), math.degrees(roll)
