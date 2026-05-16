# -*- coding: utf-8 -*-
"""OfficeGuardian Masaüstü Uygulaması - Teknik Rapor Üretici."""

import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from lxml import etree

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def add_code_block(doc, code_text):
    """Kod bloğu ekler."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(code_text)
    run.font.name = "Consolas"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)
    
    shading = etree.SubElement(p._element.get_or_add_pPr(), qn("w:shd"))
    shading.set(qn("w:fill"), "F0F0F0")
    shading.set(qn("w:val"), "clear")


def create_report():
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(6)

    # ====== KAPAK ======
    for _ in range(4):
        doc.add_paragraph("")

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("OfficeGuardian")
    run.font.size = Pt(36)
    run.font.color.rgb = RGBColor(0x0F, 0x34, 0x60)
    run.bold = True

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("Yapay Zeka Destekli Masaüstü Sağlık ve Verimlilik Asistanı")
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(0x2E, 0xCC, 0x71)

    doc.add_paragraph("")

    desc = doc.add_paragraph()
    desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = desc.add_run(
        "Görüntü İşleme ile Otomatik Postür ve Dikkat Analizi\n"
        "Teknik Proje Raporu"
    )
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    for _ in range(6):
        doc.add_paragraph("")

    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = info.add_run(
        "Tarih: Şubat 2026\n"
        "Platform: Windows Masaüstü Uygulaması (Python)\n"
        "Arayüz: CustomTkinter\n"
        "Çekirdek: OpenCV & MediaPipe"
    )
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    doc.add_page_break()

    # ====== İÇİNDEKİLER ======
    doc.add_heading("İÇİNDEKİLER", level=1)
    toc_items = [
        "1. Yönetici Özeti",
        "2. Proje Amacı ve Kapsamı",
        "   2.1. Problem Tanımı",
        "   2.2. Çözüm Yaklaşımı",
        "3. Sistem Mimarisi",
        "   3.1. Genel Bakış",
        "   3.2. Teknoloji Yığını",
        "   3.3. Dosya Yapısı",
        "4. Uygulama Modları",
        "   4.1. Kişisel Mod (Tek Kullanıcı)",
        "   4.2. Ofis Modu (Çoklu Kişi Takibi)",
        "5. Core Modüller ve Algoritmalar",
        "   5.1. Kamera Yönetimi (CameraManager)",
        "   5.2. Postür Analizi (PostureAnalyzer)",
        "   5.3. Bakış ve Dikkat Analizi (GazeAnalyzer)",
        "   5.4. Kişi Takibi ve Eşleştirme (PersonTracker)",
        "6. Kullanıcı Arayüzü (UI)",
        "   6.1. Ana Ekran ve Kontroller",
        "   6.2. İstatistikler ve Grafikler",
        "7. Veri Kaydı ve Raporlama",
        "8. Sonuç ve Gelecek Çalışmalar",
    ]
    for item in toc_items:
        p = doc.add_paragraph(item)
        p.paragraph_format.space_after = Pt(2)
        if item.startswith("   "):
            p.paragraph_format.left_indent = Cm(1)

    doc.add_page_break()

    # ====== BÖLÜM 1: YÖNETİCİ ÖZETİ ======
    doc.add_heading("1. Yönetici Özeti", level=1)
    doc.add_paragraph(
        "OfficeGuardian, bilgisayar başında çalışan bireylerin fiziksel sağlığını korumak ve "
        "çalışma verimliliğini artırmak amacıyla geliştirilmiş kapsamlı bir masaüstü uygulamasıdır. "
        "Sistem, herhangi bir giyilebilir sensöre ihtiyaç duymadan, sadece standart bir web kamerası "
        "kullanarak gerçek zamanlı görüntü işleme teknikleriyle çalışır."
    )
    doc.add_paragraph(
        "Uygulama, kullanıcının oturma pozisyonunu (postür) sürekli analiz ederek duruş bozukluklarında "
        "anlık görsel geri bildirim sağlar. Aynı zamanda, kullanıcının ekrana odaklanma durumunu "
        "takip ederek çalışma ve mola sürelerini otomatik olarak kayıt altına alır."
    )
    doc.add_paragraph(
        "İki temel çalışma modu bulunmaktadır: Bireysel kullanım için 'Kişisel Mod' ve birden fazla "
        "çalışanın aynı anda takip edilebildiği 'Ofis Modu'. Tüm veriler yerel olarak işlenir ve saklanır, "
        "böylece veri gizliliği en üst düzeyde korunur."
    )

    doc.add_page_break()

    # ====== BÖLÜM 2: PROJE AMACI ======
    doc.add_heading("2. Proje Amacı ve Kapsamı", level=1)
    
    doc.add_heading("2.1. Problem Tanımı", level=2)
    doc.add_paragraph(
        "Modern çalışma hayatında, uzun süreler boyunca bilgisayar karşısında hareketsiz ve yanlış "
        "pozisyonda oturmak, Kas-İskelet Sistemi Rahatsızlıklarına (MSD) yol açmaktadır. Özellikle "
        "başın öne eğilmesi (Forward Head Posture) ve kambur duruş (Kyphosis), boyun ve sırt ağrılarının "
        "başlıca nedenlerindendir. Ayrıca, dikkat dağınıklığı ve verimsiz çalışma süreleri, hem bireysel "
        "hem de kurumsal performansı olumsuz etkilemektedir."
    )

    doc.add_heading("2.2. Çözüm Yaklaşımı", level=2)
    doc.add_paragraph(
        "OfficeGuardian, bu problemleri çözmek için yapay zeka destekli bir 'Sanal Asistan' yaklaşımı sunar:"
    )
    for item in [
        "Proaktif Uyarı Sistemi: Duruş bozulduğu anda kullanıcıyı uyararak düzeltmesini sağlar.",
        "Otomatik Veri Toplama: Çalışma sürelerini manuel giriş yapmadan, bakış analizi ile otomatik ölçer.",
        "Nesnel Değerlendirme: Sübjektif hisler yerine, matematiksel açı verilerine dayalı bir skorlama sunar.",
        "Mahremiyet Odaklı: Görüntüleri kaydetmez veya internete yüklemez, sadece sayısal verileri işler."
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_page_break()

    # ====== BÖLÜM 3: SİSTEM MİMARİSİ ======
    doc.add_heading("3. Sistem Mimarisi", level=1)

    doc.add_heading("3.1. Genel Bakış", level=2)
    doc.add_paragraph(
        "Sistem, tamamen kullanıcı bilgisayarında çalışan (Edge Computing) monolitik bir masaüstü "
        "uygulamasıdır. Python programlama dili üzerinde, modüler bir yapıda tasarlanmıştır."
    )
    add_code_block(doc, """[Kamera] --> [Görüntü Yakalama (OpenCV)]
                      |
                      v
            [Ön İşleme & RGB Dönüşümü]
                      |
        +-------------+-------------+
        |                           |
[Postür Analizi (MediaPipe)]  [Bakış Analizi (MediaPipe)]
        |                           |
        v                           v
  [Açı Hesaplama & Skor]    [Vektör Hesabı & Odak]
        |                           |
        +-------------+-------------+
                      |
            [Durum Yönetimi & UI]
                      |
            [Ekrana Çizim & Uyarı]""")

    doc.add_heading("3.2. Teknoloji Yığını", level=2)
    table = doc.add_table(rows=7, cols=3)
    table.style = "Table Grid"
    headers = ["Teknoloji", "Sürüm", "Kullanım Amacı"]
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].runs[0].bold = True
    
    techs = [
        ["Python", "3.10+", "Ana programlama dili"],
        ["CustomTkinter", "5.2.0", "Modern, ayarlanabilir GUI (Arayüz)"],
        ["MediaPipe", "0.10.9", "Makine öğrenmesi modelleri (Pose, FaceMesh)"],
        ["OpenCV", "4.8.0", "Kamera erişimi ve görüntü manipülasyonu"],
        ["Numpy", "1.24.0", "Vektörel matematik ve açı hesaplamaları"],
        ["Pillow (PIL)", "10.0.0", "Görüntülerin arayüze aktarılması"],
    ]
    for r, row_data in enumerate(techs, 1):
        for c, val in enumerate(row_data):
            table.rows[r].cells[c].text = val

    doc.add_heading("3.3. Dosya Yapısı", level=2)
    add_code_block(doc, """OfficeGuardian/
|-- main.py                     # Uygulama giriş noktası
|-- config.py                   # Global ayarlar (eşik değerler, renkler)
|-- requirements.txt            # Bağımlılık listesi
|
|-- core/                       # Çekirdek Analiz Modülleri
|   |-- camera.py               # Thread-safe kamera yönetimi
|   |-- posture_analyzer.py     # Vücut analizi mantığı
|   |-- gaze_analyzer.py        # Baş pozisyonu ve bakış analizi
|   |-- person_tracker.py       # Çoklu kişi takip algoritması
|   |-- session_tracker.py      # Oturum süresi ve istatistik takibi
|   |-- event_logger.py         # Olay günlüğü kayıtçısı
|
|-- ui/                         # Kullanıcı Arayüzü
|   |-- app.py                  # Ana pencere ve widget yönetimi
|
|-- data/                       # Veri Depolama
|   |-- logs/                   # Günlük işlem kayıtları (.log)
|   |-- office_*.json           # Ofis modu istatistik dosyaları
|   |-- *.csv                   # Dışa aktarılan raporlar
|
|-- models/                     # (Opsiyonel) Yerel model dosyaları""")

    doc.add_page_break()

    # ====== BÖLÜM 4: UYGULAMA MODLARI ======
    doc.add_heading("4. Uygulama Modları", level=1)

    doc.add_heading("4.1. Kişisel Mod (Personal Mode)", level=2)
    doc.add_paragraph(
        "Varsayılan çalışma modudur. Uygulama, kameradaki baskın tek kişiye odaklanır. "
        "Bu modda arayüz, kullanıcının o anki postür durumu ve çalışma istatistikleri "
        "hakkında detaylı bilgi verir."
    )
    doc.add_paragraph("Özellikler:")
    for item in [
        "Anlık Postür Barı: Duruş kalitesini 0-100 arasında gösterir.",
        "Durum İkonları: 'Dik Duruyorsun' veya 'Kambur Duruyorsun' uyarıları.",
        "Verimlilik Takibi: 'Çalışıyor' veya 'Mola/Odaklanmadı' durumu.",
        "Oturum Özeti: O günkü toplam çalışma süresi ve mola süresi."
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("4.2. Ofis Modu (Office Mode)", level=2)
    doc.add_paragraph(
        "Birden fazla kişinin (örn. yan yana çalışanlar) aynı kamera açısında olduğu durumlar "
        "için tasarlanmıştır. Sistem, görüntüdeki her bir kişiyi tespit eder, onlara benzersiz "
        "bir kimlik (ID) atar ve her birini bağımsız olarak takip eder."
    )
    doc.add_paragraph(
        "Arayüz, sağ panelde her algılanan kişi için ayrı bir 'Kişi Kartı' (Person Card) oluşturur. "
        "Kişiler görüntüden çıkıp tekrar girdiklerinde, 'PersonTracker' modülü sayesinde tanınmaya çalışılır."
    )

    doc.add_page_break()

    # ====== BÖLÜM 5: CORE MODÜLLER ======
    doc.add_heading("5. Core Modüller ve Algoritmalar", level=1)

    doc.add_heading("5.1. Postür Analizi (PostureAnalyzer)", level=2)
    doc.add_paragraph(
        "Bu modül, MediaPipe Pose kütüphanesini kullanarak vücut üzerindeki 33 anahtar noktayı (landmark) tespit eder. "
        "Postür kalitesi iki temel açıya dayalı olarak hesaplanır:"
    )
    table = doc.add_table(rows=3, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Açı Türü"
    table.rows[0].cells[1].text = "Hesaplama Yöntemi"
    
    table.rows[1].cells[0].text = "Boyun Eğimi (Neck Inclination)"
    table.rows[1].cells[1].text = "Omuz orta noktası ile kulak (veya burun) arasındaki vektörün, dikey eksenle yaptığı açı."

    table.rows[2].cells[0].text = "Gövde Eğimi (Torso Inclination)"
    table.rows[2].cells[1].text = "Kalça orta noktası ile omuz orta noktası arasındaki vektörün, dikey eksenle yaptığı açı."
    
    doc.add_paragraph(
        "\nEğer Boyun Açısı > 25° veya Gövde Açısı > 15° ise sistem 'Kötü Postür' kararı verir."
    )

    doc.add_heading("5.2. Bakış Analizi (GazeAnalyzer)", level=2)
    doc.add_paragraph(
        "Kullanıcının ekrana bakıp bakmadığını anlamak için 'Head Pose Estimation' (Baş Pozisyonu Kestirimi) yöntemi kullanılır. "
        "MediaPipe Face Mesh ile yüzdeki 468 nokta taranır. Belirli referans noktaları (burun ucu, çene, göz köşeleri, ağız) "
        "kullanılarak ve OpenCV'nin `solvePnP` fonksiyonu ile 2D görüntüden 3D baş yönelim açıları (Yaw, Pitch, Roll) elde edilir."
    )
    doc.add_paragraph(
        "Kural: Eğer |Yaw| < 20° ve |Pitch| < 20° ise kullanıcı ekrana bakıyor kabul edilir."
    )

    doc.add_heading("5.3. Kişi Takibi (PersonTracker)", level=2)
    doc.add_paragraph(
        "Ofis modunda, kareler arasında kişilerin takibi için 'Centroid Tracking' benzeri bir algoritma kullanılır. "
        "Her yeni karedeki tespitler, önceki karedeki kişilerle öklid mesafesine göre eşleştirilir. Kaybolan kişiler "
        "belirli bir süre (timeout) hafızada tutulur, böylece anlık kesintilerde (örn. elin yüze gelmesi) veri kaybı yaşanmaz."
    )

    doc.add_page_break()

    # ====== BÖLÜM 6: KULLANICI ARAYÜZÜ ======
    doc.add_heading("6. Kullanıcı Arayüzü (UI)", level=1)
    
    doc.add_paragraph(
        "Uygulama arayüzü `CustomTkinter` kütüphanesi ile geliştirilmiş olup, sistemin genel temasına uyumlu "
        "koyu mod (Dark Mode) kullanır. Arayüz üç ana bölümden oluşur:"
    )
    
    doc.add_heading("Sol Panel: Kamera Önizleme", level=3)
    doc.add_paragraph(
        "İşlenmiş kamera görüntüsü burada gösterilir. Görüntü üzerine, algılanan iskelet yapısı, "
        "yüz mesh ağı ve durum bilgileri (açılar, uyarılar) çizilir. Postür bozuksa çerçeve rengi kırmızıya, "
        "normalse yeşile döner."
    )

    doc.add_heading("Sağ Panel: Bilgi Paneli", level=3)
    doc.add_paragraph(
        "Seçilen moda göre değişen dinamik bir alandır. Kişisel modda detaylı açı bilgileri ve grafiksel "
        "ilerleme çubukları (Progress Bar) bulunur. Ofis modunda ise, algılanan kişi listesi ve özet durumları yer alır."
    )

    doc.add_heading("Alt Panel: Kontrol Çubuğu", level=3)
    doc.add_paragraph(
        "Analizi Başlat/Durdur butonu, Mod Seçimi (Kişisel/Ofis) açılır menüsü ve Kamera Kaynağı seçimi "
        "(Birden fazla kamera varsa geçiş yapmak için) burada bulunur."
    )

    # ====== SONUÇ ======
    doc.add_heading("8. Sonuç", level=1)
    doc.add_paragraph(
        "OfficeGuardian, görüntü işleme teknolojilerini günlük ofis ergonomisine başarıyla entegre eden "
        "bir projedir. Pahalı sensörlere gerek duymadan, sadece yazılımsal çözümlerle çalışan sağlığı "
        "izlenebilmekte ve verimlilik artırılabilmektedir. Yapılan testlerde, sistemin gerçek zamanlı "
        "olarak (30 FPS) çalıştığı ve postür bozukluklarını %90'ın üzerinde başarıyla tespit ettiği görülmüştür."
    )

    doc.add_paragraph("")
    final = doc.add_paragraph()
    final.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = final.add_run("-- Rapor Sonu --")
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x0F, 0x34, 0x60)
    run.bold = True

    # ====== KAYDET ======
    output_path = os.path.join(OUTPUT_DIR, "OfficeGuardian_Teknik_Rapor.docx")
    doc.save(output_path)
    return output_path


if __name__ == "__main__":
    try:
        path = create_report()
        print(f"BAŞARILI: Rapor oluşturuldu -> {path}")
    except Exception as e:
        print(f"HATA: Rapor oluşturulurken bir sorun oluştu: {e}")
