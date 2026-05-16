"""
================================================================================
                    OFFICEGUARDIAN - DASHBOARD JAVASCRIPT
================================================================================

Bu dosya, yonetici panelindeki canli guncelleme, grafik ve kullanici
etkilesim islemlerini yoneten JavaScript kodlarini detayli aciklar.

Ana dosya: static/js/dashboard.js (389 satir)

Bu JS dosyasi admin_dashboard.html sayfasinda yuklenir ve su isleri yapar:
  1. WebSocket baglantisi kurar ve yonetir
  2. Gelen gercek zamanli verileri arayuze yansitir
  3. Chart.js ile canli grafikler olusturur ve gunceller
  4. Uyari gonderme islemini yonetir

================================================================================
BOLUM 1: GLOBAL DEGISKENLER
================================================================================

  let ws = null;
    WebSocket baglanti nesnesi. Sayfa boyunca tek bir baglanti kullanilir.
    Baglanti koptiginda null olur, yeniden baglantida yeni nesne atanir.

  let warningTarget = null;
    Uyari gonderilecek calisanin kullanici adi. Uyari modali acildiginda
    set edilir, gonderildikten sonra null yapilir.

  const MAX_CHART_POINTS = 60;
    Grafiklerde gosterilecek maksimum veri noktasi sayisi.
    60 nokta ≈ son 1 dakika (saniyede 1 veri gelir).
    Yeni veri geldiginde en eski nokta silinir (shift + push).

  let postureChart, workBreakChart, comparisonChart;
    Chart.js grafik nesneleri. Sayfa yuklendiginde olusturulur.

  const chartData = {};
    Her calisan icin grafik verilerini saklayan nesne.
    Format: {
      username: {
        scores: [85, 90, 78, ...],  // Postur skorlari
        labels: ["14:30:01", ...],   // Zaman etiketleri
        working: 50,                 // Calisiyor sayaci
        onBreak: 10,                 // Mola sayaci
      }
    }

  const CHART_COLORS = [...];
    10 farkli renk. Her calisana sirasiyla bir renk atanir.
    Modulo operatoru ile 10'dan fazla calisan desteklenir.

================================================================================
BOLUM 2: GRAFIK OLUSTURMA (initCharts)
================================================================================

initCharts() fonksiyonu 3 grafik olusturur:

1. POSTUR SKORU ZAMAN GRAFIGI (Line Chart)
   - Canvas ID: #postureChart
   - Tip: Cizgi grafik
   - X ekseni: Zaman (HH:MM:SS formati)
   - Y ekseni: 0-100 arasi postur skoru
   - Her calisan icin ayri bir renkli cizgi
   - Animasyon: 300ms (hizli guncelleme)
   - pointRadius: 0 (noktasiz, sadece cizgi)
   - tension: 0.3 (yumusak egri)

2. CALISMA/MOLA PASTA GRAFIGI (Doughnut Chart)
   - Canvas ID: #workBreakChart
   - Tip: Doughnut (halka)
   - Yesil: Calisiyor toplami
   - Sari: Mola toplami
   - cutout: %65 (ic bosluk orani)
   - Tum calisanlarin toplam verisini gosterir

3. CALISAN KARSILASTIRMA GRAFIGI (Bar Chart)
   - Canvas ID: #comparisonChart
   - Tip: Cubuk grafik
   - X ekseni: Calisan isimleri
   - Y ekseni: Son postur skoru (0-100)
   - Her calisan farkli renk
   - borderRadius: 4 (yuvarlatilmis koseler)

TEMA UYUMU:
  getChartTextColor() ve getChartGridColor() fonksiyonlari CSS
  degiskenlerinden (--text-secondary, --border-subtle) renk alir.
  Boylece koyu/acik tema degistiginde grafik renkleri de uyumlu olur.

================================================================================
BOLUM 3: GRAFIK GUNCELLEME (updateCharts)
================================================================================

updateCharts(username, data) - Her yeni veri geldiginde cagrilir.

ADIM 1: Veriyi sakla
  - username icin chartData nesnesi yoksa olustur
  - Score degerini scores dizisine ekle (push)
  - Zaman etiketini labels dizisine ekle
  - MAX_CHART_POINTS asilirsa en eskiyi sil (shift)
  - is_working durumuna gore working veya onBreak sayacini artir

ADIM 2: Line Chart guncelle
  - En uzun label dizisini bul (label senkronizasyonu icin)
  - Her calisan icin dataset objesi olustur
  - postureChart.update('none') ile animasyonsuz guncelle
    ('none' parametresi performans icin onemli, her saniyede
    animasyon oynatmak goze agir gelir)

ADIM 3: Doughnut Chart guncelle
  - Tum calisanlarin working ve onBreak degerlerini topla
  - Pasta dilimlerini guncelle

ADIM 4: Bar Chart guncelle
  - Her calisanin son (en guncel) skorunu al
  - Cubuk yuksekliklerini ve renklerini guncelle

================================================================================
BOLUM 4: WEBSOCKET YONETIMI
================================================================================

initAdminDashboard(roomCode) - WebSocket baglantisini kurar.

ADIM 1: URL OLUSTUR
  - Protokol: sayfa HTTPS ise wss://, degilse ws://
  - URL: ws://sunucu:port/ws/admin/{roomCode}/
  - Bu URL, dashboard/routing.py'deki AdminConsumer'a eslesir

ADIM 2: BAGLANTI AC
  const ws = new WebSocket(wsUrl);

OLAYLAR (Events):

  ws.onopen:
    Baglanti kuruldugunda calisir.
    - initCharts() ile grafikleri olusturur
    - Konsola basarili baglanti mesaji yazar

  ws.onmessage:
    Sunucudan mesaj geldiginde calisir.
    JSON.parse ile mesaji cozumler, tipine gore:

    'initial_state':
      Ilk baglantida gelir. Cevrimici calisanlarin listesi.
      Kullanim: Konsola yazdirilir.

    'employee_status':
      Bir calisanin durum guncellemesi (her saniye).
      -> updateEmployeeCard(username, data) cagrilir

    'office_status':
      Ofis modu guncellemesi (tek kamera, coklu kisi).
      -> updateOfficeStatus(username, data) cagrilir

    'employee_connected':
      Yeni calisan baglandi.
      -> addEmployeeCard(username) ile yeni kart ekle
      -> updateOnlineCount(+1) ile sayaci artir
      -> Ses efekti cal (varsa)

    'employee_disconnected':
      Calisan ayrildi.
      -> markEmployeeOffline(username) ile karti karart
      -> updateOnlineCount(-1) ile sayaci azalt
      -> Ses efekti cal (varsa)

  ws.onclose:
    Baglanti koptiginda calisir.
    -> 3 saniye sonra otomatik yeniden baglanti (setTimeout)
    -> Bu sayede sayfa acik kaldigi surece baglanti kopmaz

  ws.onerror:
    Hata durumunda konsola hata yazar.

================================================================================
BOLUM 5: CALISAN KARTI ISLEMLERI
================================================================================

updateEmployeeCard(username, data):
  Mevcut bir calisanin kartindaki verileri gunceller.

  POSTUR DURUMU (#posture-{username}):
    - is_good = true  -> Yesil badge, "Dik (15.3°)" yazisi
    - is_good = false -> Kirmizi badge, "Kambur (32.1°)" yazisi

  CALISMA DURUMU (#work-{username}):
    - is_working = true  -> Yesil badge, "Calisiyor" yazisi
    - is_working = false -> Sari badge, "Mola" yazisi

  SKOR (#score-{username}):
    - score >= 75 -> Yesil renk
    - score 50-74 -> Sari renk
    - score < 50  -> Kirmizi renk

  GRAFIK: updateCharts() cagrilir

addEmployeeCard(username):
  Yeni calisan baglandi, kart HTML'i dinamik olarak olusturulur.
  - Bootstrap grid icinde col-md-4 col-lg-3 boyutunda
  - Status dot (yesil nokta), isim, postur/calisma/skor alanlari
  - Uyar butonu ve Detay linki

markEmployeeOffline(username):
  Calisan ayrildi, karti "offline" durumuna gecirir.
  - Status dot: yesil -> gri
  - Kart opakligi: 1.0 -> 0.5 (yarim saydam)

updateOnlineCount(delta):
  #count-val elementinin degerini delta kadar degistirir.
  - delta = +1  -> calisan baglandi, sayaci artir
  - delta = -1  -> calisan ayrildi, sayaci azalt
  - Math.max(0, ...) ile negatife dusmesini onle

================================================================================
BOLUM 6: UYARI GONDERME
================================================================================

openWarningModal(username):
  1. warningTarget = username (hedef calisani kaydet)
  2. #warning-target elementine kullanici adini yaz
  3. #warning-message textarea'sini temizle
  4. Bootstrap Modal'i ac

sendWarning():
  1. Mesaj metnini al ve bos kontrolu yap
  2. WebSocket uzerinden mesaj gonder:
     { type: 'send_warning', username: '...', message: '...' }
  3. Bu mesaj AdminConsumer'a ulasir
  4. AdminConsumer, employee_{username} grubuna iletir
  5. EmployeeConsumer, calisanin ekraninda popup gosterir
  6. Ses efekti cal (varsa)
  7. Modal'i kapat ve warningTarget'i sifirla

HIZLI UYARI BUTONLARI:
  Onceden tanimlanmis uyari mesajlari (orn: "Dik otur!", "Ekrana odaklan!")
  - .quick-warn class'li butonlar data-msg attribute'undan mesaj alir
  - Click event'inde #warning-message'a bu mesaji yazar
  - Kullanici dogrudan "Gonder" butonuna basabilir

================================================================================
BOLUM 7: OFIS MODU DESTEII
================================================================================

updateOfficeStatus(username, data):
  Ofis modunda bir kamera birden fazla kisi izler.
  - data.persons dizisindeki her kisi icin:
    - Label: "{username}_{Kisi 1}", "{username}_{Kisi 2}" seklinde
    - Her kisi icin updateEmployeeCard() cagrilir
    - Bu sayede her kisi ayri bir kart olarak gosterilir

================================================================================
PERFORMANS OPTIMIZASYONLARI
================================================================================

1. CHART UPDATE MODE: 'none'
   Her guncellemede animasyon oynatilMAZ. Saniyede 1 guncelleme
   oldugu icin animasyon performansi dusurur ve gozle kotu gorunur.

2. MAX_CHART_POINTS: 60
   Son 1 dakikalik veri gosterilir. Sinirsiz veri birikimi
   tarayici bellegini sisirip performansi dusurur.

3. POINTRADIUS: 0
   Grafiklerde nokta ciziLMEZ, sadece cizgi gosterilir.
   Cok sayida nokta cizmek GPU'yu yorar.

4. RECONNECT TIMEOUT: 3000ms
   Baglanti koptiginda 3 saniye bekleyip denenir.
   Cok kisa aralik sunucuyu yorar, cok uzun aralik
   kullanici deneyimini bozar.

================================================================================
DOSYA KONUMU
================================================================================

  static/js/dashboard.js    -> Bu dosyada aciklanan tum JavaScript kodlari
  Yuklendigi template:        dashboard/templates/dashboard/admin_dashboard.html
  Bagimliliklar:              Chart.js 4.4 (CDN'den yuklenir, base.html'de)
                              Bootstrap 5.3 (Modal icin)

================================================================================
"""
