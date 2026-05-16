"""
Çoklu Kişi Takip Modülü (Multi-Person Tracker)
================================================

Bu modül, ofis ortamında kamera görüntüsü üzerinden birden fazla kişiyi
eş zamanlı olarak takip etmek için tasarlanmıştır. Her kareye (frame)
ait pose (duruş) ve göz yönü (gaze) analiz sonuçlarını alır, bunları
önceki karelerdeki mevcut kişilerle eşleştirerek sürekli bir takip
zinciri oluşturur.

Takip Algoritması Genel Bakış:
------------------------------
1. CENTROID EŞLEŞTİRME (Greedy Nearest-Neighbor):
   - Her yeni karedeki pose sonuçlarının ağırlık merkezi (centroid)
     hesaplanır ve önceki karelerde bilinen kişilerin centroid'leri
     ile karşılaştırılır.
   - Tüm olası (kişi, pose) çiftleri arasındaki Öklid mesafesi
     hesaplanır ve mesafeye göre sıralı bir liste oluşturulur.
   - En küçük mesafeden başlayarak, eşik değerin (match_threshold)
     altında kalan çiftler bire-bir eşleştirilir (greedy matching).
   - Bu yaklaşım, her karedeki kişilerin bir önceki karedeki
     konumlarına yakın olduğu varsayımına dayanır.

2. YENİ KİŞİ OLUŞTURMA:
   - Eşleşmemiş kalan pose sonuçları için yeni PersonState nesneleri
     oluşturulur. Her yeni kişiye benzersiz bir ID ve döngüsel olarak
     bir renk atanır.
   - Aynı anda takip edilebilecek maksimum kişi sayısı sınırlıdır
     (varsayılan: 6).

3. GAZE-POSE EŞLEŞTİRME:
   - Göz yönü (gaze) analiz sonuçları, burun konumu (nose_pos)
     yakınlığına göre pose sonuçlarıyla eşleştirilir.
   - Bu sayede her kişinin hem duruş hem de bakış yönü bilgisi
     birleştirilerek çalışma durumu hesaplanır.

4. İSTATİSTİK TAKİBİ:
   - Her kişi için çalışma süresi, mola süresi, iyi duruş süresi
     ve kötü duruş süresi gibi istatistikler frame-frame
     biriktirilir.
   - Çalışma durumu geçişi gecikmelidir (hysteresis): kişi ekrandan
     bakışını çevirdikten sonra belirli bir süre (GAZE_STATUS_DELAY)
     beklenilir, böylece anlık baş çevirmeleri mola olarak sayılmaz.

5. KAYIP KİŞİ TEMİZLEME:
   - Belirli bir süre (disappear_timeout) boyunca hiçbir pose ile
     eşleşmemiş kişiler, takip listesinden kaldırılır. Bu, sahneyi
     terk etmiş kişilerin bellekte gereksiz yer kaplamamasını sağlar.

Kullanım Örneği:
    tracker = PersonTracker(max_persons=6, disappear_timeout=5.0)
    persons = tracker.update(pose_results, gaze_results)
    for pid, state in persons.items():
        print(f"{state.label}: çalışma={state.is_working}, duruş_skoru={state.posture_score}")

Bağımlılıklar:
    - config: Renk paleti (PERSON_COLORS) ve gecikme sabitleri (GAZE_STATUS_DELAY)
    - core.posture_analyzer.PostureResult: Duruş analiz sonuç veri yapısı
    - core.gaze_analyzer.GazeResult: Göz yönü analiz sonuç veri yapısı
"""

import math
import time
from dataclasses import dataclass, field

import config
from core.posture_analyzer import PostureResult
from core.gaze_analyzer import GazeResult


@dataclass
class PersonState:
    """
    Tek bir kişinin anlık ve birikmiş durumunu tutan veri sınıfı.

    Bu dataclass, takip edilen her kişi için kimlik bilgilerini,
    anlık analiz sonuçlarını, zamanlama verilerini ve birikmiş
    istatistikleri bir arada tutar. PersonTracker tarafından
    oluşturulur ve her frame'de güncellenir.

    Alanlar (Fields):
    -----------------
    Kimlik Bilgileri:
        person_id   (int)   : Kişiye atanan benzersiz tamsayı kimlik numarası.
                              Takip boyunca değişmez; kişi sahneden ayrılıp
                              geri dönerse yeni bir ID alır.
        color_bgr   (tuple) : Kişiye atanan rengin BGR (Mavi-Yeşil-Kırmızı)
                              formatındaki değeri. OpenCV çizim fonksiyonları
                              BGR formatı kullandığı için bu format tercih edilir.
                              Örnek: (255, 0, 0) = mavi.
        color_hex   (str)   : Aynı rengin HEX (onaltılık) gösterimi. Arayüz (UI)
                              bileşenlerinde kullanılır. Örnek: "#0000FF" = mavi.
        label       (str)   : Kişinin kullanıcıya gösterilecek etiketi.
                              "Kişi 1", "Kişi 2" şeklinde otomatik oluşturulur.

    Anlık Sonuçlar (her frame güncellenir):
        posture     (PostureResult | None) : Bu karede kişinin duruş analiz sonucu.
                                             Kişi bu karede tespit edilmediyse None olur.
        gaze        (GazeResult | None)    : Bu karede kişinin göz yönü analiz sonucu.
                                             Göz yönü tespit edilemediyse None olur.
        is_working  (bool)                 : Kişinin şu anda çalışıp çalışmadığını
                                             belirten bayrak. Ekrana bakıyorsa True,
                                             belirli bir süredir bakmıyorsa False.
                                             Gecikme mantığı (hysteresis) uygulanır.
        centroid    (tuple)                : Kişinin görüntüdeki ağırlık merkezi
                                             koordinatı (x, y). Normalize edilmiş
                                             değerlerdir (0.0 - 1.0 aralığı).
                                             Eşleştirme için kullanılır.

    Zamanlama:
        last_seen   (float) : Kişinin en son tespit edildiği zamanın damgası
                              (time.time() değeri, epoch saniye). Kaybolma
                              zaman aşımı kontrolü için kullanılır.
        first_seen  (float) : Kişinin ilk kez tespit edildiği zamanın damgası.
                              Toplam takip süresini hesaplamak için kullanılabilir.

    Birikmiş İstatistikler:
        work_seconds          (float) : Kişinin toplam çalışma süresi (saniye).
                                        is_working=True olduğu frame'lerde biriktirilir.
        break_seconds         (float) : Kişinin toplam mola süresi (saniye).
                                        is_working=False olduğu frame'lerde biriktirilir.
        good_posture_seconds  (float) : İyi duruşta geçirilen toplam süre (saniye).
                                        posture.is_good=True olduğunda biriktirilir.
        bad_posture_seconds   (float) : Kötü duruşta geçirilen toplam süre (saniye).
                                        posture.is_good=False olduğunda biriktirilir.

    Dahili Durum (dışarıdan kullanılmaması gereken alanlar):
        _last_tick            (float)        : Son istatistik güncelleme zamanı.
                                               Delta hesabı için kullanılır.
        _not_looking_start    (float | None) : Kişinin ekrana bakmamaya başladığı an.
                                               Gecikme mantığı (hysteresis) için kullanılır.
                                               None ise kişi şu an ekrana bakıyor demektir.
        _bad_posture_start    (float | None) : Kötü duruşun başladığı an. İleride
                                               uyarı mekanizması için kullanılmak
                                               üzere ayrılmıştır.

    Hesaplanan Özellikler (Properties):
        total_seconds  : Toplam takip süresi (çalışma + mola).
        posture_score  : 0-100 arası duruş puanı (iyi duruş oranı).
        work_ratio     : 0-100 arası çalışma oranı yüzdesi.
    """

    person_id: int
    color_bgr: tuple            # BGR renk demeti — OpenCV çizim fonksiyonları için
    color_hex: str              # HEX renk dizgisi — kullanıcı arayüzü için
    label: str                  # Görüntüleme etiketi: "Kişi 1", "Kişi 2", ...

    # ── Anlık sonuçlar (her frame'de güncellenen değerler) ──
    posture: PostureResult | None = None    # Bu karedeki duruş analiz sonucu (yoksa None)
    gaze: GazeResult | None = None          # Bu karedeki göz yönü sonucu (yoksa None)
    is_working: bool = False                # Kişi şu anda ekrana bakıp çalışıyor mu?
    centroid: tuple = (0.0, 0.0)            # Kişinin normalize ağırlık merkezi (x, y)

    # ── Zamanlama bilgileri ──
    last_seen: float = 0.0      # En son görünme zamanı (epoch saniye cinsinden)
    first_seen: float = 0.0     # İlk görünme zamanı (epoch saniye cinsinden)

    # ── Birikmiş istatistikler (her frame delta olarak eklenir) ──
    work_seconds: float = 0.0           # Toplam çalışma süresi (saniye)
    break_seconds: float = 0.0          # Toplam mola süresi (saniye)
    good_posture_seconds: float = 0.0   # İyi duruşta geçen toplam süre (saniye)
    bad_posture_seconds: float = 0.0    # Kötü duruşta geçen toplam süre (saniye)

    # ── Dahili durum değişkenleri (doğrudan erişim önerilmez) ──
    _last_tick: float = 0.0                     # Son istatistik güncelleme anı
    _not_looking_start: float | None = None     # Ekrana bakmama başlangıç anı (hysteresis)
    _bad_posture_start: float | None = None     # Kötü duruş başlangıç anı (gelecek kullanım)

    @property
    def total_seconds(self) -> float:
        """
        Kişinin toplam takip edilen süresini saniye cinsinden döndürür.

        Bu değer, çalışma süresi (work_seconds) ile mola süresinin
        (break_seconds) toplamıdır. Kişinin ilk görünmesinden itibaren
        aktif olarak takip edildiği toplam zamanı yansıtır.

        Returns:
            float: Toplam çalışma + mola süresi (saniye cinsinden).
        """
        return self.work_seconds + self.break_seconds

    @property
    def posture_score(self) -> int:
        """
        Kişinin duruş puanını 0-100 arasında bir tamsayı olarak hesaplar.

        Hesaplama yöntemi:
            puan = (iyi_duruş_süresi / toplam_duruş_süresi) * 100

        Eğer toplam duruş süresi 1 saniyeden azsa (yeterli veri yoksa),
        varsayılan olarak 100 (mükemmel) döndürülür. Bu, yeni tespit
        edilen kişilerin düşük puanla başlamaması içindir.

        Returns:
            int: 0 (sürekli kötü duruş) ile 100 (sürekli iyi duruş)
                 arasında bir puan.
        """
        # İyi ve kötü duruş sürelerinin toplamı
        total = self.good_posture_seconds + self.bad_posture_seconds
        if total < 1:
            # Yeterli veri toplanmadıysa varsayılan puan: 100
            return 100
        # İyi duruş oranını yüze çevirip tamsayıya yuvarla
        return int((self.good_posture_seconds / total) * 100)

    @property
    def work_ratio(self) -> int:
        """
        Kişinin çalışma oranını 0-100 arasında bir tamsayı olarak hesaplar.

        Hesaplama yöntemi:
            oran = (çalışma_süresi / toplam_süre) * 100

        Eğer toplam süre 1 saniyeden azsa (yeterli veri yoksa),
        varsayılan olarak 0 döndürülür. Bu, yeni tespit edilen
        kişilerin henüz çalışma süresi biriktirmemiş olmasından
        kaynaklanır.

        Returns:
            int: 0 (hiç çalışmadı) ile 100 (sürekli çalıştı) arasında
                 bir oran yüzdesi.
        """
        # Çalışma ve mola sürelerinin toplamı
        total = self.work_seconds + self.break_seconds
        if total < 1:
            # Yeterli veri toplanmadıysa varsayılan oran: 0
            return 0
        # Çalışma oranını yüze çevirip tamsayıya yuvarla
        return int((self.work_seconds / total) * 100)


class PersonTracker:
    """
    Çoklu kişi takip sınıfı — frame'ler arası centroid tabanlı eşleştirme yapar.

    Bu sınıf, her video karesinde (frame) elde edilen duruş (pose) ve göz
    yönü (gaze) analiz sonuçlarını alarak, önceki karelerdeki bilinen
    kişilerle eşleştirme yapar. Böylece her kişinin kimliğini koruyarak
    sürekli bir takip zinciri oluşturur.

    Eşleştirme Algoritmasının Detaylı Açıklaması:
    ----------------------------------------------
    Algoritma, "greedy nearest-neighbor" (açgözlü en yakın komşu)
    yaklaşımını kullanır:

    Adım 1 — Mesafe Matrisi Oluşturma:
        Mevcut tüm kişiler ile yeni karedeki tüm pose sonuçları arasında
        kartezyen çarpım yapılır. Her (kişi, pose) çifti için Öklid
        mesafesi hesaplanır.

    Adım 2 — Mesafeye Göre Sıralama:
        Tüm çiftler mesafe değerine göre küçükten büyüğe sıralanır.
        Bu sıralama, en yakın eşlerin öncelikli olarak eşleştirilmesini
        sağlar.

    Adım 3 — Açgözlü Eşleştirme (Greedy Matching):
        Sıralanmış liste üzerinde tek geçiş yapılır. Her çift için:
        - Kişi zaten eşleştirilmişse atla
        - Pose zaten eşleştirilmişse atla
        - Mesafe, eşik değerden (match_threshold) büyükse atla
        - Aksi halde bu çifti eşle ve her ikisini de "kullanıldı" olarak işaretle

    Adım 4 — Yeni Kişilerin Tespiti:
        Eşleşmemiş kalan pose sonuçları, yeni kişiler olarak kaydedilir.
        Maksimum kişi limitine uyulur.

    Adım 5 — Gaze Eşleştirme:
        Aynı greedy yaklaşımla göz yönü sonuçları, pose sonuçlarına
        burun konumu yakınlığına göre eşleştirilir.

    Adım 6 — Durum Güncelleme:
        Eşleşen her kişi için posture, gaze, centroid, çalışma durumu
        ve istatistikler güncellenir.

    Adım 7 — Kayıp Kişi Temizliği:
        disappear_timeout süresi boyunca görülmeyen kişiler silinir.

    Kullanım:
    ---------
        # Takip nesnesini oluştur (en fazla 6 kişi, 5 saniye zaman aşımı)
        tracker = PersonTracker(max_persons=6, disappear_timeout=5.0)

        # Her frame'de guncelleme yap
        while kamera_acik:
            pose_results = pose_analyzer.analyze(frame)
            gaze_results = gaze_analyzer.analyze(frame)
            persons = tracker.update(pose_results, gaze_results)

            for pid, state in persons.items():
                print(f"{state.label}: çalışıyor={state.is_working}")

        # Gerektiğinde sıfırla
        tracker.reset()

    Parametreler:
        max_persons (int)          : Aynı anda takip edilebilecek maksimum kişi sayısı.
        disappear_timeout (float)  : Bir kişinin görünmeden kaldıktan sonra
                                     listeden silinmesi için gereken süre (saniye).
        match_threshold (float)    : Centroid eşleştirme için maksimum Öklid mesafesi.
                                     Bu değerin altındaki mesafeler eşleşme olarak kabul edilir.
                                     Normalize koordinat sisteminde (0-1) çalıştığı için
                                     0.15 gibi küçük bir değer yeterlidir.
    """

    def __init__(self, max_persons: int = 6, disappear_timeout: float = 5.0,
                 match_threshold: float = 0.15):
        """
        PersonTracker nesnesini verilen yapılandırma parametreleri ile başlatır.

        Args:
            max_persons (int): Aynı anda takip edilebilecek maksimum kişi sayısı.
                               Bu sınıra ulaşıldıktan sonra yeni kişiler eklenmez.
                               Varsayılan: 6.
            disappear_timeout (float): Bir kişinin kameradan kaybolmasının
                                       kabul edilmesi için gereken süre (saniye).
                                       Bu süre boyunca hiçbir pose ile eşleşmezse
                                       kişi takip listesinden silinir. Varsayılan: 5.0.
            match_threshold (float): Centroid tabanlı eşleştirmede kabul edilen
                                     maksimum Öklid mesafesi. Daha düşük değer
                                     daha katı eşleştirme sağlar. Varsayılan: 0.15.
        """
        # Aynı anda izlenebilecek en fazla kişi sayısı
        self._max_persons = max_persons
        # Kişi kaybolma zaman aşımı (saniye) — bu süre dolunca kişi silinir
        self._disappear_timeout = disappear_timeout
        # Centroid eşleştirmesinde kabul edilecek maksimum mesafe eşiği
        self._match_threshold = match_threshold
        # Bir sonraki oluşturulacak kişiye verilecek benzersiz ID
        self._next_id = 1
        # Takip edilen tüm kişilerin sözlüğü: {person_id: PersonState}
        self._persons: dict[int, PersonState] = {}
        # Renk paleti üzerinde döngüsel olarak ilerlemek için indeks sayacı
        self._color_index = 0

    def update(self, pose_results: list[PostureResult],
               gaze_results: list[GazeResult]) -> dict[int, PersonState]:
        """
        Yeni bir frame'in analiz sonuçlarıyla tüm kişilerin durumunu günceller.

        Bu metot, takip algoritmasının ana döngü fonksiyonudur. Her frame için
        çağrılmalıdır. Aşağıdaki adımları sırasıyla uygular:

        1. Pose centroid'leri ile mevcut kişileri eşleştir (greedy nearest-neighbor)
        2. Eşleşmemiş pose sonuçları için yeni kişiler oluştur ve ID ata
        3. Gaze (göz yönü) sonuçlarını pose sonuçlarıyla burun pozisyonuna göre eşleştir
        4. Eşleşen her kişinin posture, gaze, çalışma durumu ve istatistiklerini güncelle
        5. Belirli süredir görülmeyen (kayıp) kişileri takip listesinden temizle

        Args:
            pose_results (list[PostureResult]): Bu karede tespit edilen tüm duruş
                                                analiz sonuçlarının listesi. Her eleman
                                                bir kişinin centroid ve duruş bilgisini içerir.
            gaze_results (list[GazeResult]): Bu karede tespit edilen tüm göz yönü
                                             analiz sonuçlarının listesi. Her eleman bir
                                             kişinin burun konumu ve ekrana bakma durumunu içerir.

        Returns:
            dict[int, PersonState]: Güncellenmiş kişi sözlüğü. Anahtar: person_id,
                                    değer: PersonState nesnesi. Bu sözlük, şu anda
                                    aktif olarak takip edilen tüm kişileri içerir.
        """
        # Şu anki zaman damgasını al — tüm zamanlama hesaplamaları için kullanılacak
        now = time.time()

        # ══════════════════════════════════════════════════════════════════════
        # ADIM 1: POSE → MEVCUT KİŞİ EŞLEŞTİRMESİ (Centroid Yakınlığı Tabanlı)
        # ══════════════════════════════════════════════════════════════════════
        # Bu adımda, yeni karedeki her pose sonucunun centroid'i ile
        # mevcut kişilerin bilinen centroid'leri karşılaştırılır.
        # Amaç: her pose'u daha önce bilinen bir kişiye atamak.

        # Zaten eşleşmiş kişi ID'lerini takip eden küme (aynı kişi iki kez eşleşmemeli)
        used_person_ids = set()
        # Zaten eşleşmiş pose indekslerini takip eden küme (aynı pose iki kez eşleşmemeli)
        used_pose_indices = set()
        # Başarılı eşleştirmelerin listesi: her eleman (kişi_id, pose_indeksi) çiftidir
        matches: list[tuple[int, int]] = []  # (person_id, pose_index)

        if self._persons and pose_results:
            # --- Mesafe matrisi oluşturma ---
            # Mevcut kişilerin her biri ile yeni karedeki her pose arasındaki
            # Öklid mesafesini hesapla. Tüm olası (kişi, pose) çiftlerini oluştur.
            pairs = []
            for pid, ps in self._persons.items():
                for pi, pr in enumerate(pose_results):
                    # Mevcut kişinin centroid'i ile yeni pose'un centroid'i arasındaki mesafe
                    dist = self._distance(ps.centroid, pr.centroid)
                    # (mesafe, kişi_id, pose_indeksi) üçlüsünü listeye ekle
                    pairs.append((dist, pid, pi))
            # Tüm çiftleri mesafeye göre küçükten büyüğe sırala
            # En yakın çiftler listenin başına gelir — açgözlü eşleştirme için gerekli
            pairs.sort()

            # --- Açgözlü eşleştirme (Greedy Matching) ---
            # Sıralanmış liste üzerinde tek geçiş yap:
            # - En küçük mesafeli çiftten başlayarak eşleştir
            # - Zaten eşleşmiş kişi veya pose varsa atla
            # - Mesafe eşik değeri aşıyorsa eşleştirme yapma
            for dist, pid, pi in pairs:
                if pid in used_person_ids or pi in used_pose_indices:
                    # Bu kişi veya bu pose zaten başka biriyle eşleşti — atla
                    continue
                if dist < self._match_threshold:
                    # Mesafe eşik değerin altında — başarılı eşleştirme
                    matches.append((pid, pi))
                    used_person_ids.add(pid)
                    used_pose_indices.add(pi)

        # ══════════════════════════════════════════════════════════════════════
        # ADIM 2: EŞLEŞMEMİŞ POSE'LAR → YENİ KİŞİ KAYDI
        # ══════════════════════════════════════════════════════════════════════
        # Adım 1'de hiçbir mevcut kişiyle eşleşmemiş pose sonuçları,
        # sahneye yeni giren kişiler olarak değerlendirilir.
        # Maksimum kişi limitine uyulması kontrol edilir.

        new_entries = []
        for pi, pr in enumerate(pose_results):
            if pi not in used_pose_indices:
                # Bu pose eşleşmedi — yeni bir kişi olabilir
                if len(self._persons) + len(new_entries) < self._max_persons:
                    # Henüz kişi limitine ulaşılmadı — yeni kişi oluştur
                    new_person = self._create_person(pr.centroid, now)
                    new_entries.append((new_person.person_id, pi))
                    # Yeni kişiyi ana sözlüğe ekle
                    self._persons[new_person.person_id] = new_person

        # Yeni oluşturulan kişilerin eşleşme listesine ekle
        # Böylece adım 4'te bunlar da güncellenecek
        matches.extend(new_entries)

        # ══════════════════════════════════════════════════════════════════════
        # ADIM 3: GAZE (GÖZ YÖNÜ) → POSE EŞLEŞTİRMESİ (Burun Pozisyonu Tabanlı)
        # ══════════════════════════════════════════════════════════════════════
        # Göz yönü analizi ve duruş analizi farklı modeller tarafından yapılır.
        # Bu iki sonucu aynı kişiye bağlamak için, her iki sonuçtaki burun
        # konumu (nose_pos) karşılaştırılır. Burun pozisyonları birbirine
        # yeterince yakın olan çiftler aynı kişiye ait kabul edilir.

        # pose_indeksi → GazeResult eşlemesi için sözlük
        gaze_map: dict[int, GazeResult] = {}  # pose_index → GazeResult
        if gaze_results and pose_results:
            # Zaten eşleşmiş gaze indekslerini takip eden küme
            used_gaze = set()
            # Tüm olası (pose, gaze) çiftlerinin mesafe listesi
            g_pairs = []
            for pi, pr in enumerate(pose_results):
                for gi, gr in enumerate(gaze_results):
                    # Pose'un burun konumu ile gaze'in burun konumu arasindaki mesafe
                    dist = self._distance(pr.nose_pos, gr.nose_pos)
                    g_pairs.append((dist, pi, gi))
            # Mesafeye göre sırala — en yakın çiftler önce eşleşecek
            g_pairs.sort()
            for dist, pi, gi in g_pairs:
                if pi in gaze_map or gi in used_gaze:
                    # Bu pose veya bu gaze zaten eşleşti — atla
                    continue
                if dist < 0.15:
                    # Burun pozisyonları yeterince yakın — aynı kişiye ait kabul et
                    gaze_map[pi] = gaze_results[gi]
                    used_gaze.add(gi)

        # ══════════════════════════════════════════════════════════════════════
        # ADIM 4: EŞLEŞEN KİŞİLERİN DURUMUNU GÜNCELLE
        # ══════════════════════════════════════════════════════════════════════
        # Her başarılı eşleştirme için, kişinin posture, gaze, centroid,
        # çalışma durumu ve birikmiş istatistiklerini güncelle.

        # Bu frame'de güncellenen kişi ID'lerini takip eden küme
        updated_ids = set()
        for pid, pi in matches:
            # Eşleşen kişiyi ve pose sonucunu al
            ps = self._persons[pid]
            pr = pose_results[pi]
            # Bu pose'a eşleşen gaze sonucunu al (yoksa None)
            gr = gaze_map.get(pi)

            # Anlık sonuçları güncelle
            ps.posture = pr         # Bu karedeki duruş sonucu
            ps.gaze = gr            # Bu karedeki göz yönü sonucu (varsa)
            ps.centroid = pr.centroid  # Centroid'i güncelle (sonraki frame eşleştirmesi için)
            ps.last_seen = now      # Son görünme zamanını güncelle

            # Çalışma durumunu hesapla (gecikmeli geçiş / hysteresis mantığı)
            # Kişi ekrana bakmıyorsa hemen "çalışmıyor" demek yerine
            # belirli bir süre beklenir
            ps.is_working = self._compute_work_status(ps, gr, now)

            # Birikmiş istatistikleri güncelle (çalışma/mola süresi, duruş süresi)
            self._tick_stats(ps, now)

            # Bu kişinin bu frame'de güncellendiğini kaydet
            updated_ids.add(pid)

        # Bu frame'de tespit edilememiş kişilerin anlık sonuçlarını temizle
        # (centroid ve istatistikler korunur, sadece posture/gaze None yapılır)
        for pid, ps in self._persons.items():
            if pid not in updated_ids:
                # Bu kişi bu karede görülmedi — anlık verilerini sıfırla
                ps.posture = None
                ps.gaze = None

        # ══════════════════════════════════════════════════════════════════════
        # ADIM 5: KAYIP KİŞİLERİ TAKİP LİSTESİNDEN TEMİZLE
        # ══════════════════════════════════════════════════════════════════════
        # Belirli bir süredir (disappear_timeout) hiçbir pose ile eşleşmemiş
        # kişileri kalıcı olarak sil. Bu, sahneyi terk etmiş kişilerin
        # bellekte gereksiz yer kaplamamasını sağlar.

        # Son görünme zamanı zaman aşımını aşmış kişilerin ID'lerini topla
        expired = [pid for pid, ps in self._persons.items()
                   if now - ps.last_seen > self._disappear_timeout]
        # Süresi dolmuş kişileri sözlükten kaldır
        for pid in expired:
            del self._persons[pid]

        # Güncellenmiş kişi sözlüğünü döndür
        return self._persons

    def get_persons(self) -> dict[int, PersonState]:
        """
        Şu anda aktif olarak takip edilen tüm kişilerin sözlüğünü döndürür.

        Bu metot, update() çağrılmadan mevcut durumu sorgulamak için
        kullanılabilir. Dönen sözlük, PersonTracker'ın iç durumuna
        doğrudan referans verir (kopya değildir).

        Returns:
            dict[int, PersonState]: Anahtar olarak kişi ID'si, değer olarak
                                    PersonState nesnesi içeren sözlük.
        """
        return self._persons

    def reset(self):
        """
        Takip durumunu tamamen sıfırlar.

        Tüm takip edilen kişiler silinir, ID sayacı 1'e ve renk indeksi 0'a
        döndürülür. Bu metot, yeni bir oturum başlatıldığında veya
        kamera değiştirildiğinde çağrılmalıdır.

        Sıfırlanan değerler:
            - _persons: Boş sözlüğe döner
            - _next_id: 1'e döner (ilk kişi yine ID=1 alır)
            - _color_index: 0'a döner (renk paleti baştan başlar)
        """
        # Tüm kişileri sil
        self._persons.clear()
        # ID sayacını başlangıca döndür
        self._next_id = 1
        # Renk paletini baştan başlatmak için indeksi sıfırla
        self._color_index = 0

    def _create_person(self, centroid: tuple, now: float) -> PersonState:
        """
        Yeni bir kişi nesnesi oluşturur ve benzersiz ID ile renk atar.

        Renk ataması, config.PERSON_COLORS listesinden döngüsel (modulo)
        olarak yapılır. Böylece renk paleti tükense bile başına dönerek
        devam eder.

        Args:
            centroid (tuple): Yeni kişinin görüntüdeki ilk ağırlık merkezi
                              koordinatı (x, y). Normalize edilmiş değerlerdir.
            now (float): Şu anki zaman damgası (time.time()). first_seen ve
                         last_seen değerleri için kullanılır.

        Returns:
            PersonState: Tüm alanları başlangıç değerleriyle doldurulmuş
                         yeni kişi durumu nesnesi.
        """
        # Renk paletinden sıradaki rengi al (döngüsel erişim: indeks % palet_uzunluğu)
        color_info = config.PERSON_COLORS[self._color_index % len(config.PERSON_COLORS)]
        # Renk indeksini bir sonrakine ilerlet
        self._color_index += 1
        # Benzersiz kişi ID'sini ata
        pid = self._next_id
        # ID sayacını bir sonrakine ilerlet
        self._next_id += 1

        # Yeni PersonState nesnesini oluştur ve döndür
        return PersonState(
            person_id=pid,
            color_bgr=color_info["bgr"],       # BGR renk değeri (OpenCV için)
            color_hex=color_info["hex"],        # HEX renk değeri (UI için)
            label=f"Kisi {pid}",                # Görüntüleme etiketi
            centroid=centroid,                  # Başlangıç ağırlık merkezi
            last_seen=now,                      # Şu anki zaman
            first_seen=now,                     # İlk görüş zamanı = şu an
            _last_tick=now,                     # İstatistik sayacı başlangıcı
        )

    @staticmethod
    def _compute_work_status(ps: PersonState, gaze: GazeResult | None,
                             now: float) -> bool:
        """
        Kişinin çalışma durumunu gecikmeli geçiş (hysteresis) mantığı ile hesaplar.

        Bu metot, kişinin ekrana bakıp bakmadığına göre çalışma durumunu belirler.
        Ancak anlık baş çevirmelerinin yanlış "mola" olarak algılanmamasını önlemek
        için gecikme (delay) mekanizması uygular:

        - Kişi ekrana bakıyorsa: hemen is_working = True
        - Kişi ekrana bakmıyorsa (veya gaze tespit edilemediyse):
            * İlk bakmama anından itibaren bir zamanlayıcı başlatılır
            * Zamanlayıcı GAZE_STATUS_DELAY süresini aşarsa: is_working = False
            * Zamanlayıcı henüz dolmadıysa: önceki durum korunur

        Bu yaklaşım, kısa süreli bakış kayıplarında (örneğin bir an için
        klavyeye bakma) gereksiz durum değişikliklerini önler.

        Args:
            ps (PersonState): Durumu hesaplanacak kişinin mevcut durumu.
                              _not_looking_start alanı bu metot tarafından güncellenir.
            gaze (GazeResult | None): Bu karedeki göz yönü sonucu.
                                      None ise göz yönü tespit edilemedi demektir.
            now (float): Şu anki zaman damgası (saniye cinsinden epoch).

        Returns:
            bool: True ise kişi çalışıyor, False ise mola veriyor.
        """
        if gaze is None or not gaze.looking_at_screen:
            # Kişi ekrana bakmıyor veya göz yönü tespit edilemedi
            if ps._not_looking_start is None:
                # Bu, ekrana bakmama durumunun başlangıç anı — zamanı kaydet
                ps._not_looking_start = now
            if now - ps._not_looking_start >= config.GAZE_STATUS_DELAY:
                # Yeterli süre (GAZE_STATUS_DELAY) boyunca ekrana bakmadı
                # Artık kesin olarak "çalışmıyor" kabul et
                return False
            # Henüz gecikme süresi dolmadı — önceki durumu koru (hysteresis)
            return ps.is_working
        else:
            # Kişi ekrana bakıyor — zamanlayıcıyı sıfırla ve "çalışıyor" olarak işaretle
            ps._not_looking_start = None
            return True

    @staticmethod
    def _tick_stats(ps: PersonState, now: float):
        """
        Kişinin birikmiş istatistiklerini son güncelleme zamanından bu yana
        geçen süre (delta) kadar arttırır.

        Delta hesabı:
            delta = şu_an - son_güncelleme_zamanı

        Güvenlik sınırı: Delta en fazla 2.0 saniye olabilir. Bu sınır,
        uzun süreli frame kayıpları veya donmalarda istatistiklerin
        anormal şekilde şişmemesini sağlar. Örneğin, 10 saniyelik bir
        donmadan sonra gelen frame sadece 2 saniye olarak sayılır.

        Güncellenen istatistikler:
            - is_working durumuna göre: work_seconds veya break_seconds
            - posture.is_good durumuna göre: good_posture_seconds veya bad_posture_seconds

        Eğer posture verisi mevcut değilse (None), duruş varsayılan olarak
        "iyi" kabul edilir. Bu, göz yönü tespiti yapılıp duruş analizi
        yapılamadığında kişiye haksız ceza verilmemesi içindir.

        Args:
            ps (PersonState): İstatistikleri güncellenecek kişinin durumu.
            now (float): Şu anki zaman damgası (saniye cinsinden epoch).
        """
        if ps._last_tick > 0:
            # Son güncelleme ile şu an arasındaki farkı hesapla
            # Maksimum 2 saniye ile sınırlandırılır (aşırı büyük deltaları önler)
            delta = min(now - ps._last_tick, 2.0)

            # Çalışma durumuna göre ilgili sayacı artır
            if ps.is_working:
                # Kişi çalışıyor — çalışma süresine ekle
                ps.work_seconds += delta
            else:
                # Kişi çalışmıyor — mola süresine ekle
                ps.break_seconds += delta

            # Duruş durumuna göre ilgili sayacı artır
            # Posture verisi yoksa varsayılan olarak "iyi duruş" kabul edilir
            is_good = ps.posture.is_good if ps.posture else True
            if is_good:
                # İyi duruş — iyi duruş süresine ekle
                ps.good_posture_seconds += delta
            else:
                # Kötü duruş — kötü duruş süresine ekle
                ps.bad_posture_seconds += delta

        # Son güncelleme zamanını şu ana ayarla (bir sonraki delta hesabı için)
        ps._last_tick = now

    @staticmethod
    def _distance(a: tuple, b: tuple) -> float:
        """
        İki nokta arasındaki 2 boyutlu Öklid (Euclidean) mesafesini hesaplar.

        Formül:
            mesafe = sqrt((x1 - x2)^2 + (y1 - y2)^2)

        Bu metot, centroid eşleştirmesinde (pose-kişi) ve burun pozisyonu
        eşleştirmesinde (gaze-pose) kullanılır. Normalize koordinatlar
        üzerinde çalışıldığı için dönen değer 0.0 ile ~1.41 arasındadır.

        Args:
            a (tuple): Birinci noktanın (x, y) koordinatları.
            b (tuple): İkinci noktanın (x, y) koordinatları.

        Returns:
            float: İki nokta arasındaki Öklid mesafesi.
        """
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
