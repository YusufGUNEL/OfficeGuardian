"""
================================================================================
                    OFFICEGUARDIAN - BAKIS YONU ANALIZI
================================================================================

Bu dosya, calisanin EKRANA BAKIP BAKMADIGINI tespit eden bakis yonu
analiz sisteminin nasil calistigini detayli olarak aciklar.

Bakis yonu analizi, kameradan alinan goruntude yuz tespit ederek
basin hangi yone donuk oldugunu hesaplar. Boylece calisanin
calisip calismadigini (ekrana bakip bakmadigini) belirler.

================================================================================
GENEL BAKIS
================================================================================

Bakis analizi su adimlardan olusur:

1. MEDIAPIPE FACELANDMARKER ILE YUZ NOKTASI TESPITI
   - Yuz uzerinde 468 adet 3D referans noktasi tespit edilir
   - Bu noktalar burun, goz, agiz, cene gibi anatomik bolgelere karsilik gelir

2. 6 ANAHTAR NOKTA SECIMI (solvePnP icin)
   - Burun ucu (landmark 1)
   - Cene (landmark 152)
   - Sol goz dis kose (landmark 33)
   - Sag goz dis kose (landmark 263)
   - Sol agiz kosesi (landmark 61)
   - Sag agiz kosesi (landmark 291)

3. SOLVEPNP ILE 3D POZ TAHMINI
   - Bilinen 3D yuz modeli noktalari ile 2D goruntu noktalari eslestirilir
   - Kameranin yuz modeline gore rotasyon ve oteleme hesaplanir

4. EULER ACILARI HESAPLAMA
   - Rotasyon matrisinden Pitch, Yaw, Roll acilari elde edilir
   - Pitch: yukari/asagi egme
   - Yaw: sola/saga donus
   - Roll: yana yatma

5. EKRANA BAKIS KARARI
   - |yaw| < 25 derece VE |pitch| < 20 derece ise: EKRANA BAKIYOR
   - Aksi halde: BASKA YERE BAKIYOR (mola)

================================================================================
MEDIAPIPE FACELANDMARKER NEDIR?
================================================================================

FaceLandmarker, MediaPipe'in yuz analiz modelidir.

Ozellikleri:
  - Bir goruntude yuz tespit eder
  - Yuz uzerinde 468 referans noktasi belirler
  - Her noktanin normalize x, y, z koordinatlari vardir
  - 3D bilgi icerir (derinlik tahmini yapar)

Model Dosyasi:
  models/face_landmarker.task

468 noktanin hepsi kullanilmaz. Bakis yonu icin sadece 6 tanesi
solvePnP'ye verilir. Geri kalanlari yuz cizimi icin kullanilabilir.

================================================================================
SOLVEPNP NEDIR? (Perspektif n-Nokta Problemi)
================================================================================

solvePnP, bilgisayarli gorude temel bir problemdir:

PROBLEM: 3 boyutlu uzaydaki bilinen noktalarin, 2 boyutlu goruntuye
nasil yansidigi bilindigi zaman, kameranin 3D uzaydaki konumunu
(rotasyon ve oteleme) hesaplamak.

BASIT ANLATIM:
  - Elimizde bir yuz modeli var (3D noktalar)
  - Kamerada bu noktalarni goruyoruz (2D pikseller)
  - solvePnP, "kamera yuze gore nasil duruyor?" sorusunu cevaplar
  - Ama biz tersini istiyoruz: "yuz kameraya gore nasil duruyor?"
  - Sonuc ayni: rotasyon matrisi bize yuzu naci yonelimini verir

GIRISLER:
  1. 3D Model Noktalari (6 adet):
     Standart bir yuz modelinin 3D koordinatlari.
     Bunlar SABIT degerlerdir, her yuz icin ayni kullanilir.

     Burun ucu:        (0, 0, 0)        - referans noktasi (orijin)
     Cene:             (0, -330, -65)    - burun altinda ve geride
     Sol goz dis kose: (-225, 170, -135) - solda, yukarda ve geride
     Sag goz dis kose: (225, 170, -135)  - sagda, yukarda ve geride
     Sol agiz kosesi:  (-150, -150, -125)
     Sag agiz kosesi:  (150, -150, -125)

  2. 2D Goruntu Noktalari (6 adet):
     MediaPipe'in tespit ettigi yuz noktalarinin piksel koordinatlari.
     Her frame'de farkli olur (kisi hareket eder).

     piksel_x = landmark.x * goruntu_genisligi
     piksel_y = landmark.y * goruntu_yuksekligi

  3. Kamera Matrisi (3x3):
     Kameranin ic parametreleri (focal length, optik merkez).
     Gercek kalibrasyon yapilmadigi icin yaklasik degerler kullanilir:

     | fx  0   cx |     fx = fy = goruntu_genisligi (piksel)
     | 0   fy  cy |     cx = goruntu_genisligi / 2
     | 0   0   1  |     cy = goruntu_yuksekligi / 2

  4. Distorsiyon Katsayilari:
     Lens bozulmasini duzelten katsayilar.
     Sifir kabul edilir (ideal kamera modeli).

CIKISLAR:
  - rvec: Rotasyon vektoru (3x1, Rodrigues formati)
  - tvec: Oteleme vektoru (3x1, kullanilmiyor)

================================================================================
RODRIGUES DONUSUMU VE EULER ACILARI
================================================================================

solvePnP, rotasyonu "Rodrigues vektoru" olarak verir.
Bunu anlamli acilara cevirmek icin:

ADIM 1: Rodrigues -> Rotasyon Matrisi
  rmat, _ = cv2.Rodrigues(rvec)
  # 3x1 vektor -> 3x3 rotasyon matrisi

ADIM 2: Rotasyon Matrisi -> Euler Acilari
  Rotasyon matrisi R:
  | r00  r01  r02 |
  | r10  r11  r12 |
  | r20  r21  r22 |

  Buradan 3 aci cikarilir:

  sy = sqrt(r00^2 + r10^2)    # cos(yaw)'a karsilik gelir

  Eger sy > 0 (normal durum):
    pitch = atan2(r21, r22)
    yaw   = atan2(-r20, sy)
    roll  = atan2(r10, r00)

  Eger sy ~ 0 (Gimbal Lock - yaw ~= 90 derece):
    pitch = atan2(-r12, r11)
    yaw   = atan2(-r20, sy)
    roll  = 0

EULER ACILARI NEDIR?
  - PITCH (X ekseni): Basin yukari-asagi egmesi
    * pitch > 0: bas asagi egik (telefona bakiyor)
    * pitch < 0: bas yukari kalkik (tavana bakiyor)
    * pitch = 0: duz bakiyor

  - YAW (Y ekseni): Basin sola-saga donusu
    * yaw > 0: bas saga donuk
    * yaw < 0: bas sola donuk
    * yaw = 0: duz bakiyor

  - ROLL (Z ekseni): Basin yana yatmasi
    * roll > 0: saat yonunde yatik
    * roll < 0: saat yonunun tersine yatik
    * roll = 0: duz

PITCH DUZELTMESI:
  solvePnP bazen ~180 derece offset uretir.
  Duzeltme:
    if pitch > 90:  pitch -= 180
    if pitch < -90: pitch += 180
  Boylece pitch -90 ile +90 arasinda kalir.

================================================================================
EKRANA BAKIS KARARI
================================================================================

Hesaplanan yaw ve pitch acilari esik degerleriyle karsilastirilir:

  ekrana_bakiyor = |yaw| < yaw_esik VE |pitch| < pitch_esik

  Varsayilan esikler:
    yaw_esik   = 25 derece (sola/saga toplam 50 derecelik alan)
    pitch_esik = 20 derece (yukari/asagi toplam 40 derecelik alan)

  Mutlak deger (abs) kullanilir cunku:
    - Sola bakma (-yaw) ve saga bakma (+yaw) ayni sekilde degerlendirilir
    - Yukari bakma (-pitch) ve asagi bakma (+pitch) ayni sekilde degerlendirilir

  Ornek:
    yaw=5, pitch=3 -> ekrana bakiyor (ikisi de esik altinda)
    yaw=30, pitch=5 -> ekrana bakmiyor (yaw esigi asiyor)
    yaw=10, pitch=-25 -> ekrana bakmiyor (pitch esigi asiyor)

================================================================================
GAZERESULT VERI YAPISI
================================================================================

Her analiz sonucu bir GazeResult nesnesi olarak doner:

  GazeResult:
    pitch            : float  # Yukari/asagi egme acisi (derece)
    yaw              : float  # Sola/saga donus acisi (derece)
    roll             : float  # Yana yatma acisi (derece)
    looking_at_screen: bool   # Ekrana bakiyor mu? True/False
    face_landmarks   : list   # 468 yuz noktasi (yuz cizimi icin)
    nose_pos         : tuple  # Burun konumu (x, y) - eslestirme icin

================================================================================
GAZEANALYZER SINIFI KULLANIMI
================================================================================

Olusturma:
  analyzer = GazeAnalyzer(
      yaw_threshold=25,    # Yatay bakis esigi
      pitch_threshold=20,  # Dikey bakis esigi
      max_faces=1,         # Kac yuz tespit edilsin
  )

Analiz:
  # Tek yuz icin:
  sonuc = analyzer.analyze(frame_rgb)
  if sonuc and sonuc.looking_at_screen:
      print("Calisiyor")

  # Coklu yuz icin:
  sonuclar = analyzer.analyze_all(frame_rgb)

Yuz Cizimi:
  analyzer.draw_landmarks(frame, sonuc.face_landmarks, color=(0, 200, 200))

Kapatma:
  analyzer.close()

================================================================================
CALISMA DURUMU TESPITI VE GECIKME (HYSTERESIS)
================================================================================

Bakis analizi tek basina "calisiyor/calismiyor" kararini vermez.
Gecikme mekanizmasi uygulanir:

1. Kisi ekrana bakiyor -> hemen "calisiyor" olarak isaretlenir
2. Kisi ekrandan bakisini cevirdi -> HEMEN "mola" DEMEZ!
3. Belirli bir sure bekler (GAZE_STATUS_DELAY = 10 saniye)
4. 10 saniye boyunca hala ekrana bakmiyorsa -> "mola" olarak isaretlenir

NEDEN GECIKME?
  - Insan dogal olarak bazen etrafa bakar (mesela kapi acildi)
  - Klavyeye bakarak yazmak da "calismak"tir ama yuz ekrana donuk degil
  - Anlik bakis kaymalari mola olarak sayilmamali
  - 10 saniyelik gecikme bu yalanli alarmlari onler

Bu gecikme mekanizmasi person_tracker.py'deki
_compute_work_status() metodunda uygulanir.

================================================================================
DOSYA KONUMU
================================================================================

core/gaze_analyzer.py

================================================================================
"""
