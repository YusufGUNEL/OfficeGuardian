"""
================================================================================
                    OFFICEGUARDIAN - PROJE GENEL BAKIS
================================================================================

Bu dosya OfficeGuardian projesinin TAMAMEN aciklamali dokumanasyonudur.
Kod icermez, sadece projenin ne oldugunu, nasil calistigini ve tum
parcalarinin birbirleriyle nasil etkilestigini anlatir.

================================================================================
PROJE NEDIR?
================================================================================

OfficeGuardian, ofis ortaminda calisanlarin postur (oturusu) ve odaklanma
durumlarini GERCEK ZAMANLI olarak izleyen bir yapay zeka destekli sistemdir.

Sistem 3 ana parcadan olusur:
  1. DJANGO WEB SUNUCUSU  - Yonetim paneli, veritabani, API'ler
  2. MASAUSTU ISTEMCI      - Calisanin bilgisayarinda calisan kamera uygulamasi
  3. WEBSOCKET KATMANI     - Gercek zamanli iletisim altyapisi

================================================================================
NASIL CALISIR? (Bastan Sona Akis)
================================================================================

ADIM 1: YONETICI ODA OLUSTURUR
  - Web panelinden "Odalar" sayfasina gider
  - Oda adi yazar (orn: "Yazilim Ekibi")
  - Mola hatirlatici ayarlarini yapar (isterse)
  - "Olustur" butonuna basar
  - Sistem otomatik 6 haneli benzersiz kod uretir (orn: ABC123)

ADIM 2: CALISAN ODAYA KATILIR
  - Terminalde su komutu calistirir:
    python client/employee_client.py --server 192.168.1.20:8000 --room ABC123 --user AhmetYilmaz
  - Client acilir, kamera aktif olur
  - Eger ilk kez baglaniyorsa KALIBRASYON yapilir (15 saniye duz otur)
  - Yuz verisi kaydedilir (yuz tanima icin)
  - WebSocket ile sunucuya baglanir

ADIM 3: ANALIZ BASLAR
  - Client her frame'i (saniyede ~30 kare) analiz eder:
    a) MediaPipe Pose Landmarker: 33 vucut noktasi tespit eder
       -> Boyun acisi ve govde acisi hesaplanir
       -> Eger esik degerini asarsa "kambur" olarak isaretlenir
    b) MediaPipe Face Landmarker: Yuz noktalarini tespit eder
       -> Yaw (sag-sol bakis) ve Pitch (yukari-asagi bakis) hesaplanir
       -> Eger ekrana bakmiyorsa "mola" olarak isaretlenir
  - Sonuclar her 1 saniyede bir WebSocket ile sunucuya gonderilir

ADIM 4: YONETICI CANLI IZLER
  - Web panelinde "Canli Izleme" sayfasina gider
  - Odayi secer
  - Her calisan icin bir kart gorunur:
    * Postur durumu (Dik/Kambur + aci)
    * Calisma durumu (Calisiyor/Mola)
    * Postur skoru (0-100)
  - Canli grafikler guncellenir (Chart.js)
  - Uyari gonderebilir ("Dik dur!", "Ekrana odaklan!")

ADIM 5: VERILER KAYDEDILIR
  - Her saniye PostureLog ve WorkStatusLog tablolarina yazilir
  - Gunluk istatistikler (DailyStats) otomatik guncellenir
  - Bildirimler olusturulur (dusuk postur, baglanti vb.)

================================================================================
TEKNOLOJI YIGINI (TECH STACK)
================================================================================

BACKEND (Sunucu Tarafi):
  - Django 5.0+         : Python web framework'u
  - Django Channels 4.0 : WebSocket destegi (gercek zamanli iletisim)
  - Daphne 4.0          : ASGI sunucusu (HTTP + WebSocket ayni anda)
  - SQLite3             : Veritabani (dosya bazli, kurulum gerektirmez)

FRONTEND (Web Arayuzu):
  - Bootstrap 5.3       : CSS framework'u (responsive tasarim)
  - Bootstrap Icons     : Ikon seti
  - Chart.js 4.4        : Canli grafikler
  - Vanilla JavaScript  : Framework'suz saf JS

MASAUSTU ISTEMCI:
  - OpenCV 4.8+         : Kamera erisimi ve goruntu isleme
  - MediaPipe 0.10.9    : Google'in AI modelleri (postur + yuz)
  - NumPy               : Matematiksel hesaplamalar
  - websockets          : WebSocket istemci kutuphanesi

EKLENTILER:
  - openpyxl            : Excel (.xlsx) dosya olusturma
  - python-docx         : Word dosya olusturma
  - Pillow              : Goruntu isleme

================================================================================
KLASOR YAPISI
================================================================================

OfficeGuardian/
  |
  |-- accounts/              # Kullanici hesaplari ve kimlik dogrulama
  |   |-- models.py         # CustomUser modeli (roller, tema, avatar)
  |   |-- views.py          # Login, register, profil, tema degistirme
  |   |-- forms.py          # Login, register, profil, sifre formları
  |   |-- urls.py           # /accounts/login, /accounts/profile vb.
  |   |-- templates/        # Login, register, profil HTML sayfalari
  |
  |-- dashboard/             # Ana uygulama (her sey burada)
  |   |-- models.py         # Room, Session, Loglar, Bildirim, PersonalModel...
  |   |-- views.py          # Tum sayfalar ve API endpoint'leri
  |   |-- consumers.py      # WebSocket handler'lari (calisan + admin)
  |   |-- urls.py           # Tum URL tanimlari
  |   |-- routing.py        # WebSocket URL tanimlari
  |   |-- templates/        # HTML sayfalari (dashboard, odalar, loglar vb.)
  |
  |-- core/                  # AI analiz modulleri (istemci tarafinda calisir)
  |   |-- camera.py         # Kamera yonetimi (OpenCV wrapper)
  |   |-- posture_analyzer.py  # Postur analizi (MediaPipe Pose)
  |   |-- gaze_analyzer.py     # Bakis analizi (MediaPipe Face)
  |   |-- person_tracker.py    # Coklu kisi takibi (ofis modu)
  |   |-- session_tracker.py   # Oturum yonetimi
  |   |-- event_logger.py      # Olay kayitcisi
  |
  |-- client/                # Masaustu istemci uygulamasi
  |   |-- employee_client.py # Ana istemci (kamera + WS + analiz + kalibrasyon)
  |   |-- employee_gui.py    # GUI versiyonu
  |
  |-- static/                # Statik dosyalar (CSS + JS)
  |   |-- css/style.css     # Ana stil dosyasi (koyu + acik tema)
  |   |-- js/dashboard.js   # Admin dashboard WebSocket + Chart.js
  |   |-- js/employee.js    # Calisan paneli JS
  |
  |-- models/                # Onceden egitilmis AI modelleri
  |   |-- pose_landmarker_lite.task   # MediaPipe postur modeli
  |   |-- face_landmarker.task        # MediaPipe yuz modeli
  |
  |-- officeguardian/        # Django proje ayarlari
  |   |-- settings.py       # Veritabani, uygulamalar, middleware vb.
  |   |-- asgi.py           # ASGI yapilandirmasi (WebSocket icin)
  |   |-- urls.py           # Ana URL yonlendirmesi
  |
  |-- Calisma/               # DOKUMANTASYON (su an okudugunuz yer)
  |-- config.py              # Genel yapilandirma (esik degerleri, kamera vb.)
  |-- manage.py              # Django yonetim araci
  |-- requirements.txt       # Python paket bagimliliklari
  |-- db.sqlite3             # Veritabani dosyasi

================================================================================
ROLLER VE YETKILER
================================================================================

SUPER ADMIN:
  - Tum odalari gorur (baskalarinin da)
  - Kullanici rollerini degistirebilir
  - Takim liderlerine oda atayabilir
  - Her seyi yapabilir

YONETICI:
  - Kendi odalarini olusturur ve yonetir
  - Calisanlari canli izler
  - Uyari gonderir
  - Log gorur ve CSV/Excel export yapar

TAKIM LIDERI:
  - Sadece kendisine ATANAN odalari gorur
  - Canli izleme yapabilir
  - Uyari gonderebilir
  - Log gorebilir
  - Oda OLUSTURAMAZ, SILEMEZ
  - Export YAPAMAZ

CALISAN:
  - Sadece kendi panelini gorur
  - Kendi istatistiklerini inceler
  - Uyarilari okur

================================================================================
ONEMLI KAVRAMLAR
================================================================================

POSTUR SKORU (0-100):
  Calisanin ne kadar duz oturdugunu gosteren puan.
  - 100: Mukemmel durus
  - 70-99: Iyi
  - 40-69: Orta (sari uyari)
  - 0-39: Kotu (kirmizi uyari)
  Hesaplama: Boyun acisi ve govde acisi esik degerlerine gore

KALIBRASYON:
  Her calisanin vucut yapisi farkli oldugundan, sistem ilk baglantida
  15 saniye boyunca "normal" degerlerini olcer. Sonra bu degerlere gore
  kisisel esik degerleri hesaplar. Boylece uzun boylu birinin dogal
  15 derece boyun acisi "kambur" olarak isaretlenmez.

WEBSOCKET:
  Normal HTTP istekleri "istek-cevap" seklindedir. Ama canli izleme
  icin sunucunun istemciye aninda veri gondermesi gerekir. WebSocket
  surekli acik bir kanal saglar - her iki taraf da istedigi zaman
  mesaj gonderebilir.

MEDIAPIPE:
  Google'in gelistirdigi, onceden egitilmis AI modelleri. Bu projede:
  - PoseLandmarker: Vucut uzerinde 33 nokta tespit eder (omuz, diz, bilek vb.)
  - FaceLandmarker: Yuzde 478 nokta tespit eder (goz, burun, agiz vb.)
  Bu noktalardan acilar hesaplanarak postur ve bakis yonu belirlenir.

================================================================================
"""
