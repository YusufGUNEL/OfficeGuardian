# OfficeGuardian - Teknik Dokumantasyon

## Proje Nedir?

OfficeGuardian, yapay zeka tabanli bir **calisan izleme ve saglik takip sistemidir**. Kamera goruntusu uzerinden:

- **Postur tespiti**: Calisan kambur mu dik mi oturuyor?
- **Calisma takibi**: Calisan ekrana bakiyor mu yoksa baska yere mi bakiyor?
- **Istatistik toplama**: Gunluk calisma suresi, mola suresi, postur skoru
- **Canli izleme**: Yonetici web panelinden tum calisanlari gercek zamanli izleyebilir
- **Uyari sistemi**: Yonetici calisana aninda uyari gonderebilir

---

## Mimari Yapi (Architecture)

```
+-------------------+       WebSocket        +-------------------+
|   Desktop Client  | <------------------->  |   Django Server   |
|  (Python+OpenCV)  |   (Veri gonder/al)     |  (Daphne+Channels)|
|                   |                        |                   |
|  Kamera -> AI     |                        |  Database (SQLite)|
|  Postur Analizi   |                        |  Web Dashboard    |
|  Goz Yonu Analizi |                        |  Admin Panel      |
+-------------------+                        +-------------------+
                                                      |
                                                      | HTTP + WebSocket
                                                      v
                                             +-------------------+
                                             |   Web Tarayici    |
                                             |  (Admin/Calisan)  |
                                             +-------------------+
```

### Katmanlar:

1. **Desktop Client** (`client/`): Kamerayi acar, AI modelleri calistirir, sonuclari WebSocket ile sunucuya gonderir
2. **Core AI Modulleri** (`core/`): Postur analizi, goz yonu analizi, kisi takibi
3. **Django Backend** (`dashboard/`, `accounts/`): Web sunucusu, veritabani, kullanici yonetimi
4. **Frontend** (`templates/`, `static/`): Bootstrap + JavaScript ile web arayuzu

---

## 1. POSTUR TESPITI (Nasil Calisiyor?)

### Teori

Postur tespiti, **MediaPipe PoseLandmarker** modeli ile yapilir. Bu model bir video karesini alir ve insan vucudundaki 33 anahtar noktayi (landmark) tespit eder: bas, omuz, dirsek, kalca, diz vs.

Biz bu 33 noktadan sadece birkacini kullaniyoruz:

- **Kulak** (ear) - Basin konumunu belirlemek icin
- **Omuz** (shoulder) - Govde ustuyle referans almak icin
- **Kalca** (hip) - Govde altini referans almak icin

#### Aci Hesaplama Mantigi

```
Boyun Acisi (Neck Angle):
   Omuz noktasindan kulaga dogru bir vektor cizilir.
   Bu vektor ile dikey eksen (yukariya dogru) arasindaki aci olculur.

   Eger bu aci > 25 derece ise -> Kisi kambur oturuyor
   Eger bu aci < 25 derece ise -> Kisi dik oturuyor

Govde Acisi (Torso Angle):
   Kalca noktasindan omuza dogru bir vektor cizilir.
   Bu vektor ile dikey eksen arasindaki aci olculur.

   Eger bu aci > 15 derece ise -> Govde egik
   Eger bu aci < 15 derece ise -> Govde dik
```

#### Formul (Matematik)

```
vektor_A = omuz -> kulak yonu
vektor_B = dikey eksen (0, -1)  # yukari

cos(theta) = (A . B) / (|A| * |B|)
theta = arctan2(...)  # radyandan dereceye cevrilerek
```

### Kod Ornegi (core/posture_analyzer.py)

```python
# MediaPipe PoseLandmarker modelini yukle
self.landmarker = PoseLandmarker.create_from_options(options)

def analyze(self, frame_rgb, timestamp_ms):
    # Frame'i analiz et ve landmark'lari al
    result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

    if not result.pose_landmarks:
        return []  # Hicbir kisi tespit edilemedi

    for person_landmarks in result.pose_landmarks:
        # Omuz ve kulak noktalarini al
        left_shoulder = person_landmarks[11]
        left_ear = person_landmarks[7]
        left_hip = person_landmarks[23]

        # Boyun acisini hesapla
        neck_vec = (left_ear.x - left_shoulder.x, left_ear.y - left_shoulder.y)
        vertical = (0, -1)
        neck_angle = angle_between(neck_vec, vertical)  # derece cinsinden

        # Govde acisini hesapla
        torso_vec = (left_shoulder.x - left_hip.x, left_shoulder.y - left_hip.y)
        torso_angle = angle_between(torso_vec, vertical)

        # Iyi postur mu?
        is_good = (neck_angle < NECK_ANGLE_THRESHOLD and
                   torso_angle < TORSO_ANGLE_THRESHOLD)

        # Skor hesapla (0-100)
        # Boyun %70 agirlikli, govde %30 agirlikli
        neck_score = max(0, 100 - (neck_angle / NECK_ANGLE_THRESHOLD) * 100)
        torso_score = max(0, 100 - (torso_angle / TORSO_ANGLE_THRESHOLD) * 100)
        score = int(neck_score * 0.7 + torso_score * 0.3)
```

### Esik Degerleri (config.py)

```python
NECK_ANGLE_THRESHOLD = 25   # Boyun 25 dereceden fazla egilirse = kambur
TORSO_ANGLE_THRESHOLD = 15  # Govde 15 dereceden fazla egilirse = kambur
```

---

## 2. CALISMA / GOZ YONU TESPITI (Nasil Calisiyor?)

### Teori

Goz yonu tespiti **iki asamali** bir islemdir:

**Asama 1 - Yuz Tespiti (MediaPipe FaceLandmarker)**
MediaPipe FaceLandmarker modeli, yuz uzerinde 468 anahtar nokta tespit eder. Bunlardan 6 tanesi onemlidir:
- Burun ucu
- Cene
- Sol/sag goz dis kosesi
- Agiz kosesi (sol/sag)

**Asama 2 - 3D Bas Pozu Tahmini (OpenCV solvePnP)**
Bu 6 noktanin 2D goruntudeki piksel konumlari ile 3D yuz modelinin bilinen konumlari karsilastirilir. OpenCV'nin `solvePnP` fonksiyonu, kameranin yuz ile olan acisini hesaplar.

```
solvePnP Nasil Calisiyor?

   Bilinen: 3D yuz modeli koordinatlari (burun ucunun 3D pozisyonu vs.)
   Bilinen: 2D goruntudeki piksel koordinatlari (burun ucu goruntuDE nerede?)
   Bilinen: Kamera parametreleri (focal length, image center)

   Hesaplanan: Rotasyon vektoru (rvec) ve translasyon vektoru (tvec)

   rvec'ten Euler acilari cikarilir:
   - Pitch: Bas yukari/asagi egilme (X ekseni)
   - Yaw: Bas sola/saga dondurme (Y ekseni)
   - Roll: Bas yana yatirma (Z ekseni)
```

#### Calisma Durumu Karari

```
EGER |yaw| < 25 derece VE |pitch| < 20 derece:
    -> Kisi ekrana bakiyor = CALISIYOR
AKSI HALDE:
    -> Kisi baska yere bakiyor

ONEMLI - GECIKME MANTIGI (Hysteresis):
    Kisi ekrandan bakisini cevirince HEMEN "calismiyor" DEMIYORUZ.
    10 saniye bekliyoruz.

    Neden? Cunku kisi klavyeye, kagida veya yanindaki kisiye
    bir an icin bakabilir. Bu anlik bakislar "mola" sayilmamali.

    10 saniye boyunca surekli ekrana bakmiyorsa -> MOLA
    Tekrar ekrana bakarsa -> zamanlayici sifirlanir
```

### Kod Ornegi (core/gaze_analyzer.py)

```python
def analyze(self, frame_rgb, timestamp_ms):
    # Yuz landmark'larini tespit et
    result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

    if not result.face_landmarks:
        return []  # Yuz tespit edilemedi

    for face_landmarks in result.face_landmarks:
        # 6 referans noktasinin 2D koordinatlarini al
        image_points = np.array([
            [face_landmarks[1].x * w, face_landmarks[1].y * h],   # burun ucu
            [face_landmarks[152].x * w, face_landmarks[152].y * h], # cene
            [face_landmarks[33].x * w, face_landmarks[33].y * h],  # sol goz
            [face_landmarks[263].x * w, face_landmarks[263].y * h], # sag goz
            [face_landmarks[61].x * w, face_landmarks[61].y * h],  # agiz sol
            [face_landmarks[291].x * w, face_landmarks[291].y * h], # agiz sag
        ], dtype=np.float64)

        # 3D yuz modeli (sabit koordinatlar)
        model_points = np.array([
            (0.0, 0.0, 0.0),        # burun ucu
            (0.0, -330.0, -65.0),    # cene
            (-225.0, 170.0, -135.0), # sol goz
            (225.0, 170.0, -135.0),  # sag goz
            (-150.0, -150.0, -125.0),# agiz sol
            (150.0, -150.0, -125.0), # agiz sag
        ], dtype=np.float64)

        # Kamera matrisi (yaklasik)
        focal_length = w
        camera_matrix = np.array([
            [focal_length, 0, w/2],
            [0, focal_length, h/2],
            [0, 0, 1]
        ], dtype=np.float64)

        # PnP coz - rotasyon vektorunu bul
        success, rvec, tvec = cv2.solvePnP(
            model_points, image_points, camera_matrix, None
        )

        # Rotasyon vektorunu matrise cevir
        rotation_matrix, _ = cv2.Rodrigues(rvec)

        # Euler acilarini cikar
        pitch = math.atan2(rotation_matrix[2][1], rotation_matrix[2][2])
        yaw = math.atan2(-rotation_matrix[2][0],
                         math.sqrt(rotation_matrix[2][1]**2 + rotation_matrix[2][2]**2))

        # Radyandan dereceye cevir
        pitch_deg = math.degrees(pitch)
        yaw_deg = math.degrees(yaw)

        # Ekrana bakiyor mu?
        looking_at_screen = (abs(yaw_deg) < 25 and abs(pitch_deg) < 20)
```

### Gecikme Mantigi (person_tracker.py)

```python
def _compute_work_status(ps, gaze, now):
    if gaze is None or not gaze.looking_at_screen:
        # Ekrana bakmiyor
        if ps._not_looking_start is None:
            ps._not_looking_start = now  # Zamanlayici basla

        if now - ps._not_looking_start >= 10:  # 10 saniye gecti mi?
            return False  # Artik kesin calismiyor

        return ps.is_working  # Onceki durumu koru (henuz 10sn dolmadi)
    else:
        # Ekrana bakiyor - zamanlayiciyi sifirla
        ps._not_looking_start = None
        return True  # Calisiyor
```

---

## 3. COKLU KISI TAKIBI (Multi-Person Tracking)

### Teori

Ofis modunda birden fazla kisi ayni anda izlenebilir. Sorun su: MediaPipe her karede "su kadar kisi var" der ama **hangi kisinin hangisi oldugunu** soylemez. Yani 1. karede tespit edilen "Kisi A" ile 2. karede tespit edilen "Kisi A"nin ayni kisi oldugunu biz bulmamiz gerekir.

### Algoritma: Greedy Nearest-Neighbor (Acgozlu En Yakin Komsu)

```
ADIM 1: Her karedeki her kisinin agirlik merkezi (centroid) hesaplanir.
         Centroid = omuzlarin ve kalcalarin ortalama konumu

ADIM 2: Onceki karede bilinen kisilerin centroid'leri ile yeni karenin
         centroid'leri karsilastirilir.
         Her cift icin Oklid mesafesi hesaplanir.

ADIM 3: Tum ciftler mesafeye gore siralanir (en yakin ilk).
         En yakin ciftten baslayarak eslestirilir.
         Mesafe < 0.15 ise eslestir.

ADIM 4: Eslesmemis pose'lar = yeni kisi (max 6 kisi)

ADIM 5: 5 saniye boyunca gorunmeyen kisiler silinir.
```

### Kod Ornegi (core/person_tracker.py)

```python
class PersonTracker:
    def update(self, pose_results, gaze_results):
        now = time.time()

        # 1. Mesafe matrisi olustur
        pairs = []
        for pid, person in self._persons.items():
            for pi, pose in enumerate(pose_results):
                dist = distance(person.centroid, pose.centroid)
                pairs.append((dist, pid, pi))

        # 2. Mesafeye gore sirala
        pairs.sort()

        # 3. Acgozlu eslestirme
        used_persons = set()
        used_poses = set()
        matches = []

        for dist, pid, pi in pairs:
            if pid in used_persons or pi in used_poses:
                continue
            if dist < 0.15:  # Esik degeri
                matches.append((pid, pi))
                used_persons.add(pid)
                used_poses.add(pi)

        # 4. Yeni kisileri ekle
        for pi, pose in enumerate(pose_results):
            if pi not in used_poses:
                new_person = create_person(pose.centroid)
                matches.append((new_person.id, pi))

        # 5. Istatistikleri guncelle
        for pid, pi in matches:
            person = self._persons[pid]
            person.posture = pose_results[pi]
            person.is_working = compute_work_status(person, gaze, now)
            # Calisma/mola surelerini biriktir
            tick_stats(person, now)

        # 6. Kayip kisileri temizle
        expired = [pid for pid, p in self._persons.items()
                   if now - p.last_seen > 5.0]
        for pid in expired:
            del self._persons[pid]
```

---

## 4. VERITABANI YAPISI

### Teknoloji: SQLite3

SQLite dosya tabanli bir veritabanidir. Ayri bir sunucu gerektirmez, tek bir `db.sqlite3` dosyasinda tum veriler saklanir.

### Tablolar (Models)

```
CustomUser (Kullanici)
├── username     : Kullanici adi
├── password     : Sifreli sifre (hash)
├── role         : "yonetici" veya "calisan"
└── email        : E-posta (opsiyonel)

Room (Oda)
├── name         : Oda adi (orn: "Yazilim Ekibi")
├── code         : 6 haneli benzersiz kod (orn: "ABC123")
├── created_by   : Odayi olusturan yonetici (FK -> User)
├── is_active    : Oda aktif mi?
└── created_at   : Olusturulma tarihi

EmployeeSession (Calisan Oturumu)
├── user         : Calisan (FK -> User)
├── room         : Oda (FK -> Room)
├── started_at   : Baslangic zamani
├── ended_at     : Bitis zamani (null = hala aktif)
└── is_online    : Cevrimici mi?

PostureLog (Postur Kaydi)
├── session      : Oturum (FK -> EmployeeSession)
├── timestamp    : Zaman damgasi
├── neck_angle   : Boyun acisi (derece)
├── torso_angle  : Govde acisi (derece)
├── is_good      : Iyi postur mu?
└── score        : 0-100 arasi skor

WorkStatusLog (Calisma Durumu Kaydi)
├── session      : Oturum (FK -> EmployeeSession)
├── timestamp    : Zaman damgasi
├── is_working   : Calisiyor mu?
├── yaw          : Yatay bas acisi
└── pitch        : Dikey bas acisi

Warning (Uyari)
├── from_user    : Gonderen yonetici (FK -> User)
├── to_session   : Hedef oturum (FK -> EmployeeSession)
├── message      : Uyari mesaji
├── created_at   : Gonderilme zamani
└── is_read      : Okundu mu?

DailyStats (Gunluk Istatistikler)
├── user         : Calisan (FK -> User)
├── room         : Oda (FK -> Room)
├── date         : Tarih
├── work_seconds : Toplam calisma suresi (sn)
├── break_seconds: Toplam mola suresi (sn)
├── good_posture_seconds : Iyi postur suresi (sn)
└── bad_posture_seconds  : Kotu postur suresi (sn)
```

### Django ORM Nasil Calisiyor?

Django ORM (Object-Relational Mapping), Python siniflariyla veritabani tablolarini esler:

```python
# Model tanimlamak = Tablo olusturmak
class Room(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=6, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

# Veri kaydetmek
room = Room(name="Yazilim Ekibi", code="ABC123", created_by=user)
room.save()  # SQL: INSERT INTO room ...

# Veri sorgulamak
rooms = Room.objects.filter(created_by=user, is_active=True)
# SQL: SELECT * FROM room WHERE created_by_id=? AND is_active=1

# Veri guncellemek
room.is_active = False
room.save()  # SQL: UPDATE room SET is_active=0 WHERE id=?
```

---

## 5. WEBSOCKET BAGLANTISI

### Teori

Normal HTTP istek-yanit modelinde, istemci istekte bulunur ve sunucu yanitlar. Ama biz **gercek zamanli** veri aktarimi istiyoruz. WebSocket, iki yonlu (bidirectional) kalici bir baglanti kurar.

```
HTTP (Normal):
  Istemci ---istek---> Sunucu
  Istemci <--yanit---- Sunucu
  (Baglanti kapanir)

WebSocket (Gercek Zamanli):
  Istemci <=========> Sunucu
  (Baglanti acik kalir, her iki taraf istediginde veri gonderebilir)
```

### Django Channels

Django normalde sadece HTTP destekler. **Django Channels** eklentisi WebSocket destegi ekler.

```python
# routing.py - WebSocket URL'leri
websocket_urlpatterns = [
    path("ws/employee/<str:room_code>/", EmployeeConsumer.as_asgi()),
    path("ws/admin/<str:room_code>/", AdminConsumer.as_asgi()),
]

# consumers.py - WebSocket islemcisi
class EmployeeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Calisan baglandi
        self.room_code = self.scope["url_route"]["kwargs"]["room_code"]
        await self.channel_layer.group_add(
            f"room_{self.room_code}", self.channel_name
        )
        await self.accept()

    async def receive(self, text_data):
        # Calisandan veri geldi (postur, goz yonu vs.)
        data = json.loads(text_data)

        # Veritabanina kaydet
        await self.save_posture_log(data)

        # Admin'lere bildir
        await self.channel_layer.group_send(
            f"admin_{self.room_code}",
            {"type": "employee_status", "data": data}
        )

    async def disconnect(self, close_code):
        # Calisan baglantisi kesildi
        await self.channel_layer.group_discard(
            f"room_{self.room_code}", self.channel_name
        )
```

### Veri Akisi

```
1. Desktop Client kamerayi acar
2. Her frame'de AI analizi yapilir
3. Sonuclar JSON formatinda WebSocket ile sunucuya gonderilir:
   {
     "type": "status_update",
     "posture": {"neck_angle": 15.2, "torso_angle": 8.1, "is_good": true, "score": 85},
     "gaze": {"yaw": -5.3, "pitch": 3.1, "looking_at_screen": true, "is_working": true}
   }
4. Django Consumer bu veriyi alir:
   - PostureLog ve WorkStatusLog tablolarina kaydeder
   - DailyStats tablosunu gunceller
   - Admin WebSocket grubuna iletir
5. Admin tarayicisindaki JavaScript bu veriyi alir ve sayfayi canli gunceller
```

---

## 6. DESKTOP CLIENT (Istemci)

### Calisma Dongüsu

```python
# client/employee_client.py (basitlestirilmis)

async def main(server, room_code, username):
    # 1. Kamerayi ac
    camera = Camera(camera_index=0, width=640, height=480)

    # 2. AI modellerini yukle
    posture_analyzer = PostureAnalyzer(model_path="models/pose_landmarker_lite.task")
    gaze_analyzer = GazeAnalyzer(model_path="models/face_landmarker.task")
    tracker = PersonTracker(max_persons=6)

    # 3. WebSocket baglantisi kur
    ws = await websockets.connect(f"ws://{server}/ws/employee/{room_code}/")

    # 4. Ana dongu
    while True:
        frame = camera.read()
        if frame is None:
            continue

        # AI analizi
        timestamp = int(time.time() * 1000)
        pose_results = posture_analyzer.analyze(frame, timestamp)
        gaze_results = gaze_analyzer.analyze(frame, timestamp)
        persons = tracker.update(pose_results, gaze_results)

        # Sonuclari sunucuya gonder
        for pid, person in persons.items():
            data = {
                "type": "status_update",
                "posture": {
                    "neck_angle": person.posture.neck_angle if person.posture else 0,
                    "is_good": person.posture.is_good if person.posture else True,
                    "score": person.posture_score,
                },
                "gaze": {
                    "is_working": person.is_working,
                }
            }
            await ws.send(json.dumps(data))

        # ~15 FPS hiz
        await asyncio.sleep(0.066)
```

---

## 7. KONFIGURASYON DEGERLERI

```python
# config.py - Tum ayarlar

# Postur Tespiti
NECK_ANGLE_THRESHOLD = 25   # Boyun esik acisi (derece)
TORSO_ANGLE_THRESHOLD = 15  # Govde esik acisi (derece)
POSTURE_WARNING_DELAY = 10  # Kambur uyari gecikmesi (saniye)

# Goz Yonu / Calisma Tespiti
GAZE_YAW_THRESHOLD = 25     # Yatay bas donme esigi (derece)
GAZE_PITCH_THRESHOLD = 20   # Dikey bas egilme esigi (derece)
GAZE_STATUS_DELAY = 10      # Calisma durumu gecikme suresi (saniye)
                             # Kisi 10sn boyunca ekrana bakmiyorsa "mola" sayilir

# Coklu Kisi
MAX_PERSONS = 6              # Ayni anda max kisi
PERSON_DISAPPEAR_TIMEOUT = 5.0  # Kisi kaybolma suresi (saniye)
PERSON_MATCH_THRESHOLD = 0.15   # Eslestirme mesafe esigi

# Kamera
CAMERA_INDEX = 0       # Kamera indeksi (0 = varsayilan)
FRAME_WIDTH = 640      # Goruntu genisligi (piksel)
FRAME_HEIGHT = 480     # Goruntu yuksekligi (piksel)
```

---

## 8. PROJEYI GELISTIRMEK ICIN ONERILER

Projeye eklenebilecek ozellikler:

### Kolay Eklenebilir

1. **Mola Hatirlatici**: Belirli suredir calisan kisiye otomatik "mola ver" uyarisi
2. **Sesli Uyari**: Kambur oturma veya uzun sure calisma durumunda bip sesi
3. **Gunluk Rapor**: Her gun sonunda otomatik PDF/Excel rapor olusturma
4. **Tema Secimi**: Kullanicinin acik/koyu tema arasinda gecis yapabilmesi
5. **Profil Sayfasi**: Kullanicinin kendi bilgilerini gorup duzenleyebildigi sayfa

### Orta Zorluk

6. **Grafikler**: Dashboard'a Chart.js ile canli grafikler ekleme (anlik postur trendi)
7. **Bildirim Sistemi**: Tarayici push notification destegi
8. **Multi-Kamera**: Birden fazla kamerayi ayni anda kullanabilme
9. **Disa Aktarma**: Haftalik/aylik istatistikleri Excel'e aktarma
10. **Rol Bazli Erisim**: Farkli yonetici rolleri (super admin, takam lideri vs.)

### Ileri Seviye

11. **PostgreSQL**: SQLite yerine PostgreSQL veritabani (buyuk olcekli kullanim icin)
12. **Docker**: Projeyi Docker container ile paketleme
13. **REST API**: Mobil uygulama icin API endpoint'leri
14. **Makine Ogrenmesi**: Kisiye ozel postur modeli egitme
15. **Yuz Tanima**: Kisi tespitini yuz tanima ile yapma (centroid yerine)

---

## 9. KURULUM VE CALISTIRMA

### Gereksinimler

```
Python 3.10+
pip install -r requirements.txt
```

### requirements.txt Icerik

```
django>=5.0
channels>=4.0
daphne>=4.0
websockets>=12.0
opencv-python>=4.8.0
mediapipe>=0.10.9
numpy>=1.24.0
Pillow>=10.0.0
python-docx>=1.0.0
```

### Sunucuyu Baslatma

```bash
# 1. Veritabanini olustur
python manage.py migrate

# 2. Admin kullanici olustur
python manage.py createsuperuser

# 3. Sunucuyu baslat
daphne -b 0.0.0.0 -p 8000 officeguardian.asgi:application
```

### Istemciyi Baslatma

```bash
python client/employee_client.py --server 192.168.1.X:8000 --room ODA_KODU --user ADINIZ
```

---

## 10. DOSYA YAPISI OZETI

```
OfficeGuardian/
├── accounts/          # Kullanici giris/kayit sistemi
├── client/            # Desktop istemci (kamera + AI)
├── core/              # AI modulleri (postur, goz yonu, takip)
├── dashboard/         # Web dashboard (Django app)
├── data/              # Oturum verileri (JSON)
├── logs/              # Olay loglari (JSONL)
├── models/            # AI model dosyalari (MediaPipe)
├── officeguardian/    # Django proje ayarlari
├── static/            # CSS, JavaScript dosyalari
├── config.py          # Genel konfigürasyon
├── db.sqlite3         # SQLite veritabani
├── manage.py          # Django yonetim araci
└── requirements.txt   # Python bagimliliklari
```




  Kolay: Mola hatirlatici, sesli uyari, gunluk rapor, tema secimi, profil sayfasi

  Orta: Canli grafikler, bildirim sistemi, multi-kamera, Excel export, rol bazli erisim

  Ileri: PostgreSQL, Docker, REST API, ML ile kisisel model, yuz tanima