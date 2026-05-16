"""
================================================================================
                    OFFICEGUARDIAN - ML KISISEL MODEL (KALIBRASYON)
================================================================================

Bu dosya, her calisanin vucuduna ozel kisisel esik degerlerinin
nasil hesaplandigini (kalibrasyon) detayli olarak aciklar.

================================================================================
NEDEN KISISEL MODEL GEREKLI?
================================================================================

Herkesin vucut yapisi farklidir:
  - Uzun boylu birisinin dogal boyun acisi 10-15 derece olabilir
  - Kisa boylu birisi 5 derecede oturabiir
  - Gozluk takanlar monitore daha yakin oturup hafifce one egilebilir
  - Her calisan icin AYNI esik degeri kullanmak adaletsiz olur

ORNEK:
  Genel esik: boyun_acisi > 25 derece = kambur

  Ahmet: Dogal boyun acisi 5 derece. 26 derecede gercekten kambur. ✓
  Mehmet: Dogal boyun acisi 18 derece. 26 derecede aslinda sadece
          8 derece fazla egilmis, bu normal sapma. ✗

  Kisisel model ile:
  Ahmet: Kisisel esik = 5 + 2*3 = 11 derece -> 26 derece = KAMBUR ✓
  Mehmet: Kisisel esik = 18 + 2*4 = 26 derece -> 26 derece = SINIRDA ✓

================================================================================
KALIBRASYON SURECI
================================================================================

Calisan ilk kez baglandiginda kalibrasyon yapilir:

ADIM 1: KALIBRASYON BASLAT
  - Istemci (employee_client.py) sunucudan kisisel modeli sorgular
  - API: GET /api/personal-model/{username}/
  - Eger is_calibrated=False ise kalibrasyon baslar

ADIM 2: 15 SANIYE BOYUNCA OLCUM
  - Ekranda "Lutfen dik oturun ve ekrana bakin" mesaji gorulur
  - Geri sayim baslar: 15... 14... 13... ...1
  - Her frame'de su degerler kaydedilir:
    * Boyun acisi (neck_angle)
    * Govde acisi (torso_angle)
    * Yaw acisi (sag-sol bakis)
    * Pitch acisi (yukari-asagi bakis)
  - ~450 frame (30 FPS * 15 saniye) boyunca veri toplanir

ADIM 3: ISTATISTIKLERI HESAPLA
  Toplanan verilerden ORTALAMA ve STANDART SAPMA hesaplanir:

  Ortalama (mean):
    Tum degerlerin toplami / deger sayisi
    Ornek: [10, 12, 11, 13, 10] -> ortalama = 11.2

  Standart Sapma (std):
    Degerlerin ortalamadan ne kadar saptiginin olcusu
    Dusuk std = degerler birbirine yakin (istikrarli)
    Yuksek std = degerler cok degisiyor (istikrarsiz)

ADIM 4: KISISEL ESIK DEGERLERINI HESAPLA
  Formul: esik = max(minimum_esik, ortalama + 2 * standart_sapma)

  Neden "ortalama + 2 * standart_sapma"?
    - Normal dagilimda degerlerin %95.4'u bu aralikta kalir
    - Yani kisinin dogal hareketlerinin %95'i bu esigin altinda olur
    - Esigi asmak icin normalden BELIRGIN olcude sapma olmali
    - Bu, yanlis alarmlari minimuma indirir

  Minimum esikler (cok dusuk olmamasi icin):
    - Boyun: min 15 derece
    - Govde: min 10 derece
    - Yaw: min 15 derece
    - Pitch: min 12 derece

  ORNEK HESAPLAMA:
    Ahmet'in kalibrasyon sonuclari:
      Boyun acisi: ort=8, std=3 -> esik = max(15, 8+2*3) = max(15, 14) = 15
      Govde acisi: ort=5, std=2 -> esik = max(10, 5+2*2) = max(10, 9) = 10
      Yaw acisi:   ort=3, std=4 -> esik = max(15, 3+2*4) = max(15, 11) = 15
      Pitch acisi: ort=-2, std=3 -> esik = max(12, |-2|+2*3) = max(12, 8) = 12

ADIM 5: SUNUCUYA KAYDET
  Hesaplanan degerler API ile sunucuya gonderilir:
  POST /api/calibration/save/
  {
    "username": "AhmetYilmaz",
    "neck_angle_mean": 8.0,
    "neck_angle_std": 3.0,
    "torso_angle_mean": 5.0,
    "torso_angle_std": 2.0,
    "yaw_mean": 3.0,
    "yaw_std": 4.0,
    "pitch_mean": -2.0,
    "pitch_std": 3.0,
    "calibration_samples": 450,
    "is_calibrated": true
  }

  Sunucu bu verileri PersonalModel tablosuna kaydeder ve
  calculate_thresholds() metoduyla esik degerlerini hesaplar.

================================================================================
PERSONALMODEL VERITABANI MODELI
================================================================================

Django veritabaninda her calisan icin BIR PersonalModel kaydi tutulur.

  PersonalModel:
    user               : Calisan (OneToOneField - her calisan icin tek kayit)
    is_calibrated      : Kalibre edildi mi? (True/False)
    calibrated_at      : Kalibrasyon tarihi
    calibration_samples: Kac ornek toplandi (orn: 450)

    # Kalibrasyon olcumleri (ortalama ve standart sapma)
    neck_angle_mean    : Boyun acisi ortalamasi
    neck_angle_std     : Boyun acisi standart sapmasi
    torso_angle_mean   : Govde acisi ortalamasi
    torso_angle_std    : Govde acisi standart sapmasi
    yaw_mean           : Yaw acisi ortalamasi
    yaw_std            : Yaw acisi standart sapmasi
    pitch_mean         : Pitch acisi ortalamasi
    pitch_std          : Pitch acisi standart sapmasi

    # Hesaplanan kisisel esikler
    neck_threshold     : Kisisel boyun esigi (varsayilan: 25)
    torso_threshold    : Kisisel govde esigi (varsayilan: 15)
    yaw_threshold      : Kisisel yaw esigi (varsayilan: 25)
    pitch_threshold    : Kisisel pitch esigi (varsayilan: 20)

================================================================================
ISTEMCI TARAFINDA KULLANIM
================================================================================

employee_client.py'deki kalibrasyon akisi:

  1. Sunucudan kisisel model sorgula:
     GET /api/personal-model/{username}/

  2. Eger kalibre degklse -> run_calibration() cagir:
     - 15 saniye boyunca frame analiz et
     - Acilari topla
     - Ortalama ve std hesapla
     - Sunucuya kaydet

  3. Kalibre ise -> esik degerlerini yukle:
     - PostureAnalyzer.neck_threshold = model.neck_threshold
     - PostureAnalyzer.torso_threshold = model.torso_threshold
     - GazeAnalyzer.yaw_threshold = model.yaw_threshold
     - GazeAnalyzer.pitch_threshold = model.pitch_threshold

  4. Analizorler artik kisisel esiklerle calisir

KALIBRASYON GORSEL GORUNUMU:
  - OpenCV penceresi uzerinde overlay gosterilir
  - Yesil cerceve ile "KALIBRASYON - Dik oturun" yazisi
  - Ilerleme cubugu (progress bar) gosterilir
  - Geri sayim (15... 14... 13...) gorunur
  - Kalibrasyon bitince "Kalibrasyon tamamlandi!" mesaji

YENIDEN KALIBRASYON:
  --calibrate komutu satiri argumanityle zorla kalibrasyon yapilabilir:
  python client/employee_client.py --server ... --room ... --user ... --calibrate

================================================================================
DOSYA KONUMLARI
================================================================================

  dashboard/models.py          - PersonalModel veritabani modeli
  dashboard/views.py           - api_personal_model, api_calibration_save views
  client/employee_client.py    - run_calibration(), load_personal_model()

================================================================================
"""
