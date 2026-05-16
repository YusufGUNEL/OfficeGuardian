"""
================================================================================
                    OFFICEGUARDIAN - DJANGO VIEWS VE API ENDPOINTLERI
================================================================================

Bu dosya, projedeki tum Django view'larini (sayfa ve API endpoint'lerini)
detayli olarak aciklar. views.py dosyalari HTTP isteklerini karsilayip
uygun yaniti (HTML sayfa, JSON, dosya indirme vb.) dondurur.

Proje 2 uygulamada view'lar icerir:
  1. accounts/views.py   -> Kimlik dogrulama (login, register, profil)
  2. dashboard/views.py  -> Tum is mantigi (panel, odalar, loglar, API'ler)

================================================================================
BOLUM 1: ACCOUNTS VIEWS (accounts/views.py)
================================================================================

1. CustomLoginView
   URL: /accounts/login/
   Yontem: GET (formu goster) + POST (giris yap)
   Tur: Django'nun LoginView sinifini genisletir
   Islem:
     - LoginForm kullanarak kullanici adi + sifre alir
     - Basarili giriste 'next' parametresine veya ana sayfaya yonlendirir
     - Basarisiz giriste hata mesaji gosterir

2. RegisterView
   URL: /accounts/register/
   Yontem: GET + POST
   Tur: Class-Based View
   Islem:
     - RegisterForm ile yeni kullanici olusturur
     - Kullanici adi, sifre ve rol (calisan/yonetici vb.) alir
     - Basarili kayitta otomatik giris yapar ve ana sayfaya yonlendirir

3. logout_view
   URL: /accounts/logout/
   Yontem: GET
   Islem: Oturumu kapatir, login sayfasina yonlendirir

4. toggle_theme
   URL: /accounts/toggle-theme/
   Yontem: POST (AJAX)
   Islem:
     - JSON body'den tema degerini alir ('dark' veya 'light')
     - Kullanicinin theme alanini gunceller
     - Tarayici sayfayi yenilemeden tema degisir

5. profile_view
   URL: /accounts/profile/
   Yontem: GET + POST
   Islem:
     - Profil bilgilerini goster/guncelle (ad, soyad, email)
     - Sifre degistirme formu (eski sifre + yeni sifre)
     - 'action' parametresine gore hangi formu isledigini belirler:
       * 'update_profile' -> ProfileForm
       * 'change_password' -> PasswordChangeCustomForm
     - update_session_auth_hash: sifre degistikten sonra oturumu korur

================================================================================
BOLUM 2: FORMLAR (accounts/forms.py)
================================================================================

Django form siniflari, HTML formlarini Python ile tanimlar.
Dogrulama (validation) ve HTML olusturma isini otomatik yaparlar.

  LoginForm (AuthenticationForm turetmesi):
    - username + password alanlari
    - Bootstrap class'lari ile stillendirilmis widget'lar
    - Placeholder text ile kullanici yonlendirmesi

  RegisterForm (UserCreationForm turetmesi):
    - username, password1, password2, role alanlari
    - role alani: ChoiceField (dropdown ile rol secimi)
    - Sifre dogrulama: Django'nun yerlesik validatorleri
    - __init__ metodu: widget'lara CSS class'lari ekler

  ProfileForm (ModelForm):
    - first_name, last_name, email alanlari
    - Koyu tema uyumlu stil (bg-dark text-light)

  PasswordChangeCustomForm (PasswordChangeForm turetmesi):
    - old_password, new_password1, new_password2
    - Koyu tema uyumlu stil

================================================================================
BOLUM 3: DASHBOARD VIEWS - SAYFA VIEWS'LARI (dashboard/views.py)
================================================================================

Sayfa view'lari HTML template render eder ve GET/POST isteklerini isler.
Hepsi @login_required dekoratoru ile korunur.

1. index (Ana Sayfa)
   URL: /
   Islem: Kullanici rolune gore yonlendirme:
     - super_admin, yonetici, takim_lideri -> /dashboard/ (admin paneli)
     - calisan -> /panel/ (calisan paneli)

2. admin_dashboard (Canli Izleme)
   URL: /dashboard/
   Islem:
     a) Kullanicinin erisebilecegi odalari al (get_accessible_rooms)
     b) URL parametresinden secili odayi belirle (?room=ABC123)
     c) Secili odadaki aktif oturumlari getir (is_online=True)
     d) admin_dashboard.html template'ini render et
   Context: rooms, selected_room, online_sessions

3. room_manage (Oda Yonetimi)
   URL: /rooms/
   Yontem: GET + POST
   GET: Odalari listele (erisim yetkisine gore)
   POST: Yeni oda olustur
     - Oda adi al
     - Mola hatirlatici ayarlarini al (break_reminder_*)
     - Room.objects.create() ile kaydet
     - room_manage sayfasina yonlendir

4. room_toggle (Oda Aktif/Pasif)
   URL: /rooms/<room_id>/toggle/
   Yontem: POST
   Islem: is_active alanini tersine cevir (True <-> False)

5. room_delete (Oda Silme)
   URL: /room/<room_id>/delete/
   Yontem: POST
   Islem: Odayi veritabanindan sil (CASCADE ile iliskili kayitlar da silinir)
   Yetki: can_delete_room() kontrolu

6. employee_detail (Calisan Detay)
   URL: /employee/<username>/
   Islem:
     - Calisanin son 7 gunluk istatistiklerini getir (DailyStats)
     - Son oturumlarini getir (EmployeeSession, son 10)
     - Grafik verileri hazirla (gunluk postur skorlari, calisma sureleri)
   Context: employee, stats, sessions, chart_data

7. logs_view (Log Goruntuleme)
   URL: /logs/
   Islem:
     - Filtreleme: tarih araligi, kullanici, oda, tip (postur/calisma)
     - PostureLog ve WorkStatusLog sorgulari
     - Sonuclari zaman sirasina gore sirala
     - Sayfalama (pagination) ile goster
   Context: logs, filters, rooms

8. employee_panel (Calisan Paneli)
   URL: /panel/
   Islem:
     - Calisanin kendi istatistiklerini goster
     - Son 7 gunluk DailyStats verileri
     - Okunmamis uyarilar (Warning.filter(is_read=False))
     - Bugunun ozet bilgileri (calisma suresi, postur skoru)
   Context: today_stats, weekly_stats, warnings, recent_alerts

9. daily_report (Gunluk Rapor)
   URL: /daily-report/
   Islem:
     - Secilen tarih icin tum calisanlarin istatistikleri
     - Her calisan icin: postur skoru, calisma orani, toplam sure
     - Siralamayla goster (en yuksek skordan en dusuge)
   Context: stats, date, rooms

10. user_manage (Kullanici Yonetimi)
    URL: /users/
    Yontem: GET + POST
    Yetki: Sadece super_admin
    GET: Tum kullanicilari listele (roller, atanmis odalar)
    POST: Kullanici rolunu degistir ve oda ata
      - Rol degistirme: request.POST['role_<user_id>']
      - Oda atama: request.POST.getlist('rooms_<user_id>')

11. join_room (Odaya Katilma)
    URL: /join/
    Yontem: GET + POST
    Islem:
      - Oda kodu ile odaya katilma formu
      - Basarili katilimda: komut gosterir (python client/...)
      - ZIP indirme linki sunar
      - Login gerektirmez (anonim erisim)

================================================================================
BOLUM 4: DASHBOARD VIEWS - DOSYA INDIRME
================================================================================

12. download_launcher (Baslatici Indirme)
    URL: /room/<room_code>/launcher/
    Yetki: @login_required
    Islem:
      - Odaya ozel .bat dosyasi olusturur
      - BAT icerigi: python client/employee_client.py --server ... --room ... --user ...
      - @chcp 65001 >nul ile Turkce karakter destegi
      - BAT dosyasini ZIP icine paketler (guvenlik engellerini asmak icin)
      - ZIP'i HTTP response olarak dondurur

13. download_client_script (Anonim Script Indirme)
    URL: /download-script/?room=ABC123&user=AhmetYilmaz
    Yetki: Login GEREKMEZ
    Islem:
      - URL parametrelerinden oda kodu ve kullanici adini alir
      - Ayni sekilde BAT -> ZIP olusturur ve indirir
      - join_room sayfasindan cagrilir

================================================================================
BOLUM 5: DASHBOARD VIEWS - EXPORT (DISA AKTARIM)
================================================================================

14. export_csv (CSV Disa Aktarim)
    URL: /export/
    Yetki: can_export() kontrolu
    Islem:
      - Tarih araligini filtrele
      - DailyStats verilerini CSV formatina cevir
      - CSV kolonlari: Kullanici, Oda, Tarih, Calisma, Mola, Iyi Postur,
        Kotu Postur, Postur Skoru
      - HttpResponse ile dosya olarak indir

15. export_excel (Excel Disa Aktarim)
    URL: /export-excel/
    Yetki: can_export() kontrolu
    Islem:
      - openpyxl kutuphanesi ile .xlsx dosyasi olusturur
      - COKLU SHEET yapisi:
        Sheet 1 "Gunluk Istatistikler": DailyStats verileri
        Sheet 2 "Postur Loglari": PostureLog detaylari
        Sheet 3 "Calisma Loglari": WorkStatusLog detaylari
      - Formatli basliklar (arka plan rengi, kalin yazi)
      - Otomatik kolon genisligi (auto_width)
      - BytesIO ile bellekte olusturup HTTP response olarak dondurur

    Yardimci fonksiyonlar (ic icekapanma):
      style_header(ws, headers): Baslik satirini formatlar
      auto_width(ws): Kolon genisliklerini iceriye gore ayarlar

================================================================================
BOLUM 6: DASHBOARD VIEWS - API ENDPOINTLERI
================================================================================

Bu endpointler JSON dondurur ve AJAX/istemci tarafindan kullanilir.

16. notifications_api (Bildirim Listesi)
    URL: /api/notifications/
    Yontem: GET
    Islem: Okunmamis bildirimleri JSON olarak dondur
    Donus: [{id, type, title, message, created_at, is_read}, ...]

17. notifications_read (Tumu Okundu)
    URL: /api/notifications/read-all/
    Yontem: POST
    Islem: Kullanicinin tum bildirimlerini okundu isaretle

18. notification_read_single (Tek Okundu)
    URL: /api/notifications/<notif_id>/read/
    Yontem: POST
    Islem: Belirtilen bildirimi okundu isaretle

19. api_personal_model (Kisisel Model Sorgula)
    URL: /api/personal-model/<username>/
    Yontem: GET
    Islem:
      - Kullanicinin PersonalModel kaydini sorgula
      - Yoksa varsayilan degerlerle yeni kayit olustur (get_or_create)
      - Kalibrasyon durumu ve esik degerlerini JSON olarak dondur
    Donus: {is_calibrated, neck_threshold, torso_threshold, yaw_threshold,
            pitch_threshold, calibration_samples}
    Kullanici: Masaustu istemci (employee_client.py)

20. api_calibration_save (Kalibrasyon Kaydet)
    URL: /api/calibration/save/
    Yontem: POST
    Islem:
      - Istemciden gelen kalibrasyon verilerini al
      - PersonalModel'i guncelle (mean, std degerleri)
      - calculate_thresholds() ile esikleri hesapla
      - is_calibrated = True olarak isaretle
    Body: {username, neck_angle_mean, neck_angle_std, ...}
    Kullanici: Masaustu istemci (kalibrasyon sonrasi)

21. api_face_register (Yuz Kaydi)
    URL: /api/face/register/
    Yontem: POST
    Islem:
      - Base64 ile encode edilmis yuz encoding verisi alir
      - bytes'a cevirerek FaceEncoding modeline kaydeder
      - Mevcut kayit varsa gunceller (update_or_create)
    Body: {username, encoding}

22. api_face_encodings (Oda Yuz Verileri)
    URL: /api/face/encodings/<room_code>/
    Yontem: GET
    Islem:
      - Belirtilen odadaki aktif oturumlarin kullanicilarinin
        yuz encodinglerini dondurur
      - Her encoding base64 ile encode edilerek JSON'da gonderilir
    Donus: {username1: base64_encoding, username2: base64_encoding, ...}
    Kullanici: Masaustu istemci (yuz tanima eslestirmesi icin)

23. get_active_rooms (Aktif Odalar)
    URL: /api/active-rooms/
    Yontem: GET
    Yetki: Login GEREKMEZ
    Islem: Aktif odalarin listesini JSON olarak dondur
    Donus: [{name, code}, ...]
    Kullanici: Masaustu istemci (oda secimi icin)

================================================================================
URL YAPILANDIRMASI (dashboard/urls.py)
================================================================================

app_name = 'dashboard'  -> Isimlendirme icin namespace

Tum URL'ler bu dosyada tanimlanir. Django, gelen URL'yi sirayla
bu listeyle eslestirir ve ilk eslesen view'i calistirir.

Onemli URL kaliplari:
  ''                              -> index (ana sayfa)
  'dashboard/'                    -> admin_dashboard
  'rooms/'                        -> room_manage
  'rooms/<int:room_id>/toggle/'   -> room_toggle
  'employee/<str:username>/'      -> employee_detail
  'logs/'                         -> logs_view
  'export/'                       -> export_csv
  'export-excel/'                 -> export_excel
  'panel/'                        -> employee_panel
  'join/'                         -> join_room
  'daily-report/'                 -> daily_report
  'users/'                        -> user_manage
  'api/notifications/'            -> notifications_api
  'api/personal-model/<username>/'-> api_personal_model
  'api/calibration/save/'         -> api_calibration_save
  'api/face/register/'            -> api_face_register
  'api/face/encodings/<code>/'    -> api_face_encodings
  'api/active-rooms/'             -> get_active_rooms

================================================================================
DEKORATOR ACIKLAMALARI
================================================================================

@login_required:
  Kullanici giris yapmamissa LOGIN_URL'ye yonlendirir.
  Cogu view'da kullanilir. API'lerde bazen kaldirilir (anonim erisim).

@require_POST:
  Sadece POST isteklerini kabul eder. GET ile erisim 405 hatasi dondurur.
  Degisiklik yapan view'larda guvenlik icin kullanilir.

@database_sync_to_async:
  WebSocket consumer'larinda kullanilir (views.py'de degil).
  Senkron Django ORM cagrilarini asenkron ortamda calistirir.

================================================================================
DOSYA KONUMLARI
================================================================================

  accounts/views.py     -> Kimlik dogrulama view'lari
  accounts/forms.py     -> Form siniflari
  accounts/urls.py      -> Hesap URL tanimlari
  dashboard/views.py    -> Tum is mantigi view'lari (27 fonksiyon)
  dashboard/urls.py     -> Dashboard URL tanimlari

================================================================================
"""
