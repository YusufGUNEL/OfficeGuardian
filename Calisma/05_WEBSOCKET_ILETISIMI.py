"""
================================================================================
                    OFFICEGUARDIAN - WEBSOCKET ILETISIMI
================================================================================

Bu dosya, OfficeGuardian'daki gercek zamanli iletisim altyapisini aciklar.
WebSocket, sistemin kalbidir - calisan istemci ile web sunucusu arasindaki
canli veri akisini saglar.

================================================================================
WEBSOCKET NEDIR?
================================================================================

Normal HTTP istekleri "istek-cevap" seklinde calisir:
  Istemci: "Veri ver"  ->  Sunucu: "Al sana veri"
  Baglanti kapanir.
  Istemci tekrar isteyene kadar sunucu bir sey gonderemez.

WebSocket ise SUREKLI ACIK bir iletisim kanalidir:
  Istemci: "Baglantı ac"  ->  Sunucu: "Tamam"
  (Kanal acik kalir)
  Istemci: Veri gonderebilir  <->  Sunucu: Veri gonderebilir
  Her iki taraf da istedigi zaman mesaj gonderebilir.

NEDEN WEBSOCKET KULLANIYORUZ?
  - Canli izleme icin sunucunun istemciye ANINDA veri gondermesi gerekir
  - HTTP ile bu yapilsa, istemci her saniye sunucuya "yeni veri var mi?"
    diye sormak zorunda kalir (polling) -> verimsiz
  - WebSocket ile sunucu, yeni veri geldiginde HEMEN istemciye iletir

================================================================================
DJANGO CHANNELS
================================================================================

Django normalde sadece HTTP destekler. WebSocket icin Django Channels
eklentisi kullanilir.

BILESENLERI:
  1. ASGI (Asynchronous Server Gateway Interface):
     Django'nun asenkron sunucu arayuzu. HTTP ve WebSocket'i
     ayni anda destekler.

  2. Daphne:
     ASGI uyumlu sunucu. Django'nun varsayilan sunucusu (runserver)
     sadece HTTP'yi desteklerken, Daphne hem HTTP hem WebSocket'i
     ayni anda servir eder.

  3. Channel Layers:
     WebSocket gruplari arasinda mesaj iletimi saglar.
     Ornegin, bir calisan veri gonderdiginde bu veri
     ayni odadaki yoneticilere iletilir.

  4. Consumers:
     Django'nun "views" kavramisinin WebSocket karsiligi.
     Her WebSocket baglantisi bir Consumer tarafindan yonetilir.

================================================================================
PROJE YAPILANDIRMASI
================================================================================

officeguardian/asgi.py:
  Django uygulamasinin ASGI yapilandirmasi.
  HTTP isteklerini Django'ya, WebSocket isteklerini
  Channels'a yonlendirir.

dashboard/routing.py:
  WebSocket URL tanimlari:
    ws/employee/<room_code>/<username>/  -> EmployeeConsumer
    ws/admin/<room_code>/                -> AdminConsumer

Sunucu baslatma:
  python manage.py runserver  # Gelistirme icin (daphne otomatik)
  daphne officeguardian.asgi:application  # Uretim icin

================================================================================
CONSUMER SINIFLARI
================================================================================

Projede 2 consumer vardir:

1. EmployeeConsumer (Calisan Tarafli)
2. AdminConsumer (Yonetici Tarafli)

Her ikisi de AsyncWebsocketConsumer sinifindan turetilir
(asenkron calisir, veritabani islemleri icin database_sync_to_async kullanilir).

================================================================================
EMPLOYEECONSUMER - DETAYLI AKIS
================================================================================

BAGLANTI KURULMASI (connect):
  1. URL'den room_code ve username alinir
  2. Iki gruba katilir:
     - room_{room_code}  : Odadaki tum calisanlar
     - employee_{username}: Bu calisana ozel (uyari gondermek icin)
  3. Veritabaninda oturum kaydı olusturulur (EmployeeSession)
  4. Baglanti kabul edilir (accept)
  5. Oda ayarlari calisana gonderilir (mola hatirlatici vb.)
  6. Admin grubuna "calisan baglandi" mesaji gonderilir
  7. Yoneticiye bildirim olusturulur

VERI ALMA (receive):
  Calisan istemci her saniye "status_update" mesaji gonderir:

  {
    "type": "status_update",
    "data": {
      "posture": {
        "neck_angle": 15.3,
        "torso_angle": 8.7,
        "is_good": true,
        "score": 85
      },
      "gaze": {
        "yaw": 5.2,
        "pitch": -3.1,
        "is_working": true
      }
    }
  }

  Bu veri alindiginda:
  a) Veritabanina kaydedilir (PostureLog, WorkStatusLog, DailyStats)
  b) Dusuk postur kontrolu yapilir (skor < 30 ise bildirim olustur)
  c) Admin grubuna iletilir (canli izleme icin)

BAGLANTI KAPANMASI (disconnect):
  1. Veritabanindaki oturum kapatilir
  2. Gruplardan ayrilir
  3. Admin grubuna "calisan ayrildi" mesaji gonderilir
  4. Yoneticiye bildirim olusturulur

GELEN MESAJLAR (calisan tarafi):
  - warning_message: Yoneticiden gelen uyari ("Dik dur!" vb.)
  - break_reminder: Mola hatirlatici mesaji

================================================================================
ADMINCONSUMER - DETAYLI AKIS
================================================================================

BAGLANTI KURULMASI (connect):
  1. URL'den room_code alinir
  2. YETKI KONTROLU yapilir:
     - Kullanici oturum acmis mi?
     - Rolu super_admin, yonetici veya takim_lideri mi?
  3. admin_{room_code} grubuna katilir
  4. Mevcut cevrimici calisanlarin listesi gonderilir

GELEN MESAJLAR (yonetici tarafi):
  - employee_status: Calisan durum guncellemesi -> arayuze iletilir
  - office_status: Ofis modu guncellemesi -> arayuze iletilir
  - employee_connected: Calisan baglandi bildirimi
  - employee_disconnected: Calisan ayrildi bildirimi

GONDERILEN MESAJLAR (yonetici tarafi):
  - send_warning: Secilen calisana uyari gonder
    {
      "type": "send_warning",
      "username": "AhmetYilmaz",
      "message": "Dik dur!"
    }

================================================================================
GRUP YAPISI
================================================================================

WebSocket gruplari, mesajlarin dogru yerlere iletilmesini saglar.

GRUPLAR:
  room_{room_code}      : Bir odadaki TUM calisanlar
                          Ornek: room_ABC123

  employee_{username}    : TEK bir calisan (uyari gondermek icin)
                          Ornek: employee_AhmetYilmaz

  admin_{room_code}      : Bir odayi izleyen TUM yoneticiler
                          Ornek: admin_ABC123

MESAJ AKISI ORNEGI:
  1. AhmetYilmaz (calisan) baglaniyor
     -> room_ABC123 grubuna katilir
     -> employee_AhmetYilmaz grubuna katilir
     -> admin_ABC123 grubuna "baglandi" mesaji gonderilir

  2. AhmetYilmaz her saniye durum gonderiyor
     -> EmployeeConsumer veritabanina kaydeder
     -> admin_ABC123 grubuna iletir

  3. Yonetici AhmetYilmaz'a "Dik dur!" mesaji gonderiyor
     -> AdminConsumer mesaji alir
     -> employee_AhmetYilmaz grubuna iletir
     -> AhmetYilmaz'in istemcisi uyariyi gosterir

================================================================================
VERITABANI ISLEMLERI
================================================================================

WebSocket consumer'lari ASENKRON calisir. Ama Django ORM SENKRON'dur.
Bu yuzden veritabani islemleri @database_sync_to_async dekoratoruyle
senkrondan asenkrona cevrulir.

  @database_sync_to_async
  def save_status(self, data):
      PostureLog.objects.create(...)  # Senkron ORM islemi

Bu dekorator, senkron kodu ayri bir thread'de calistirir ve
sonucu asenkron olarak doner.

KAYDEDILEN VERILER:
  - PostureLog: boyun acisi, govde acisi, iyi/kotu, skor
  - WorkStatusLog: calisiyor/mola, yaw, pitch
  - DailyStats: gunluk toplam calisma/mola/postur sureleri

================================================================================
ISTEMCI TARAFI WEBSOCKET
================================================================================

Masaustu istemci (employee_client.py) sunucuya su sekilde baglanir:

  import websockets

  uri = "ws://192.168.1.20:8000/ws/employee/ABC123/AhmetYilmaz/"
  async with websockets.connect(uri) as websocket:
      # Veri gonder
      await websocket.send(json.dumps(data))
      # Veri al
      message = await websocket.recv()

Web arayuzu (dashboard.js) ise tarayici WebSocket API'si kullanir:

  const ws = new WebSocket("ws://localhost:8000/ws/admin/ABC123/");
  ws.onmessage = function(e) {
      const data = JSON.parse(e.data);
      // Arayuzu guncelle...
  };

OTOMATIK YENIDEN BAGLANTI:
  Baglanti koparsa 3 saniye sonra tekrar denir:
  ws.onclose = function() {
      setTimeout(() => initAdminDashboard(roomCode), 3000);
  };

================================================================================
DOSYA KONUMLARI
================================================================================

  dashboard/consumers.py   - WebSocket consumer siniflari
  dashboard/routing.py     - WebSocket URL tanimlari
  officeguardian/asgi.py   - ASGI yapilandirmasi
  static/js/dashboard.js   - Yonetici tarafli WebSocket istemcisi
  client/employee_client.py - Masaustu istemci WebSocket baglantisi

================================================================================
"""
