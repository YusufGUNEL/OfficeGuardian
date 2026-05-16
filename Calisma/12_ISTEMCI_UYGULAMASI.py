"""
================================================================================
                    OFFICEGUARDIAN - MASAUSTU ISTEMCI UYGULAMASI
================================================================================

Bu dosya, calisanin bilgisayarinda calisan masaustu istemci uygulamasinin
(client/employee_client.py) nasil calistigini detayli olarak aciklar.

Bu uygulama projenin EN BUYUK ve EN KARMASIK dosyasidir (657 satir).
Kamera, AI analiz, WebSocket, kalibrasyon, yuz tanima ve GUI islemlerini
tek bir dosyada birlestirerek calisanin bilgisayarinda calisan
bagimsiz bir program olarak gorev yapar.

================================================================================
BOLUM 1: GENEL YAPI
================================================================================

Program TEK bir sinif uzerinde caliser: EmployeeClient

Dosya: client/employee_client.py

KULLANIM:
  Kisisel mod (tek kisi, tek kamera):
    python client/employee_client.py --server 192.168.1.20:8000 --room ABC123 --user AhmetYilmaz

  Ofis modu (coklu kisi, tek kamera):
    python client/employee_client.py --server 192.168.1.20:8000 --room ABC123 --user kamera1 --mode office

  Zorla kalibrasyon:
    python client/employee_client.py --server ... --room ... --user ... --calibrate

KOMUT SATIRI ARGUANLARI:
  --server     : Sunucu adresi (IP:port veya hostname:port)
  --room       : Oda kodu (6 haneli, orn: ABC123)
  --user       : Kullanici adi
  --mode       : 'personal' (varsayilan) veya 'office'
  --camera     : Kamera indeksi (varsayilan: 0)
  --calibrate  : Kalibrasyon modunda baslat (gecmis veriyi yoksay)

================================================================================
BOLUM 2: EMPLOYEECLIENT SINIFI (__init__)
================================================================================

Sinifin __init__ metodu tum alt sistemleri hazirlar:

PARAMETRELER:
  server       -> Sunucu adresi
  room_code    -> Oda kodu
  username     -> Kullanici adi
  mode         -> 'personal' veya 'office'
  camera_index -> Kamera indeksi (varsayilan 0)

DURUM DEGISKENLERI:
  running                -> Program calisiyor mu? (True/False)
  ws                     -> WebSocket baglanti nesnesi
  warnings               -> Gelen uyarilarin listesi
  warning_display_until  -> Uyari gosterim bitis zamani

KALIBRASYON DEGISKENLERI:
  calibration_mode       -> Kalibrasyon modunda mi?
  calibration_data       -> Toplanan olcum verileri
    {neck_angles: [], torso_angles: [], yaws: [], pitches: []}
  personal_thresholds    -> Kisisel esik degerleri (sunucudan yuklenir)

YUZ TANIMA DEGISKENLERI:
  face_recognition_enabled -> Yuz tanima aktif mi?
  known_faces              -> Kayitli yuzler {username: encoding}
  recognized_user          -> Taninan kullanici adi

MOLA HATIRLATICI DEGISKENLERI:
  break_reminder_enabled -> Mola hatirlatici aktif mi?
  break_work_minutes     -> Calisma suresi (dk, varsayilan 25)
  break_rest_minutes     -> Mola suresi (dk, varsayilan 5)
  break_timer_start      -> Calisma sayaci baslangici
  on_break               -> Su an mola modunda mi?
  break_until            -> Mola bitis zamani
  break_display_until    -> Mola uyarisi gosterim zamani

CORE MODULLER (nesneler):
  CameraManager         -> Kamera erisimi (core/camera.py)
  PostureAnalyzer       -> Postur analizi (core/posture_analyzer.py)
  GazeAnalyzer          -> Bakis analizi (core/gaze_analyzer.py)
  PersonTracker         -> Coklu kisi takibi (sadece ofis modunda)

MOD FARKLARI:
  KISISEL MOD (personal):
    - max_persons = 1
    - PersonTracker OLUSTURULMAZ
    - Tek kisi analiz edilir

  OFIS MODU (office):
    - max_persons = config.MAX_PERSONS (6)
    - PersonTracker olusturulur
    - Birden fazla kisi analiz edilir

================================================================================
BOLUM 3: YASAM DONGUSU (run metodu)
================================================================================

run() metodu programin ana dongusudur. Sira ile su adimlari gerceklestirir:

ADIM 1: KAMERAYI AC
  self.camera.open()
  - Basarisiz olursa program sonlanir
  - DirectShow ve sonra genel mod denenir

ADIM 2: KISISEL MODEL YUKLE
  await self.load_personal_model()
  - HTTP GET /api/personal-model/{username}/
  - Kalibre ise esik degerlerini yukle
  - Kalibre degilse varsayilan esiklerle devam et

ADIM 3: KALIBRASYON KONTROLU
  Eger kisisel model kalibre degilse VEYA --calibrate argumanit verilmisse:
  await self.run_calibration()
  - 15 saniye boyunca veri topla
  - Ortalama ve std hesapla
  - Sunucuya kaydet

ADIM 4: YUZ KAYDI VE YUKLEME
  Kisisel modda:
  - Ilk frame'den yuz encoding'i cikar
  - await self.register_face(frame)
  - await self.load_face_encodings()

ADIM 5: WEBSOCKET BAGLANTISI
  await self.connect()
  - ws://sunucu:port/ws/employee/{room_code}/{username}/
  - Baglanti kuramazsa tekrar dener

ADIM 6: MESAJ ALIM THREAD'I
  asyncio.ensure_future(self.receive_messages())
  - Ayri bir coroutine olarak sunucudan gelen mesajlari dinler
  - Uyarilari self.warnings listesine ekler
  - Oda ayarlarini uygular (mola hatirlatici)

ADIM 7: ANA DONGU
  self.running = True iken:
    a) Kameradan frame oku
    b) Frame'i analiz et (analyze_frame)
    c) Overlay ciz (draw_overlay)
    d) WebSocket ile durum gonder (send_status)
    e) OpenCV penceresi goster
    f) 'q' tusuna basilirsa cik
    g) Her dongu arasinda kisa bekleme (rate limiting)

ADIM 8: TEMIZLIK
  - Kamerayi kapat
  - WebSocket'i kapat
  - Analiz modullerini kapat
  - OpenCV pencerelerini kapat

================================================================================
BOLUM 4: FRAME ANALIZI (analyze_frame)
================================================================================

analyze_frame(frame) -> Tek bir frame'i analiz eder, sonuclari dondurur.

KISISEL MOD:
  1. RGB donusumu: frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
  2. Postur analizi: posture = self.posture_analyzer.analyze(frame_rgb)
  3. Bakis analizi: gaze = self.gaze_analyzer.analyze(frame_rgb)
  4. Sonuc sozlugu olustur:
     {
       "posture": {
         "neck_angle": 15.3,
         "torso_angle": 8.7,
         "is_good": True,
         "score": 85
       },
       "gaze": {
         "yaw": 5.2,
         "pitch": -3.1,
         "is_working": True
       }
     }
  5. Iskelet ciz: draw_landmarks()
  6. Kalibrasyon modundaysa: Acilari calibration_data'ya kaydet

OFIS MODU:
  1. Tum vucutlari tespit et: postures = analyzer.analyze_all(frame_rgb)
  2. Tum yuzleri tespit et: gazes = gaze_analyzer.analyze_all(frame_rgb)
  3. PersonTracker.update(postures, gazes) ile eslestir
  4. Her kisi icin sonuc olustur
  5. Tum kisilerin sonuclarini tek mesajda gonder

================================================================================
BOLUM 5: GORSEL OVERLAY (draw_overlay)
================================================================================

draw_overlay(frame, status_data) -> Frame uzerine bilgi katmani cizer.

SOL UST KOSE - BAGLANTI DURUMU:
  - "BAGLI" veya "BAGLANTI YOK" yazisi
  - Yesil veya kirmizi arka plan

SOL UST - POSTUR SKORU:
  - "Skor: 85" gibi buyuk yazi
  - Renk skora gore degisir (yesil/sari/kirmizi)

SOL UST - CALISMA DURUMU:
  - "Calisiyor" veya "Mola" yazisi
  - Yesil veya sari arka plan

ALT PANEL - DETAYLI BILGI:
  - Boyun acisi
  - Govde acisi
  - Yaw / Pitch acilari
  - FPS (saniyedeki kare sayisi)

UYARI GOSTERIMI:
  - Yoneticiden uyari geldiginde buyuk kirmizi cerceveli metin
  - Bip sesi calinir
  - Belirli sure sonra kaybolur (warning_display_until)

KALIBRASYON GOSTERIMI:
  - Yesil cerceve ile "KALIBRASYON" yazisi
  - Geri sayim (15... 14... 13...)
  - Ilerleme cubugu (progress bar)

MOLA HATIRLATICI GOSTERIMI:
  - Sari cerceve ile "MOLA ZAMANI!" yazisi
  - Kalan mola suresi gosterilir

================================================================================
BOLUM 6: WEBSOCKET YONETIMI
================================================================================

connect():
  - WebSocket baglantisi kurar
  - ws://sunucu:port/ws/employee/{room_code}/{username}/
  - websockets kutuphanesi kullanilir
  - Hata durumunda tekrar dener

receive_messages():
  Asenkron coroutine olarak surekli dinler:

  GELEN MESAJ TIPLERI:

    "warning" (Uyari):
      - Yoneticiden gelen uyari mesaji
      - self.warnings listesine ekler
      - warning_display_until ayarlar (10 saniye gosterim)
      - play_beep() ile sesli uyari
      - OpenCV penceresinde kirmizi uyari gosterir

    "room_settings" (Oda Ayarlari):
      - Oda ayarlarini uygular
      - break_reminder_enabled, break_work_minutes, break_rest_minutes
      - Bu ayarlar mola hatirlatici sistemini yapilandirir

    "break_reminder" (Mola Hatirlatici):
      - Sunucudan gelen mola mesaji
      - Uyari gibi gosterilir

send_status(data):
  - Analiz sonuclarini WebSocket ile sunucuya gonderir
  - JSON formatinda: {"type": "status_update", "data": {...}}
  - Saniyede 1 kez cagrilir

================================================================================
BOLUM 7: KALIBRASYON (run_calibration)
================================================================================

15 saniye boyunca calisanin dogal pozisyonunu olcer:

  1. Zamanlayici baslat: start_time = time.time()
  2. Dongu (15 saniye):
     a) Frame oku
     b) Postur analiz et ve açiyi calibration_data'ya ekle
     c) Bakis analiz et ve aciyi calibration_data'ya ekle
     d) Geri sayim overlay ciz
     e) OpenCV penceresi guncelle
  3. Ortalama ve standart sapma hesapla (numpy)
  4. Kisisel esikleri hesapla:
     esik = max(minimum_esik, ortalama + 2 * standart_sapma)
  5. HTTP POST /api/calibration/save/ ile sunucuya gonder
  6. Analizor esiklerini guncelle

OVERLAY GORUNUMU:
  - Buyuk "KALIBRASYON" basligi
  - "Lutfen duz oturun ve ekrana bakin" talimati
  - Geri sayim (15... 14... 13...)
  - Yatay ilerleme cubugu (dolan yesil cubuk)
  - Tamamlandiginda "Kalibrasyon basarili!" mesaji

================================================================================
BOLUM 8: YUZ TANIMA ISLEMLERI
================================================================================

register_face(frame):
  1. Frame'den MediaPipe ile yuz noktalarini tespit et
  2. 10 anahtar noktadan encoding vektoru (30 eleman) olustur
  3. numpy dizisini bytes'a cevir, base64 ile encode et
  4. HTTP POST /api/face/register/ ile sunucuya kaydet
  5. Basari/basarisizlik durumunu konsola yaz

load_face_encodings():
  1. HTTP GET /api/face/encodings/{room_code}/
  2. JSON yanitindaki her encoding'i:
     - base64 decode et
     - bytes'tan numpy dizisine cevir
  3. self.known_faces sozlugune kaydet: {username: numpy_array}

recognize_face(frame):
  1. Frame'den yuz encoding'i hesapla
  2. known_faces'deki her encoding ile Oklid mesafesi hesapla
  3. En kucuk mesafeyi bul
  4. Mesafe < esik ise -> taninan kullanici adini dondur
  5. Mesafe >= esik ise -> None dondur (bilinmeyen kisi)

================================================================================
BOLUM 9: MOLA HATIRLATICI SISTEMI
================================================================================

Pomodoro benzeri calisma/mola dongusu:

BASLANGIC:
  - Sunucudan oda ayarlari geldiginde aktif olur
  - break_timer_start = time.time() ile calisma sayaci baslar

CALISMA DONGUSU:
  Her frame'de kontrol:
  1. Gecen sure = time.time() - break_timer_start
  2. Gecen sure >= break_work_minutes * 60 ise:
     - "MOLA ZAMANI!" overlay goster
     - Bip sesi cal
     - on_break = True
     - break_until = time.time() + break_rest_minutes * 60

MOLA DONGUSU:
  Mola modundaysa:
  1. Kalan mola suresi = break_until - time.time()
  2. Kalan sure <= 0 ise:
     - Moladan cik
     - on_break = False
     - break_timer_start = time.time() (yeni calisma dongusu)

================================================================================
BOLUM 10: SESLI UYARI SISTEMI
================================================================================

play_beep(frequency=800, duration=200):
  - Platform bagimsiz bip sesi
  - Windows: winsound.Beep() (yerel API)
  - Diger: terminal bip ('\a' karakteri)
  - Ayri thread'de calisir (ana donguyu engellemez)

KULLANIM YERLERI:
  - Yoneticiden uyari geldiginde
  - Mola hatirlatici tetiklendiginde
  - Kalibrasyon tamamlandiginda

================================================================================
BOLUM 11: MAIN FONKSIYONU (program giris noktasi)
================================================================================

main():
  1. argparse ile komut satiri argumanlarini parse et
  2. EmployeeClient nesnesi olustur
  3. asyncio.run(client.run()) ile ana donguyu calistir
  4. KeyboardInterrupt (Ctrl+C) ile duzgun kapatma

if __name__ == '__main__':
  main()

ARGPARSE PARAMETRELERI:
  --server, -s    : Sunucu adresi (zorunlu)
  --room, -r      : Oda kodu (zorunlu)
  --user, -u      : Kullanici adi (zorunlu)
  --mode, -m      : 'personal' veya 'office' (varsayilan: personal)
  --camera, -c    : Kamera indeksi (varsayilan: 0)
  --calibrate     : store_true (zorla kalibrasyon)

================================================================================
BAGIMLILIKLAR
================================================================================

PYTHON PAKETLERI:
  opencv-python (cv2)  -> Kamera ve goruntu isleme
  numpy                -> Matematiksel hesaplamalar
  websockets           -> WebSocket istemci kutuphanesi
  mediapipe            -> AI modelleri (postur + yuz) [PostureAnalyzer icinde]

DAHILI MODULLER:
  config               -> Yapilandirma sabitleri
  core.CameraManager   -> Kamera erisim sarmalayicisi
  core.PostureAnalyzer  -> Postur analiz sinifi
  core.GazeAnalyzer    -> Bakis analiz sinifi
  core.PersonTracker   -> Coklu kisi takip sinifi

STANDART KUTUPHANE:
  argparse             -> Komut satiri argumanlar
  asyncio              -> Asenkron programlama
  json                 -> JSON islemleri
  sys, os              -> Sistem islemleri
  threading            -> Paralel islemler (bip sesi, mesaj dinleme)
  time                 -> Zaman islemleri
  platform             -> Platform tespiti (Windows/Linux)
  urllib.request       -> HTTP istekleri (API cagrilari)
  base64               -> Binary veri kodlama (yuz encoding)

================================================================================
DOSYA KONUMU
================================================================================

  client/employee_client.py  -> Bu dosyada aciklanan tum istemci kodlari
  client/employee_gui.py     -> GUI versiyonu (tkinter ile masaustu arayuz)

================================================================================
"""
