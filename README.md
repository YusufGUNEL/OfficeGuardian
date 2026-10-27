# OfficeGuardian

Yapay zeka destekli postür ve dikkat analizi ile çalışan sağlığını ve verimliliğini izleyen bir Django + Python istemci uygulamasıdır. Sistem, standart bir web kamerası üzerinden gerçek zamanlı olarak çalışır; herhangi bir giyilebilir sensöre ihtiyaç duymaz.

## İçindekiler

- [Özellikler](#özellikler)
- [Mimari](#mimari)
- [Gereksinimler](#gereksinimler)
- [Kurulum](#kurulum)
- [Kullanım](#kullanım)
- [Yapılandırma](#yapılandırma)
- [Roller ve Yetkiler](#roller-ve-yetkiler)
- [API Uç Noktaları](#api-uç-noktaları)
- [Proje Yapısı](#proje-yapısı)
- [Geliştirme Notları](#geliştirme-notları)
- [Lisans](#lisans)

## Özellikler

- Gerçek zamanlı postür analizi (boyun ve gövde açıları, MediaPipe Pose).
- Bakış ve dikkat analizi (yaw / pitch açıları, MediaPipe FaceMesh + OpenCV solvePnP).
- Kişisel mod (tek kullanıcı) ve ofis modu (aynı anda birden fazla kişi takibi).
- Kişiye özel kalibrasyon (kullanıcının doğal duruş profili öğrenilerek kişisel eşik değerleri üretilir).
- Yüz tanıma (MediaPipe landmark tabanlı, kullanıcıyı odadaki diğer kişilerden ayırt eder).
- Yönetici paneli üzerinden canlı izleme, anlık uyarı gönderme ve oda yönetimi.
- WebSocket (Django Channels) ile düşük gecikmeli istemci–sunucu iletişimi.
- Günlük istatistik kaydı (çalışma süresi, mola süresi, postür skoru, verimlilik oranı).
- Pomodoro tarzı mola hatırlatıcısı (oda bazında ayarlanabilir).
- CSV ve Excel (çoklu sheet, biçimlendirilmiş) rapor dışa aktarımı.
- Rol bazlı yetkilendirme (Süper Admin / Yönetici / Takım Lideri / Çalışan).
- Bildirim sistemi (bağlantı, düşük postür, uyarı, sistem mesajları).

## Mimari

```
[Çalışan PC]                                  [Sunucu]
+----------------------+   WebSocket / HTTP   +-----------------------+
| client/employee_*.py | <------------------> | Django + Channels     |
| - OpenCV kamera      |                      | - dashboard (app)     |
| - MediaPipe analiz   |                      | - accounts (app)      |
| - Yerel kalibrasyon  |                      | - SQLite veritabanı   |
+----------------------+                      | - WebSocket consumers |
                                              +-----------------------+
                                                        |
                                                        v
                                              +-----------------------+
                                              | Yönetici tarayıcısı    |
                                              | (canlı izleme paneli) |
                                              +-----------------------+
```

İstemci kamerayı yerel olarak işler; sunucuya yalnızca sayısal sonuçlar (açılar, skorlar, durum bilgisi) gönderilir. Görüntü hiçbir zaman ağa çıkmaz.

## Gereksinimler

- Python 3.10 veya üzeri
- Web kamerası (dahili, USB veya DroidCam gibi sanal kamera)
- Windows 10/11, Linux veya macOS

Ana bağımlılıklar (`requirements.txt`):

- Django >= 5.0
- channels >= 4.0
- daphne >= 4.0
- websockets >= 12.0
- opencv-python >= 4.8.0
- mediapipe >= 0.10.9
- numpy >= 1.24.0
- Pillow >= 10.0.0
- python-docx >= 1.0.0
- openpyxl >= 3.1.0
- customtkinter >= 5.2.0 (GUI istemcisi)
- requests >= 2.31.0 (istemci)

## Kurulum

1. Depoyu klonlayın:

   ```bash
   git clone https://github.com/<kullanici>/OfficeGuardian.git
   cd OfficeGuardian
   ```

2. Sanal ortam oluşturun ve etkinleştirin:

   Windows:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

   Linux / macOS:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Bağımlılıkları yükleyin:

   ```bash
   pip install -r requirements.txt
   ```

4. MediaPipe model dosyalarını indirin (yaklaşık 10 MB):

   ```bash
   python setup_models.py
   ```

   Bu komut `models/pose_landmarker_lite.task` ve `models/face_landmarker.task` dosyalarını otomatik indirir.

5. Veritabanını hazırlayın:

   ```bash
   python manage.py migrate
   ```

6. Yönetici (süper admin) hesabı oluşturun:

   ```bash
   python manage.py createsuperuser
   ```

   Oluşturulan hesabı Django admin (`/admin/`) üzerinden açıp `role` alanını `super_admin` yapın.

## Kullanım

### Sunucuyu Başlatma

```bash
python manage.py runserver 0.0.0.0:8000
```

Sunucu hem HTTP (yönetici paneli) hem WebSocket (istemci bağlantısı) trafiğini aynı portta karşılar (Daphne / Channels üzerinden).

Tarayıcıdan açın:

- Yönetici / takım lideri paneli: `http://localhost:8000/`
- Django admin: `http://localhost:8000/admin/`

### Çalışan İstemcisini Çalıştırma

Çalışan kendi makinesinde projeyi indirip aşağıdaki komutu çalıştırır:

```bash
python client/employee_client.py --server <sunucu-adresi:port> --room <ODA-KODU> --user <kullanici-adi> --mode personal
```

Parametreler:

- `--server` : Django sunucusunun adresi (örn. `192.168.1.10:8000`).
- `--room`   : 6 karakterli oda kodu (yönetici panelinden alınır).
- `--user`   : Sistemde kayıtlı kullanıcı adı.
- `--mode`   : `personal` (tek kişi) veya `office` (aynı kamerada birden çok kişi).
- `--camera` : Kamera indeksi (varsayılan `0`).

Yönetici paneli üzerinden her odaya özel hazır `.bat` başlatıcı dosyası da indirilebilir; bu dosya yukarıdaki komutu otomatik çalıştırır.

İlk bağlantıda istemci 15 saniyelik bir kalibrasyon süreci yürütür ve kullanıcıya özel postür / bakış eşiklerini sunucuya kaydeder.

## Yapılandırma

### Çevre Değişkenleri (Üretim İçin)

Geliştirme dışında aşağıdaki değişkenler tanımlanmalıdır:

| Değişken | Açıklama | Örnek |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django gizli anahtarı | `<50+ karakterli rastgele dize>` |
| `DJANGO_DEBUG` | Hata ayıklama modu | `False` |
| `DJANGO_ALLOWED_HOSTS` | İzin verilen hostlar (virgülle) | `example.com,192.168.1.10` |

### Analiz Eşik Değerleri (`config.py`)

| Ayar | Varsayılan | Açıklama |
|---|---|---|
| `NECK_ANGLE_THRESHOLD` | 25 | Boyun öne eğilme eşiği (derece) |
| `TORSO_ANGLE_THRESHOLD` | 15 | Gövde eğilme eşiği (derece) |
| `POSTURE_WARNING_DELAY` | 10 | Kambur uyarısı gecikmesi (sn) |
| `GAZE_YAW_THRESHOLD` | 25 | Baş dönüş açısı eşiği |
| `GAZE_PITCH_THRESHOLD` | 20 | Baş eğilme açısı eşiği |
| `GAZE_STATUS_DELAY` | 10 | Bakış durum değişimi gecikmesi (sn) |
| `MAX_PERSONS` | 6 | Ofis modunda aynı anda izlenecek azami kişi |
| `PERSON_DISAPPEAR_TIMEOUT` | 5.0 | Kişi listeden düşmeden önce beklenen süre (sn) |

Kalibrasyon yapılan kullanıcılarda bu genel eşikler yerine kişisel eşikler kullanılır.

## Roller ve Yetkiler

| Rol | Oda Oluştur | Oda Sil | Uyarı Gönder | Log Görüntüle | CSV/Excel Dışa Aktar | Kullanıcı Yönetimi |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Süper Admin | + | + | + | + | + | + |
| Yönetici | + | + | + | + | + | - |
| Takım Lideri | - | - | + | + | - | - |
| Çalışan | - | - | - | - | - | - |

Takım lideri yalnızca kendisine atanmış odaları görür. Yönetici yalnızca kendisinin oluşturduğu odaları görür. Süper admin tüm odalara erişebilir.

## API Uç Noktaları

İstemcinin kullandığı temel uç noktalar:

| Yöntem | Yol | Açıklama |
|---|---|---|
| GET | `/api/personal-model/<username>/` | Kullanıcının kalibrasyon verilerini döner. |
| POST | `/api/calibration/save/` | Yeni kalibrasyon kayıt eder (CSRF muaf). |
| POST | `/api/face/register/` | Yüz landmark verisini kaydeder (CSRF muaf). |
| GET | `/api/face/encodings/<room_code>/` | Bir odadaki kayıtlı yüz verilerini döner. |
| GET | `/api/active-rooms/` | Aktif oda listesi. |
| GET | `/api/notifications/` | Oturum açmış kullanıcının bildirimleri (oturum gerektirir). |

WebSocket adresleri (`dashboard/routing.py`):

- `ws://<host>/ws/employee/<room_code>/<username>/`
- `ws://<host>/ws/admin/<room_code>/`

## Proje Yapısı

```
OfficeGuardian/
├── accounts/                 # Kullanıcı, rol ve kimlik doğrulama modülü
├── client/                   # Çalışan istemci uygulaması
│   ├── employee_client.py    # CLI istemcisi (WebSocket + OpenCV)
│   └── employee_gui.py       # CustomTkinter GUI istemcisi
├── core/                     # Görüntü işleme çekirdeği
│   ├── camera.py             # Thread güvenli kamera yöneticisi
│   ├── posture_analyzer.py   # MediaPipe Pose analizi
│   ├── gaze_analyzer.py      # MediaPipe FaceMesh + solvePnP
│   ├── person_tracker.py     # Çoklu kişi takip algoritması
│   ├── session_tracker.py    # Oturum süresi ve istatistikleri
│   └── event_logger.py       # JSONL formatında olay kayıtçısı
├── dashboard/                # Yönetici paneli, WebSocket consumer'ları
├── officeguardian/           # Django proje ayarları (settings, urls, asgi)
├── static/                   # CSS ve JS dosyaları
├── models/                   # MediaPipe model dosyaları (setup_models.py ile inilir)
├── data/                     # Çalışma zamanında oluşturulan veri dosyaları
├── logs/                     # JSONL olay günlükleri
├── config.py                 # Analiz eşik değerleri ve UI sabitleri
├── manage.py                 # Django yönetim komutu
├── setup_models.py           # MediaPipe modellerini indirir
├── create_report.py          # DOCX teknik rapor üretir
└── requirements.txt
```

## Geliştirme Notları

- Tüm görüntü işleme istemci tarafında yapılır; sunucuya yalnızca sayısal veriler iletilir, bu da bant genişliğini ve mahremiyet riskini düşürür.
- WebSocket katmanı geliştirme için `InMemoryChannelLayer` kullanır. Birden fazla worker / dağıtık kurulum için Redis tabanlı katmana geçilmesi önerilir.
- `db.sqlite3` ve `models/*.task` dosyaları kullanıcı makinesinde oluşur; depoya dâhil edilmemelidir (bkz. `.gitignore`).
- Kalibrasyon veri toplama eşiği 10 örnektir; yetersiz örnek olursa kişisel eşikler kaydedilmez ve genel `config.py` değerleri kullanılmaya devam eder.
- Excel raporu dört sheet üretir: Günlük İstatistikler, Postür Logları, Çalışma Logları ve Özet.

## Lisans

Bu proje akademik / eğitim amaçlı olarak geliştirilmiştir. Ticari kullanım için lütfen proje sahibiyle iletişime geçin.
