"""
================================================================================
                    OFFICEGUARDIAN - VERITABANI MODELLERI
================================================================================

Bu dosya, projenin tum veritabani modellerini (tablolarini) detayli olarak
aciklar. Django ORM (Object-Relational Mapping) kullanilarak Python siniflari
ile veritabani tablolari tanimlanir.

Proje 2 Django uygulamasi icerir:
  1. accounts/models.py  -> Kullanici modeli (CustomUser)
  2. dashboard/models.py -> Tum is mantigi modelleri

Veritabani: SQLite3 (dosya bazli, db.sqlite3)

================================================================================
BOLUM 1: CUSTOMUSER MODELI (accounts/models.py)
================================================================================

Django'nun yerlesik User modelini GENISLETIR (AbstractUser'dan turetilir).
Ek alanlar ekleyerek rol bazli yetkilendirme ve tema destegi saglar.

  CustomUser(AbstractUser):
    |------------------------------------------------------------|
    | Alan            | Tip          | Aciklama                  |
    |------------------------------------------------------------|
    | username        | CharField    | (AbstractUser'dan miras)   |
    | password        | CharField    | (AbstractUser'dan miras)   |
    | email           | EmailField   | (AbstractUser'dan miras)   |
    | first_name      | CharField    | (AbstractUser'dan miras)   |
    | last_name       | CharField    | (AbstractUser'dan miras)   |
    | role            | CharField    | Kullanici rolu (asagida)   |
    | theme           | CharField    | 'dark' veya 'light'        |
    | avatar_initial  | CharField    | Avatar bas harfi (max 2)   |
    | assigned_rooms  | ManyToMany   | Takim liderinin odalari    |
    |------------------------------------------------------------|

ROLLER:
  'super_admin'  -> Her seye erisim, kullanici yonetimi
  'yonetici'     -> Kendi odalarini yonetir, export yapar
  'takim_lideri' -> Atanan odalari gorur, oda olusturamaz
  'calisan'      -> Sadece kendi panelini gorur

YETKI METODLARI:
  is_super_admin()      -> role == 'super_admin'
  is_yonetici()         -> role in ('yonetici', 'super_admin')
  is_takim_lideri()     -> role == 'takim_lideri'
  is_calisan()          -> role == 'calisan'
  can_create_room()     -> super_admin veya yonetici
  can_delete_room()     -> super_admin veya yonetici
  can_send_warning()    -> super_admin, yonetici, takim_lideri
  can_view_logs()       -> super_admin, yonetici, takim_lideri
  can_export()          -> super_admin veya yonetici
  can_manage_users()    -> sadece super_admin

  get_accessible_rooms() -> Role gore erisilebilir odalari dondurur:
    - super_admin: Tum odalar
    - yonetici: Kendi olusturdugu odalar (Room.created_by filtresi)
    - takim_lideri: assigned_rooms (ManyToMany iliskisi)
    - calisan: Bos sorgu seti (Room.objects.none())

  get_initials() -> Avatar icin bas harfler (ad soyad veya username)

NEDEN ABSTRACTUSER?
  Django'nun varsayilan User modeli sinirlidir. AbstractUser kullanarak:
  - Mevcut tum alanlar korunur (username, password, email vb.)
  - Yeni alanlar eklenebilir (role, theme, assigned_rooms)
  - Dogrudan AUTH_USER_MODEL olarak atanir
  Not: settings.py'de AUTH_USER_MODEL = 'accounts.CustomUser' tanimlidir

ASSIGNED_ROOMS (ManyToManyField):
  Takim liderlerinin hangi odalara erisimi oldugunu belirler.
  ManyToMany iliskisi: Bir lider birden fazla odaya, bir oda birden fazla
  lidere atanabilir. Ara tablo Django tarafindan otomatik olusturulur.

  related_name='assigned_leaders' -> Room.assigned_leaders.all() ile
  bir odaya atanmis tum liderlere erisilir.

================================================================================
BOLUM 2: ROOM MODELI (dashboard/models.py)
================================================================================

Izleme odalari temsil eder. Her oda bir calisma grubu gibidir.

  Room:
    |------------------------------------------------------------|
    | Alan                   | Tip             | Aciklama         |
    |------------------------------------------------------------|
    | name                   | CharField(100)  | Oda adi          |
    | code                   | CharField(6)    | Benzersiz kod    |
    | created_by             | ForeignKey      | Olusturan yonet. |
    | is_active              | BooleanField    | Aktif mi?        |
    | created_at             | DateTimeField   | Olusturma tarihi |
    | break_reminder_enabled | BooleanField    | Mola hatirlatici |
    | break_work_minutes     | IntegerField    | Calisma suresi   |
    | break_rest_minutes     | IntegerField    | Mola suresi      |
    |------------------------------------------------------------|

ODA KODU URETIMI:
  generate_room_code() fonksiyonu 6 haneli benzersiz alfanumerik kod uretir.
  - Buyuk harfler + rakamlar: A-Z, 0-9
  - random.choices ile rastgele secilir
  - Benzersizlik garanti edilir (while dongusunde kontrol)
  - Ornek: "ABC123", "X7Y2Z9"

MOLA HATIRLATICI:
  Pomodoro teknigine benzer bir mola sistemi:
  - break_reminder_enabled: True ise aktif
  - break_work_minutes: Kac dakika calistiktan sonra mola (varsayilan: 25)
  - break_rest_minutes: Mola suresi (varsayilan: 5)
  - Bu ayarlar WebSocket uzerinden istemciye gonderilir

online_count() -> Odadaki cevrimici calisan sayisini dondurur
  EmployeeSession.filter(is_online=True).count()

================================================================================
BOLUM 3: EMPLOYEESESSION MODELI
================================================================================

Bir calisanin bir odaya baglanip ayrilmasini temsil eder.

  EmployeeSession:
    |------------------------------------------------------------|
    | Alan       | Tip           | Aciklama                      |
    |------------------------------------------------------------|
    | user       | ForeignKey    | Calisan (CustomUser)           |
    | room       | ForeignKey    | Oda (Room)                     |
    | started_at | DateTimeField | Baglanti zamani (auto)         |
    | ended_at   | DateTimeField | Ayrilma zamani (null olabilir) |
    | is_online  | BooleanField  | Su an bagli mi?                |
    |------------------------------------------------------------|

YASAM DONGUSU:
  1. Calisan WebSocket ile baglanir -> Yeni EmployeeSession olusur (is_online=True)
  2. Calisan bagli oldugu surece -> PostureLog ve WorkStatusLog kayitlari olusur
  3. Calisan ayrilir -> is_online=False, ended_at=simdi

BIR CALISANIN BIRDEN FAZLA OTURUMU OLABILIR:
  - Her baglanti yeni Session olusturur
  - Onceki aktif oturumlar kapatilir (is_online=False)
  - Gecmis oturumlar silinmez, istatistik icin saklanir

================================================================================
BOLUM 4: POSTURELOG VE WORKSTATUSLOG MODELLERI
================================================================================

Her saniye gelen veriler bu tablolara kaydedilir.

  PostureLog:
    |------------------------------------------------------------|
    | Alan        | Tip           | Aciklama                     |
    |------------------------------------------------------------|
    | session     | ForeignKey    | Ilgili oturum                |
    | timestamp   | DateTimeField | Zaman damgasi (auto)         |
    | neck_angle  | FloatField    | Boyun acisi (derece)         |
    | torso_angle | FloatField    | Govde acisi (derece)         |
    | is_good     | BooleanField  | Iyi postur mu?               |
    | score       | IntegerField  | 0-100 arasi skor             |
    |------------------------------------------------------------|

  WorkStatusLog:
    |------------------------------------------------------------|
    | Alan       | Tip           | Aciklama                      |
    |------------------------------------------------------------|
    | session    | ForeignKey    | Ilgili oturum                 |
    | timestamp  | DateTimeField | Zaman damgasi (auto)          |
    | is_working | BooleanField  | Calisiyor mu?                 |
    | yaw        | FloatField    | Sag-sol bakis acisi           |
    | pitch      | FloatField    | Yukari-asagi bakis acisi      |
    |------------------------------------------------------------|

VERI HACMI:
  Her calisan saniyede 1 PostureLog + 1 WorkStatusLog uretir.
  1 saatte: 3600 PostureLog + 3600 WorkStatusLog = 7200 kayit/kisi
  8 saatlik gunde: ~57600 kayit/kisi
  Bu yuzden log temizleme stratejisi gerekebilir (eski veriyi silme).

================================================================================
BOLUM 5: WARNING VE NOTIFICATION MODELLERI
================================================================================

  Warning (Uyari):
    |------------------------------------------------------------|
    | Alan        | Tip          | Aciklama                      |
    |------------------------------------------------------------|
    | from_user   | ForeignKey   | Gonderen (yonetici)           |
    | to_session  | ForeignKey   | Hedef oturum (calisan)        |
    | message     | CharField    | Uyari metni (max 500)         |
    | created_at  | DateTimeField| Gonderilme zamani             |
    | is_read     | BooleanField | Calisan okudu mu?             |
    |------------------------------------------------------------|

  Notification (Bildirim):
    |------------------------------------------------------------|
    | Alan         | Tip          | Aciklama                     |
    |------------------------------------------------------------|
    | user         | ForeignKey   | Bildirim sahibi (yonetici)   |
    | notif_type   | CharField    | Bildirim tipi (asagida)      |
    | title        | CharField    | Baslik (max 200)             |
    | message      | CharField    | Icerik (max 500)             |
    | is_read      | BooleanField | Okundu mu?                   |
    | created_at   | DateTimeField| Olusturma zamani             |
    | related_room | ForeignKey   | Ilgili oda (opsiyonel)       |
    |------------------------------------------------------------|

  BILDIRIM TIPLERI:
    'warning'  -> Postur uyarisi (skor dusuk)
    'info'     -> Genel bilgi
    'success'  -> Basarili islem
    'system'   -> Sistem mesaji
    'posture'  -> Postur uyarisi (skor < 30)
    'connect'  -> Baglanti bildirimi (katildi/ayrildi)

FARK: Warning vs Notification
  - Warning: Yonetici -> Calisan yonunde, WebSocket ile canli iletilir
  - Notification: Sistem -> Yonetici yonunde, AJAX polling ile cekilir
  - Warning calisanin ekraninda popup olarak gosterilir
  - Notification web panelinde bildirim zili ile gosterilir

================================================================================
BOLUM 6: PERSONALMODEL VE FACEENCODING MODELLERI
================================================================================

  PersonalModel: Kisisel kalibrasyon verileri (06_ML_KISISEL_MODEL.py'de detayli)
  FaceEncoding: Yuz tanima verileri (07_YUZ_TANIMA.py'de detayli)

  Bu modeller OneToOneField kullanir:
  - Her kullanici icin EN FAZLA BIR kayit olabilir
  - user.personal_model ile dogrudan erisilebilir
  - Kalibrasyon yapildiginda guncellenir, yeni kayit olusmaz

================================================================================
BOLUM 7: DAILYSTATS MODELI
================================================================================

Gunluk toplam istatistikleri icerir. PostureLog ve WorkStatusLog'un
ozeti gibidir ama cok daha verimli sorgulanir.

  DailyStats:
    |------------------------------------------------------------|
    | Alan                  | Tip        | Aciklama              |
    |------------------------------------------------------------|
    | user                  | ForeignKey | Calisan               |
    | room                  | ForeignKey | Oda                   |
    | date                  | DateField  | Tarih                 |
    | work_seconds          | FloatField | Toplam calisma (sn)   |
    | break_seconds         | FloatField | Toplam mola (sn)      |
    | good_posture_seconds  | FloatField | Iyi postur (sn)       |
    | bad_posture_seconds   | FloatField | Kotu postur (sn)      |
    |------------------------------------------------------------|

  unique_together = ['user', 'room', 'date']
  -> Ayni kullanici, ayni oda, ayni gun icin TEK kayit
  -> get_or_create ile ya olusturulur ya guncellenir

  HESAPLANAN OZELLIKLER (@property):
    total_seconds   -> work + break toplami
    posture_score   -> (good / (good + bad)) * 100  (0-100)
    work_ratio      -> (work / total) * 100  (%calisma orani)

  NEDEN AYRI MODEL?
    - PostureLog'dan gunluk skoru hesaplamak binlerce kaydi okumak demek
    - DailyStats tek satir okuma ile tum gunluk ozeti verir
    - Raporlama, grafik ve export islemleri icin cok daha hizli

================================================================================
ENTITY-RELATIONSHIP DIYAGRAMI (ILISKILER)
================================================================================

  CustomUser ----1:N----> Room (created_by)
  CustomUser ----M:N----> Room (assigned_rooms) [takim liderleri icin]
  CustomUser ----1:N----> EmployeeSession (user)
  CustomUser ----1:1----> PersonalModel (user)
  CustomUser ----1:1----> FaceEncoding (user)
  CustomUser ----1:N----> DailyStats (user)
  CustomUser ----1:N----> Notification (user)
  CustomUser ----1:N----> Warning (from_user)

  Room -----------1:N----> EmployeeSession (room)
  Room -----------1:N----> DailyStats (room)
  Room -----------1:N----> Notification (related_room)

  EmployeeSession -1:N----> PostureLog (session)
  EmployeeSession -1:N----> WorkStatusLog (session)
  EmployeeSession -1:N----> Warning (to_session)

  1:N = Bir-Cok, M:N = Cok-Cok, 1:1 = Bir-Bir

================================================================================
DOSYA KONUMLARI
================================================================================

  accounts/models.py   -> CustomUser
  dashboard/models.py  -> Room, EmployeeSession, PostureLog, WorkStatusLog,
                          Warning, Notification, PersonalModel, FaceEncoding,
                          DailyStats

================================================================================
"""
