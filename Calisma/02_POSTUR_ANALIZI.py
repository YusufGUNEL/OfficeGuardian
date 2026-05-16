"""
================================================================================
                    OFFICEGUARDIAN - POSTUR (KAMBURLUK) ANALIZI
================================================================================

Bu dosya, OfficeGuardian projesinin en temel ozelliklerinden biri olan
POSTUR ANALIZI'nin nasil calistigini detayli olarak aciklar.

Postur analizi, kameradan alinan goruntuyu kullanarak calisanin DUZ mu
yoksa KAMBUR mu oturdugunu tespit eder.

================================================================================
GENEL BAKIS
================================================================================

Postur analizi su adimlardan olusur:

1. KAMERADAN GORUNTU AL
   - OpenCV ile kameradan her saniye ~30 kare (frame) alinir
   - Her frame 640x480 piksel boyutunda bir goruntudur

2. MEDIAPIPE POSE LANDMARKER'A VER
   - Google'in onceden egitilmis yapay zeka modeli
   - Goruntude insan vucudu tespit eder
   - Vucutta 33 ANAHTAR NOKTA belirler (omuz, dirsek, kalca, diz vb.)
   - Bu noktalar "landmark" olarak adlandirilir

3. ANAHTAR NOKTALARI SEC
   - 33 noktanin hepsine ihtiyacimiz yok
   - Kamburluk icin su noktalar yeterli:
     * SOL KULAK ve SAG KULAK  -> ortalama = kulak ortasi
     * SOL OMUZ ve SAG OMUZ    -> ortalama = omuz ortasi
     * SOL KALCA ve SAG KALCA  -> ortalama = kalca ortasi

4. ACILARI HESAPLA
   - Boyun acisi: omuz -> kulak vektorunun dikey ile yaptigi aci
   - Govde acisi: kalca -> omuz vektorunun dikey ile yaptigi aci

5. KARARI VER
   - Boyun acisi > 25 derece VE/VEYA govde acisi > 15 derece ise: KAMBUR
   - Her iki aci de esiklerin altindaysa: DIK (iyi postur)

6. SKOR HESAPLA
   - 0 ile 100 arasinda bir puan uret
   - 100 = mukemmel dik durus, 0 = cok kotu kambur

================================================================================
MEDIAPIPE POSE LANDMARKER NEDIR?
================================================================================

MediaPipe, Google tarafindan gelistirilen acik kaynakli bir yapay zeka
kutuphanesidir. Icerisinde onceden egitilmis modeller bulunur.

PoseLandmarker modeli:
  - Bir goruntude insan vucudunu tespit eder
  - Vucut uzerinde 33 anahtar nokta (landmark) belirler
  - Her noktanin x, y, z koordinatlari ve gorunurluk degeri vardir
  - Koordinatlar NORMALIZE edilmistir (0.0 ile 1.0 arasi)
    * x=0.0 -> gorunturun en sol kenari
    * x=1.0 -> gorunturun en sag kenari
    * y=0.0 -> gorunturun en ust kenari
    * y=1.0 -> gorunturun en alt kenari

33 Landmark Noktasi (onemli olanlar):
  0  = Burun
  7  = Sol Kulak
  8  = Sag Kulak
  11 = Sol Omuz
  12 = Sag Omuz
  23 = Sol Kalca
  24 = Sag Kalca

Model Dosyasi:
  models/pose_landmarker_lite.task
  Bu dosya, onceden egitilmis agirliklari icerir (~5 MB)
  "lite" versiyonu hizli calisir ama biraz daha az hassastir

Calisma Modlari:
  - IMAGE: Tek goruntu icin (fotograd analizi)
  - VIDEO: Video akisi icin (bizim kullandigimiz mod)
  - LIVE_STREAM: Canli kamera akisi (async callback)

Biz VIDEO modunu kullaniyoruz cunku:
  - Her frame icin zaman damgasi gerektirir
  - Frameler arasi takip yapar (daha karasiz sonuclar)
  - Senkron calisir (kolay kullanim)

================================================================================
ACI HESAPLAMA - MATEMATIKSEL ACIKLAMA
================================================================================

Kamburlugu tespit etmek icin iki aci hesaplariz:

1. BOYUN ACISI (Neck Angle)
------------------------------
Boyun acisi, kisininn basinin ne kadar one egik oldugunu olcer.

Nasil hesaplanir:
  a) Omuz orta noktasi hesapla: (sol_omuz + sag_omuz) / 2
  b) Kulak orta noktasi hesapla: (sol_kulak + sag_kulak) / 2
  c) Vektor olustur: omuz_ortasi -> kulak_ortasi
     vektor = (kulak_x - omuz_x, kulak_y - omuz_y)
  d) Bu vektorun DIKEY EKSEN ile yaptigi aciyi hesapla

  Dikey eksen nedir?
  - Tam dik durusta, kulak omuzun TAM USTUNDE olur
  - Bu durumda vektor dikey eksene paralel olur -> aci = 0 derece
  - Bas one egildikce vektor dikeyden sapar -> aci artar

  Formul:
    cos(aci) = (vektor . dikey_referans) / (|vektor| * |dikey_referans|)

    dikey_referans = (0, -1)  # Yukari yonu
    # y ekseni goruntude ASAGI dogru artar, bu yuzden yukari = (0, -1)

    vektor . dikey_referans = vx*0 + vy*(-1) = -vy

    |dikey_referans| = 1 (birim vektor)

    cos(aci) = -vy / sqrt(vx^2 + vy^2)

    aci = arccos(cos(aci))  # Radyandan dereceye cevrilerek

  Ornek:
    - Tam dik oturan kisi: vektor = (0, -0.3) -> aci = 0 derece
    - Hafif one egik: vektor = (0.05, -0.28) -> aci ~= 10 derece
    - Cok kambur: vektor = (0.15, -0.20) -> aci ~= 37 derece

  ESIK DEGER: 25 derece
    - 25 derecenin altinda -> DIK (iyi postur)
    - 25 derecenin ustunde -> KAMBUR (kotu postur)

2. GOVDE ACISI (Torso Angle)
------------------------------
Govde acisi, ustut govdenin ne kadar one egik oldugunu olcer.

Nasil hesaplanir:
  a) Kalca orta noktasi hesapla: (sol_kalca + sag_kalca) / 2
  b) Omuz orta noktasi hesapla: (sol_omuz + sag_omuz) / 2
  c) Vektor olustur: kalca_ortasi -> omuz_ortasi
  d) Dikey eksenle olan aciyi hesapla (ayni formul)

  ESIK DEGER: 15 derece
    - 15 derecenin altinda -> DIK govde
    - 15 derecenin ustunde -> ONE EGIK govde

================================================================================
POSTUR SKORU HESAPLAMA (0-100)
================================================================================

Skor, calisanin ne kadar iyi oturdugunu tek bir sayiyla gosterir.

Formul:
  boyun_orani = max(0, 1 - boyun_acisi / (boyun_esik * 2))
  govde_orani = max(0, 1 - govde_acisi / (govde_esik * 2))
  skor = (boyun_orani * 0.7 + govde_orani * 0.3) * 100

Aciklama:
  - boyun_orani: Boyun acisi esik degerinin 2 katina ulastiginda 0 olur
    Ornek: esik=25, aci=0 -> oran=1.0, aci=25 -> oran=0.5, aci=50 -> oran=0
  - Boyun %70 agirligina sahip (daha onemli)
  - Govde %30 agirligina sahip

Ornekler:
  - Tam dik: boyun=0, govde=0 -> skor=100
  - Hafif kambur: boyun=15, govde=8 -> skor ~= 79
  - Cok kambur: boyun=35, govde=20 -> skor ~= 31
  - Asiri kambur: boyun=50, govde=30 -> skor = 0

================================================================================
POSTURERESULT VERI YAPISI
================================================================================

Her analiz sonucu bir PostureResult nesnesi olarak doner:

  PostureResult:
    neck_angle  : float  # Boyun acisi (derece). Ornek: 15.3
    torso_angle : float  # Govde acisi (derece). Ornek: 8.7
    is_good     : bool   # Postur iyi mi? True/False
    score       : int    # 0-100 arasi skor
    landmarks   : list   # 33 noktanin listesi (iskelet cizimi icin)
    centroid    : tuple  # Kisinin merkez noktasi (x, y) - coklu kisi takibi icin
    nose_pos    : tuple  # Burun konumu (x, y) - yuz eslestirme icin

================================================================================
POSTUREANALYZER SINIFI
================================================================================

Bu sinif, postur analizinin tum islemlerini yonetir.

Olusturma:
  analyzer = PostureAnalyzer(
      neck_threshold=25,   # Boyun aci esigi
      torso_threshold=15,  # Govde aci esigi
      max_persons=1,       # Kac kisi tespit edilsin (1=kisisel, 6=ofis)
  )

Analiz:
  # Tek kisi icin:
  sonuc = analyzer.analyze(frame_rgb)

  # Coklu kisi icin (ofis modu):
  sonuclar = analyzer.analyze_all(frame_rgb)

Iskelet Cizimi:
  analyzer.draw_landmarks(frame, sonuc.landmarks, color=(0, 255, 0))
  # Goruntu uzerine vucut iskeletini cizer

Kapatma:
  analyzer.close()  # MediaPipe kaynaklarini serbest birakir

================================================================================
KOD AKISI (ADIM ADIM)
================================================================================

1. PostureAnalyzer.__init__():
   - MediaPipe PoseLandmarker modelini yukler
   - Esik degerlerini ayarlar
   - Zaman sayacini baslatir (VIDEO modu icin gerekli)

2. PostureAnalyzer.analyze_all(frame_rgb):
   a) Zaman damgasini hesapla (milisaniye)
   b) Frame'i MediaPipe Image formatina cevir
   c) detect_for_video() ile modeli calistir
   d) Her tespit edilen kisi icin:
      - Sol ve sag kulak, omuz, kalca noktalarini al
      - Orta noktalari hesapla (_midpoint)
      - Boyun vektorunu olustur ve acisini hesapla (_angle_with_vertical)
      - Govde vektorunu olustur ve acisini hesapla
      - Esik kontrolu yap (is_good belirle)
      - Skor hesapla
      - Merkez noktasi (centroid) hesapla
      - PostureResult nesnesi olustur
   e) Sonuc listesini don

3. PostureAnalyzer.draw_landmarks():
   - MediaPipe'in cizim yardimcisini kullanir
   - Vucut noktalarini ve baglantilari goruntu uzerine cizer
   - Yesil/kirmizi renk ile postur durumunu gosterir

================================================================================
ONEMLI NOTLAR
================================================================================

1. FRAME FORMATI:
   - Kamera BGR formatinda goruntu verir (OpenCV standardi)
   - MediaPipe RGB formatinda bekler
   - Bu yuzden cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) donusumu gerekir

2. NORMALIZE KOORDINATLAR:
   - MediaPipe noktalar 0.0-1.0 arasinda normalize edilmis
   - Piksel koordinati icin: piksel_x = landmark.x * goruntu_genisligi

3. GUVEN ESIKLERI:
   - min_pose_detection_confidence = 0.6 (%60)
   - min_pose_presence_confidence = 0.5 (%50)
   - min_tracking_confidence = 0.5 (%50)
   Bu degerler dusurulerek daha fazla algilama saglanabilir,
   ancak yanlis pozitif orani artar.

4. SIMETRI:
   - Sol ve sag noktalar ortalamalanarak simetri etkisi azaltilir
   - Bu sayede kisi kameraya hafif cakrik oturursa da dogru sonuc alinir

5. DOSYA KONUMU:
   core/posture_analyzer.py

================================================================================
"""
