"""
================================================================================
                    OFFICEGUARDIAN - KAMERA YONETIMI VE COKLU KISI TAKIBI
================================================================================

Bu dosya, kamera erisimi, goruntu okuma ve birden fazla kisiyi
ayni anda takip etme sisteminin nasil calistigini aciklar.

================================================================================
BOLUM 1: KAMERA YONETIMI (CameraManager)
================================================================================

CameraManager sinifi, kameraya erisimi yoneten bir sarmalayicidir (wrapper).

DESTEKLENEN KAMERA TURLERI:
  1. Dahili webcam (laptop kamerasi)
  2. USB webcam (harici kamera)
  3. Sanal kameralar (DroidCam, EpocCam vb.)

KAMERA ACMA STRATEJISI:
  Windows'ta kamera acmak icin iki yontem vardir:

  1. DirectShow (DSHOW): Windows'un yerel video yakalama API'si
     - En kararli ve en hizli yontemdir
     - Cogu USB webcam ve dahili kamera ile calisir
     - Ilk denemede bu yontem kullanilir

  2. Dogrudan acma (DSHOW olmadan):
     - Bazi sanal kameralar (DroidCam) DirectShow'u desteklemez
     - Bu durumda ikinci yontem olarak denenir

  Kod akisi:
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)  # 1. deneme
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)               # 2. deneme

THREAD GUVENLIGI:
  Kamera islemleri threading.Lock ile korunur.
  Bu, birden fazla thread'in ayni anda kameraya erisimini onler.
  Neden gerekli?
    - Ana thread goruntuyu okurken baska bir thread kamerayi kapatabilir
    - Bu durum program cokusuene neden olabilir
    - Lock, ayni anda sadece bir thread'in kameraya erisimini garanti eder

KAMERA AYARLARI:
  - CAMERA_INDEX = 0     # Varsayilan kamera (0 = ilk kamera)
  - FRAME_WIDTH = 640    # Goruntu genisligi (piksel)
  - FRAME_HEIGHT = 480   # Goruntu yuksekligi (piksel)
  - BUFFERSIZE = 1       # En guncel frame'i al (gecikmeyi azaltir)

KULLANIM:
  kamera = CameraManager(index=0, width=640, height=480)
  if kamera.open():
      basarili, frame = kamera.read()  # BGR formatinda numpy dizisi
      if basarili:
          # frame ile islem yap...
      kamera.release()  # Kamerayi kapat

KAMERA LISTELEME:
  CameraManager.list_cameras(max_check=5)
  # 0'dan 4'e kadar tum kamera indekslerini dener
  # Her birini acmaya calisir, acilanlarin bilgilerini doner
  # Donus: [{"index": 0, "name": "Kamera 0", "resolution": "640x480"}, ...]

DOSYA KONUMU: core/camera.py

================================================================================
BOLUM 2: COKLU KISI TAKIBI (PersonTracker)
================================================================================

PersonTracker, ofis ortaminda bir kameradan birden fazla kisiyi
ayni anda takip eden sistemdir.

NEDEN GEREKLI?
  - Ofis modunda bir kamera birden fazla kisiyi gorebiir
  - PoseLandmarker birden fazla vucut tespit edebilir
  - FaceLandmarker birden fazla yuz tespit edebilir
  - Ama "hangi vucut hangi yuz?" sorusunu cevaplamak lazim
  - Ayrica "bu karenin kisisi onceki kareniinn aynisi mi?" sorusu da var

ESLESTIRME ALGORITMASI (Greedy Nearest-Neighbor):
=================================================

Frame 1'de 3 kisi tespit edildi: Kisi_A, Kisi_B, Kisi_C
Frame 2'de 3 vucut tespit edildi: Vucut_1, Vucut_2, Vucut_3
Soru: Vucut_1 hangi kisiye ait? Vucut_2? Vucut_3?

ADIM 1: MESAFE MATRISI OLUSTUR
  Her (kisi, vucut) cifti arasindaki Oklid mesafesini hesapla.
  Mesafe, centroid (agirlik merkezi) noktalarinin uzakligina gore.

  Ornek matris:
               Vucut_1   Vucut_2   Vucut_3
  Kisi_A       0.05      0.30      0.45
  Kisi_B       0.25      0.08      0.35
  Kisi_C       0.40      0.32      0.06

ADIM 2: MESAFEYE GORE SIRALA
  (0.05, A, 1), (0.06, C, 3), (0.08, B, 2), (0.25, B, 1), ...

ADIM 3: ACGOZLU ESLESTIRME
  En kucuk mesafeden basla:
  1. (0.05, A, 1): A <-> Vucut_1 ✓ (mesafe < esik 0.15)
  2. (0.06, C, 3): C <-> Vucut_3 ✓
  3. (0.08, B, 2): B <-> Vucut_2 ✓

  Sonuc: A=Vucut_1, B=Vucut_2, C=Vucut_3

ADIM 4: ESLESMEYEN VUCUT = YENI KISI
  Eger bir vucut hicbir mevcut kisiyle eslesmezse,
  yeni bir kisi olarak kaydedilir (yeni ID ve renk atanir).
  Maksimum 6 kisi siniri vardir.

GAZE-POSE ESLESTIRME:
======================
Pose (vucut) ve Gaze (yuz) analizi FARKLI modeller tarafindan yapilir.
Ayni kisiyi birbirine baglamak icin BURUN KONUMU kullanilir:
  - PoseResult.nose_pos = vucut analizinden burun konumu
  - GazeResult.nose_pos = yuz analizinden burun konumu
  - Iki burun konumu birbirine yakin olan sonuclar AYNI KISIYE aittir

PERSONSTATE VERI YAPISI:
========================
Her takip edilen kisi icin bir PersonState nesnesi tutulur:

  PersonState:
    person_id   : int    # Benzersiz kimlik (1, 2, 3, ...)
    color_bgr   : tuple  # BGR renk (OpenCV cizim icin)
    color_hex   : str    # HEX renk (web arayuzu icin)
    label       : str    # Etiket ("Kisi 1", "Kisi 2", ...)

    posture     : PostureResult  # Bu karenin postur sonucu
    gaze        : GazeResult     # Bu karenin bakis sonucu
    is_working  : bool           # Calisiyor mu?
    centroid    : tuple          # Agirlik merkezi (x, y)

    work_seconds         : float  # Toplam calisma suresi
    break_seconds        : float  # Toplam mola suresi
    good_posture_seconds : float  # Iyi posturde gecen sure
    bad_posture_seconds  : float  # Kotu posturde gecen sure

KAYIP KISI TEMIZLEME:
=====================
Bir kisi kameradan kaybolursa (ornegin masasindan kalktiysa):
  - son_gorunme_zamani kaydedilir
  - 5 saniye (disappear_timeout) boyunca tekrar gorulmezse silinir
  - Bu, sahneden ayrilan kisilerin bellekte birikmesini onler

ISTATISTIK TAKIBI:
==================
Her frame'de delta (gecen sure) hesaplanir ve ilgili sayaca eklenir:
  - delta = su_an - son_guncelleme (max 2 saniye siniri)
  - is_working=True ise -> work_seconds += delta
  - is_working=False ise -> break_seconds += delta
  - is_good_posture=True ise -> good_posture_seconds += delta
  - is_good_posture=False ise -> bad_posture_seconds += delta

Max 2 saniye siniri, uygulama donmasi durumunda istatistiklerin
anormal sismesini onler.

DOSYA KONUMU: core/person_tracker.py

================================================================================
BOLUM 3: OTURUM TAKIBI (SessionTracker)
================================================================================

SessionTracker, kisisel modda istatistikleri JSON dosyalarina kaydeder.

CALISMA PRENSIBI:
  1. Her frame'de tick() metodu cagrilir
  2. tick(), onceki frame'den bu yana gecen sureyi hesaplar
  3. Gecen sureyi calisma/mola ve iyi/kotu postur sayaclarina ekler
  4. Veriler gunluk JSON dosyasina kaydedilir

JSON DOSYA FORMATI:
  data/session_2026-02-17.json
  {
    "date": "2026-02-17",
    "work_seconds": 3600.5,
    "break_seconds": 450.2,
    "good_posture_seconds": 3200.0,
    "bad_posture_seconds": 850.7
  }

GUN DEGISIMI:
  Gece yarisi gecildiginde (tarih degisince):
  1. Mevcut istatistikler kaydedilir
  2. Yeni gun icin sifir istatistik dosyasi olusturulur

DOSYA KONUMU: core/session_tracker.py

================================================================================
BOLUM 4: OLAY KAYITCISI (EventLogger)
================================================================================

EventLogger, tum onemli olaylari JSONL (JSON Lines) formatinda kaydeder.

JSONL FORMATI:
  Her satir bagimsiz bir JSON nesnesidir. Ornek:
  {"ts": "2026-02-17 14:30:00", "epoch": 1771067400.0, "person": "self",
   "event": "posture_change", "details": {"posture": "bad"}}
  {"ts": "2026-02-17 14:30:05", "epoch": 1771067405.0, "person": "self",
   "event": "work_status_change", "details": {"status": "break"}}

NEDEN JSONL?
  - Her satir bagimsiz okunabilir (buyuk dosyalarda verimli)
  - Dosya sonu ekleme yapilabilir (append mode)
  - Ani kapatmalarda sadece son satir kaybolur (tampon bosaltma flush)

KAYIT EDILEN OLAYLAR:
  - posture_change     : Postur iyi -> kotu veya kotu -> iyi degisti
  - work_status_change : Calisiyor -> mola veya mola -> calisiyor degisti
  - person_enter       : Yeni kisi sahnede goruldu (ofis modu)
  - person_exit        : Kisi sahneden ayrildi (ofis modu)
  - warning            : Uyari tetiklendi
  - session_start      : Oturum baslatildi
  - session_stop       : Oturum durduruldu

DOSYA KONUMU: core/event_logger.py
LOG DOSYALARI: logs/log_2026-02-17.jsonl

================================================================================
"""
