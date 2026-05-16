"""
================================================================================
                    OFFICEGUARDIAN - YUZ TANIMA SISTEMI
================================================================================

Bu dosya, OfficeGuardian'daki yuz tanima sisteminin nasil calistigini
aciklar. Yuz tanima, "kamerada kim var?" sorusuna cevap verir.

================================================================================
NEDEN YUZ TANIMA?
================================================================================

Sorun:
  - Calisan istemciye baglanadiginda kullanici adini giriyor
  - Ama baska birisi o bilgisayarin basina oturabilir
  - Veya ofis modunda birden fazla kisi var, hangisi kim?

Cozum:
  - Her calisanin yuzunu kaydet
  - Kamerada gorunen yuzu kayitli yuzlerle karsilastir
  - Eslesen calisanin verilerini guncelle

================================================================================
MEDIAPIPE TABANLI YUZ ENCODING
================================================================================

Bu projede yuz tanima icin face_recognition veya dlib gibi
agir kutuphaneler KULLANILMAZ. Bunun yerine ZATEN MEVCUT olan
MediaPipe FaceLandmarker kullanilir.

ENCODING NEDIR?
  Yuz encoding, bir yuzu SAYISAL VEKTOR olarak temsil eder.
  Bu vektor, yuzun ozelliklerini (gozler arasi mesafe, burun boyutu,
  cene genisligi vb.) sayisal olarak ifade eder.

MEDIAPIPE ILE ENCODING OLUSTURMA:
  MediaPipe FaceLandmarker, yuz uzerinde 468 nokta tespit eder.
  Bu noktalardan ANAHTAR noktalar secilerek bir encoding vektoru olusturulur.

  Secilen noktalar:
    [1, 33, 61, 199, 263, 291, 4, 6, 10, 152]
    # burun, sol_goz, sol_agiz, cene_alt, sag_goz, sag_agiz,
    # burun_ucu, burun_koprusu, alin, cene

  Her noktanin x, y, z koordinatlari alinir:
    encoding = [nokta1.x, nokta1.y, nokta1.z, nokta2.x, nokta2.y, ...]

  Sonuc: 30 elemanli bir float dizisi (10 nokta * 3 koordinat)

================================================================================
YUZ KAYIT SURECI
================================================================================

ADIM 1: KAMERADAN YUZ YAKALA
  - Calisan ilk kez baglandiginda veya yuz kaydi yoksa
  - Kameradan bir frame alinir
  - MediaPipe ile yuz noktalari tespit edilir

ADIM 2: ENCODING HESAPLA
  - 10 anahtar noktanin x, y, z koordinatlari alinir
  - 30 elemanli numpy dizisi olusturulur
  - Bu dizi yuzun "parmak izi" gibidir

ADIM 3: SUNUCUYA GONDER
  - Encoding verisi base64 ile encode edilir
  - POST /api/face/register/ endpointine gonderilir
  {
    "username": "AhmetYilmaz",
    "encoding": "base64_encoded_numpy_array"
  }

ADIM 4: VERITABANINA KAYDET
  - FaceEncoding modeli ile kaydedilir
  - encoding_data alani BinaryField (ikili veri)
  - Her kullanici icin TEK kayit (OneToOneField)

================================================================================
YUZ TANIMA SURECI (ESLESTIRME)
================================================================================

ADIM 1: ODADAKI TUM KAYITLI YUZLERI YUKLE
  - GET /api/face/encodings/{room_code}/
  - Odadaki tum aktif calisanlarin yuz encodingleri doner
  - Sonuc: {username: numpy_array, ...} sozlugu

ADIM 2: KAMERADAKI YUZU ANALIZ ET
  - Her frame'de MediaPipe ile yuz tespit edilir
  - Tespit edilen yuzun encoding'i hesaplanir

ADIM 3: MEVCUT ENCODINGLERLE KARSILASTIR
  - Kameradaki yuz encoding'i ile veritabanindaki tum encodingler
    arasindaki OKLID MESAFESI hesaplanir

  Oklid Mesafesi:
    mesafe = sqrt(sum((a_i - b_i)^2))

    Burada a = kameradaki yuz, b = kayitli yuz
    Her ikisi de 30 elemanli vektorler

ADIM 4: EN YAKIN ESLESTIRMEYI BUL
  - En kucuk mesafeye sahip kayitli yuz secilir
  - Eger mesafe bir esik degerinin altindaysa -> ESLESTI
  - Esik degerinin ustundeyse -> TANINMADI (bilinmeyen kisi)

  Esik degeri: ~0.1 (normalize koordinatlarla)
  Bu deger deneysel olarak belirlenmistir.

ORNEK:
  Kameradaki yuz encoding'i: [0.45, 0.52, 0.01, ...]

  Kayitli yuzler:
    Ahmet:  [0.44, 0.53, 0.01, ...] -> mesafe = 0.02 (yakin!)
    Mehmet: [0.38, 0.48, 0.03, ...] -> mesafe = 0.09
    Ayse:   [0.50, 0.60, 0.02, ...] -> mesafe = 0.12

  En yakin: Ahmet (0.02) -> Eslesti! Bu kisi Ahmet.

================================================================================
FACEENCODING VERITABANI MODELI
================================================================================

  FaceEncoding:
    user          : Calisan (OneToOneField)
    encoding_data : BinaryField  # numpy dizisinin bytes hali
    created_at    : Olusturma tarihi
    updated_at    : Son guncelleme tarihi

  Neden BinaryField?
    - numpy dizileri dogrudan veritabaninda saklanamaz
    - numpy.tobytes() ile bytes'a cevrilir
    - numpy.frombuffer() ile geri donusturulur
    - Veritabaninda binary (ikili) olarak tutulur

================================================================================
ISTEMCI TARAFINDA KODLAR
================================================================================

employee_client.py'deki yuz tanima fonksiyonlari:

  register_face(frame_rgb):
    - Frame'den yuz encoding'i hesapla
    - base64 ile encode et
    - POST /api/face/register/ ile sunucuya gonder

  load_face_encodings():
    - GET /api/face/encodings/{room_code}/
    - Odadaki tum yuz encodinglerini indir
    - {username: numpy_array} sozlugu olustur

  recognize_face(frame_rgb):
    - Frame'den yuz encoding'i hesapla
    - load_face_encodings() ile kayitli yuzlerle karsilastir
    - En yakin eslestirmeyi don (veya None)

================================================================================
GUVENLIK VE GIZLILIK NOTU
================================================================================

  - Yuz encoding'i, yuzun SAYISAL TEMSILI'dir, goruntusu DEG+L
  - Encoding'den yuzun geri olusturulmasi MUMKUN DEGILDIR
  - Veriler sunucu veritabaninda binary olarak saklanir
  - API'ler yetki kontrolu gerektirir (oturum acik olmali)
  - Encoding'ler odaya ozel indirilir (baska odanin verileri gelmez)

================================================================================
SINIRLILIKLAR
================================================================================

  1. MediaPipe encoding, face_recognition kutuphanesine gore
     daha az hassastir (10 nokta vs 128 boyutlu vektor)
  2. Aydinlanma degisiklikleri dogrulugu dusurabilir
  3. Gozluk, maske gibi aksesuarlar tanima basarisini etkiler
  4. En iyi sonuc: iyi aydinlatilmis ortam, yuze dogru kamera

================================================================================
DOSYA KONUMLARI
================================================================================

  dashboard/models.py          - FaceEncoding modeli
  dashboard/views.py           - api_face_register, api_face_encodings
  client/employee_client.py    - register_face, load_face_encodings, recognize_face

================================================================================
"""
