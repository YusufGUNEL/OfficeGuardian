"""
================================================================================
                    OFFICEGUARDIAN - AYARLAR VE YAPILANDIRMA
================================================================================

Bu dosya, projenin yapilandirma dosyalarini detayli olarak aciklar.
3 ana dosya incelenir:
  1. officeguardian/settings.py  -> Django proje ayarlari
  2. officeguardian/asgi.py      -> Asenkron sunucu yapilandirmasi
  3. config.py                   -> Uygulama sabitleri (esikler, kamera vb.)

================================================================================
BOLUM 1: DJANGO AYARLARI (officeguardian/settings.py)
================================================================================

Django proje ayarlarinin tamami bu dosyada tanimlanir.
En onemli ayarlar asagida aciklanir.

---------------------------------------------------------------------------
1.1 TEMEL AYARLAR
---------------------------------------------------------------------------

  BASE_DIR = Path(__file__).resolve().parent.parent
    Projenin kok dizini. Diger tum dosya yollari buna goredir.
    Ornek: c:/Dark/OfficeGuardian/

  SECRET_KEY = 'django-insecure-...'
    Django'nun guvenlik anahtari. Oturum sifrelemesinde ve CSRF korumasinda
    kullanilir. Uretim ortaminda (production) Bu deger degistirilmeli
    ve cevresel degiskenden (env variable) okunmalidir.
    !!! UYARI: Mevcut deger guvensizdir, sadece gelistirme icindir.

  DEBUG = True
    Hata ayiklama modu. True iken:
    - Detayli hata sayfalari gosterilir
    - Statik dosyalar otomatik servis edilir
    - Performans dusuktur
    Uretim ortaminda MUTLAKA False olmalidir.

  ALLOWED_HOSTS = ['*']
    Hangi host isimlerinin kabul edilecegi.
    '*' tum hostlari kabul eder (guvenlik riski).
    Uretim: ['192.168.1.20', 'officeguardian.example.com'] gibi sinirlanmali.

---------------------------------------------------------------------------
1.2 UYGULAMALAR (INSTALLED_APPS)
---------------------------------------------------------------------------

  INSTALLED_APPS = [
      'daphne',                        # ASGI sunucusu (WebSocket icin)
      'django.contrib.admin',          # Django admin paneli
      'django.contrib.auth',           # Kimlik dogrulama sistemi
      'django.contrib.contenttypes',   # Icerik tipi framework'u
      'django.contrib.sessions',       # Oturum yonetimi (cookie)
      'django.contrib.messages',       # Flash mesajlar
      'django.contrib.staticfiles',    # Statik dosya yonetimi
      'channels',                      # Django Channels (WebSocket)
      'accounts',                      # Kullanici hesaplari
      'dashboard',                     # Ana uygulama
  ]

  ONEMLI SIRALAMA:
    - 'daphne' en basta olmali (ASGI sunucusunun dogru baslamasi icin)
    - 'channels' Django uygulamalarindan once olmali
    - Proje uygulamalari ('accounts', 'dashboard') en sonda

---------------------------------------------------------------------------
1.3 MIDDLEWARE
---------------------------------------------------------------------------

  Middleware, her HTTP istegi ve yanitinin gecirildigikaesit katmanlardir.
  Her biri sirirasiyla calisir:

    SecurityMiddleware     -> HTTPS yonlendirme, guvenlik basaliklari
    SessionMiddleware      -> Oturum yonetimi (cookie <-> DB)
    CommonMiddleware       -> URL duzeltme (trailing slash vb.)
    CsrfViewMiddleware     -> CSRF saldiri korumasi
    AuthenticationMiddleware -> request.user nesnesini olusturur
    MessageMiddleware      -> Flash mesaj destegi
    XFrameOptionsMiddleware -> Clickjacking korumasi

  Istek akisi:  Istemci -> Middleware (yukari) -> View -> Middleware (asagi) -> Istemci

---------------------------------------------------------------------------
1.4 VERITABANI
---------------------------------------------------------------------------

  DATABASES = {
      'default': {
          'ENGINE': 'django.db.backends.sqlite3',
          'NAME': BASE_DIR / 'db.sqlite3',
      }
  }

  SQLite3 KULLANIMIN AVANTAJLARI:
    - Kurulum gerektirmez (dosya bazli)
    - Tek bir dosya: db.sqlite3
    - Gelistirme icin ideal
    - Yedekleme: dosyayi kopyala

  DEZAVANTAJLARI:
    - Eszamanlı yazma sinirli (tek yazuci kilidi)
    - Buyuk veri setlerinde yavas
    - Ag uzerinden paylasim zor
    -  Uretim icin PostgreSQL veya MySQL onerilir

---------------------------------------------------------------------------
1.5 KIMLIK DOGRULAMA
---------------------------------------------------------------------------

  AUTH_USER_MODEL = 'accounts.CustomUser'
    Django'nun varsayilan User modelini degil, bizim ozel CustomUser
    modelimizi kullanmasini saglar. Proje basinda ayarlanmali, sonra
    degistirmek cok zordur (migration sorunlari).

  AUTH_PASSWORD_VALIDATORS:
    Sifre karmasikligi kontrolu. Mevcut:
    - MinimumLengthValidator: En az 8 karakter (varsayilan)
    Gelistirme asamasinda basit tutulmus.

  LOGIN_URL = '/accounts/login/'
    @login_required dekoratoru yonlendirme adresi.
  LOGIN_REDIRECT_URL = '/'
    Basarili giristen sonra yonlendirme adresi.
  LOGOUT_REDIRECT_URL = '/accounts/login/'
    Cikistan sonra yonlendirme adresi.

---------------------------------------------------------------------------
1.6 CHANNEL LAYERS (WEBSOCKET)
---------------------------------------------------------------------------

  CHANNEL_LAYERS = {
      'default': {
          'BACKEND': 'channels.layers.InMemoryChannelLayer',
      },
  }

  InMemoryChannelLayer:
    - Mesajlari RAM'de saklar
    - Tek proses icin calisir
    - Gelistirme icin idealdir
    - DEZAVANTAJ: Sunucu yeniden basladiginda TUM mesajlar kaybolur

  Uretim icin onerilir: channels_redis.RedisChannelLayer
    - Redis sunucusu gerektirir
    - Coklu proses destekler (olceklenebilir)
    - Mesajlar disk'e yazilabilir (dayaniklilik)

---------------------------------------------------------------------------
1.7 YERELLESIRME VE STATIK DOSYALAR
---------------------------------------------------------------------------

  LANGUAGE_CODE = 'tr'
    Django admin paneli ve hata mesajlari Turkce
  TIME_ZONE = 'Europe/Istanbul'
    Saat dilimi (UTC+3)
  USE_I18N = True
    Uluslararasilastirma aktif
  USE_TZ = True
    Zaman dilimi destegi aktif (timezone-aware datetime)

  STATIC_URL = '/static/'
    Statik dosyalarin URL oneki.
    Tarayici: /static/css/style.css -> Disk: static/css/style.css

  STATICFILES_DIRS = [BASE_DIR / 'static']
    Statik dosyalarin ARANDIGI dizinler.
    Sistem: OfficeGuardian/static/ klasorune bakar.

================================================================================
BOLUM 2: ASGI YAPILANDIRMASI (officeguardian/asgi.py)
================================================================================

ASGI (Asynchronous Server Gateway Interface), Django'nun asenkron
sunucu arayuzudur. Normal WSGI sadece HTTP desteklerken, ASGI
hem HTTP hem WebSocket'i ayni anda destekler.

KOD AKISI:

  1. Django uygulamasini yukle:
     os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'officeguardian.settings')
     django_asgi_app = get_asgi_application()

  2. WebSocket URL'lerini import et:
     from dashboard.routing import websocket_urlpatterns

  3. Protokol yonlendiricisini olustur:
     application = ProtocolTypeRouter({
         'http': django_asgi_app,           # HTTP -> Django
         'websocket': AuthMiddlewareStack(  # WebSocket -> Channels
             URLRouter(websocket_urlpatterns)
         ),
     })

  ProtocolTypeRouter:
    Gelen baglantinin tipini belirler:
    - HTTP istegi ise -> Django'nun standart isleyicisine gonder
    - WebSocket istegi ise -> Channels URL yonlendiricisine gonder

  AuthMiddlewareStack:
    WebSocket baglantilarina Django'nun oturum bilgisini ekler.
    Boylece consumer icinde self.scope['user'] ile oturum acmis
    kullaniciya erisilebilir.

  URLRouter:
    WebSocket URL'lerini consumer siniflarinra eslestirir.
    (dashboard/routing.py'deki tanimlar)

  NEDEN AYRI DOSYA?
    Django normalde wsgi.py kullanir. ASGI farkli bir protokol oldugu
    icin asgi.py'ye ihtiyac duyar. Daphne sunucusu bu dosyayi yukler:
    daphne officeguardian.asgi:application

================================================================================
BOLUM 3: WEBSOCKET ROUTING (dashboard/routing.py)
================================================================================

WebSocket URL tanimlari. HTTP URL'leri urls.py'de, WebSocket URL'leri
routing.py'de tanimlanir.

  websocket_urlpatterns = [
      re_path(r'ws/employee/(?P<room_code>\w+)/(?P<username>\w+)/$',
              consumers.EmployeeConsumer.as_asgi()),

      re_path(r'ws/admin/(?P<room_code>\w+)/$',
              consumers.AdminConsumer.as_asgi()),
  ]

  CALISAN BAGLANTISI:
    URL: ws://sunucu:port/ws/employee/ABC123/AhmetYilmaz/
    Regex gruplari:
      room_code: ABC123 (oda kodu)
      username: AhmetYilmaz (kullanici adi)
    Consumer: EmployeeConsumer

  YONETICI BAGLANTISI:
    URL: ws://sunucu:port/ws/admin/ABC123/
    Regex gruplari:
      room_code: ABC123 (oda kodu)
    Consumer: AdminConsumer

  re_path vs path:
    re_path: Regex kullanir (karmasik URL desenleri icin)
    path: Basit URL desenleri icin (views'da kullanilir)
    WebSocket URL'lerinde regex tercih edilir (esneklik)

================================================================================
BOLUM 4: UYGULAMA SABITLERI (config.py)
================================================================================

Projenin tum yapilandirma sabitleri tek bir dosyada toplanmistir.
Bu sayede degerler degistirildiginde tek yerde guncelleme yeterlidir.

---------------------------------------------------------------------------
4.1 DOSYA YOLLARI
---------------------------------------------------------------------------

  BASE_DIR -> Projenin kok dizini
  DATA_DIR -> data/ klasoru (oturum JSON dosyalari)
  LOGS_DIR -> logs/ klasoru (JSONL log dosyalari)
  MODELS_DIR -> models/ klasoru (AI model dosyalari)

  POSE_MODEL_PATH -> models/pose_landmarker_lite.task
  FACE_MODEL_PATH -> models/face_landmarker.task

---------------------------------------------------------------------------
4.2 KAMERA AYARLARI
---------------------------------------------------------------------------

  CAMERA_INDEX = 0
    Kullanilacak kamera numarasi.
    0 = varsayilan kamera (genelde dahili webcam)
    1 = ikinci kamera (USB webcam)
    Birden fazla kamerasi olan bilgisayarlarda degistirilmeli.

  FRAME_WIDTH = 640
  FRAME_HEIGHT = 480
    Goruntu boyutu (piksel). Daha yuksek cozunurluk daha iyi analiz
    ama daha fazla islem gucu gerektirir. 640x480 iyi bir denge.

---------------------------------------------------------------------------
4.3 POSTUR TESPITI ESIKLERI
---------------------------------------------------------------------------

  NECK_ANGLE_THRESHOLD = 25  (derece)
    Boyun one egme esigi. 25 derecenin ustunde = kambur.
    Dusurulurse: Daha hassas, daha cok uyari
    Yukseltilirse: Daha toleransli, daha az uyari

  TORSO_ANGLE_THRESHOLD = 15  (derece)
    Govde egme esigi. 15 derecenin ustunde = one egik.

  POSTURE_WARNING_DELAY = 10  (saniye)
    Kamburhluk gecikme suresi. 10 saniye boyunca surekli kambur
    kalirsa uyari tetiklenir. Anlik duzelmeleri filtreler.

---------------------------------------------------------------------------
4.4 BAKIS TESPITI ESIKLERI
---------------------------------------------------------------------------

  GAZE_YAW_THRESHOLD = 25  (derece)
    Sag/sol bakis esigi. |yaw| > 25 ise ekrana bakmiyor.

  GAZE_PITCH_THRESHOLD = 20  (derece)
    Yukari/asagi bakis esigi. |pitch| > 20 ise ekrana bakmiyor.

  GAZE_STATUS_DELAY = 10  (saniye)
    Calisma durumu gecikme suresi. 10 saniye boyunca bakmiyorsa "mola".
    Anlik bakis kaymalarini filtreler (telefona bakma, kapi kontrolu vb.)

---------------------------------------------------------------------------
4.5 COKLU KISI TAKIBI AYARLARI
---------------------------------------------------------------------------

  MAX_PERSONS = 6
    Ayni anda takip edilecek maksimum kisi sayisi. Daha fazlasi
    performansi dusurur ve eslestirme hatalarini artirir.

  PERSON_DISAPPEAR_TIMEOUT = 5.0  (saniye)
    Bir kisi kameradan kaybolursa 5 saniye sonra listeden silinir.
    Kisa sureli gizlenmeler (orn: onizdeki kisi gecti) tolere edilir.

  PERSON_MATCH_THRESHOLD = 0.15
    Eslestirme mesafe esigi (normalize koordinatlarda).
    0.15'in altindaki mesafe = ayni kisi.
    0.15'in ustunde = farkli kisi veya yeni kisi.

---------------------------------------------------------------------------
4.6 KISI RENKLERI
---------------------------------------------------------------------------

  PERSON_COLORS = [
      {"bgr": (0, 200, 0),     "hex": "#00c800"},   # Yesil
      {"bgr": (255, 165, 0),   "hex": "#ffa500"},   # Turuncu
      {"bgr": (255, 0, 255),   "hex": "#ff00ff"},   # Magenta
      {"bgr": (255, 255, 0),   "hex": "#ffff00"},   # Cyan
      {"bgr": (0, 128, 255),   "hex": "#ff8000"},   # Mavi-Turuncu
      {"bgr": (128, 0, 255),   "hex": "#ff0080"},   # Mor
  ]

  Her takip edilen kisiye sirayla renk atanir.
  bgr: OpenCV cizimlerinde kullanilir (BGR formati)
  hex: Web arayuzunde kullanilir (HEX renk kodu)

---------------------------------------------------------------------------
4.7 ARAYUZ AYARLARI
---------------------------------------------------------------------------

  UI_UPDATE_MS = 66
    Masaustu arayuz guncelleme araligi (milisaniye).
    66ms ≈ 15 FPS. Daha yuksek FPS gereksiz islem gucuttuketir.

  WINDOW_TITLE = "OfficeGuardian"
    Masaustu uygulamanin pencere basligi.

  WINDOW_SIZE = "1100x680"
    Masaustu uygulamanin pencere boyutu (piksel).

---------------------------------------------------------------------------
4.8 RENK SABITLERI
---------------------------------------------------------------------------

  COLOR_GREEN   = "#2ecc71"   -> Iyi durum (dik postur, calisiyor)
  COLOR_YELLOW  = "#f39c12"   -> Uyari durumu (orta skor, mola)
  COLOR_RED     = "#e74c3c"   -> Kotu durum (kambur, dusuk skor)
  COLOR_DARK_BG = "#1a1a2e"   -> Koyu arka plan
  COLOR_CARD_BG = "#16213e"   -> Kart arka plani
  COLOR_TEXT    = "#e0e0e0"   -> Metin rengi
  COLOR_ACCENT  = "#0f3460"   -> Vurgu rengi

  Bu renkler masaustu istemcinin GUI versiyonunda (employee_gui.py)
  kullanilir. Web arayuzundeki renkler CSS degiskenleri ile tanimlanir.

================================================================================
DOSYA KONUMLARI
================================================================================

  officeguardian/settings.py  -> Django proje ayarlari
  officeguardian/asgi.py      -> ASGI yapilandirmasi
  officeguardian/urls.py      -> Ana URL yonlendirmesi (accounts + dashboard)
  dashboard/routing.py        -> WebSocket URL tanimlari
  config.py                   -> Uygulama sabitleri

================================================================================
"""
