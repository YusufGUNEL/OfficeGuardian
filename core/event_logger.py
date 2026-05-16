"""Olay Kaydedici Modülü (Event Logger)

Bu modül, OfficeGuardian uygulamasındaki tüm önemli olayları
JSONL (JSON Lines) formatında günlük log dosyalarına kaydeder.

Desteklenen olay türleri:
    - posture_change      : Postür değişikliği (iyi <-> kötü)
    - work_status_change  : Çalışma durumu değişikliği (çalışıyor <-> mola)
    - person_enter        : Yeni kişi algılandı (ofis modu)
    - person_exit         : Kişi kayboldu (ofis modu)
    - warning             : Uyarı tetiklendi (uzun süreli kamburluk vb.)
    - session_start       : Oturum başlatıldı
    - session_stop        : Oturum durduruldu
    - mode_change         : Mod değiştirildi (kişisel <-> ofis)

Log dosyası konumu: logs/log_YYYY-MM-DD.jsonl
Her satır bağımsız bir JSON nesnesidir, örnek:
    {"ts": "2026-02-13 14:30:00", "epoch": 1771067400.0,
     "person": "Kişi 1", "event": "posture_change",
     "details": {"posture": "bad", "neck_angle": 32.5}}
"""

import json
import os
import time
from datetime import datetime

import config


class EventLogger:
    """Tüm olayları JSONL formatında günlük dosyalara kaydeder.

    Her log kaydı şu alanları içerir:
        ts     : Zaman damgası (insan okunabilir format: YYYY-MM-DD HH:MM:SS)
        epoch  : Unix zaman damgası (saniye, hesaplama için)
        person : Kişi kimliği ("self" = kişisel mod, "Kişi 1" vb. = ofis modu)
        event  : Olay türü (posture_change, work_status_change, warning vb.)
        details: Olaya özgü ek bilgiler (opsiyonel sözlük)

    Kullanım:
        logger = EventLogger()
        logger.log("posture_change", "Kişi 1", posture="bad", neck_angle=30)
        logger.close()  # Uygulama kapanırken
    """

    def __init__(self):
        # Log klasörünü oluştur (yoksa otomatik oluşturulur)
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        # Bugünün tarihini sakla (gün değişimini algılamak için)
        self._today = datetime.now().strftime("%Y-%m-%d")
        # Günün log dosyasını aç (ekleme modunda)
        self._file = self._open_log_file()

    def log(self, event_type: str, person_id: str = "self", **details):
        """Bir olayı log dosyasına kaydet.

        Parametreler:
            event_type : Olay türü (örnek: "posture_change", "warning" vb.)
            person_id  : Kişi kimliği. Kişisel modda "self", ofis modunda "Kişi 1" vb.
            **details  : Ek detaylar (anahtar=değer çiftleri olarak)

        Örnek çağırımlar:
            log("session_start", mode="Kişisel Mod")
            log("posture_change", "Kişi 2", posture="bad", neck_angle=35)
            log("warning", "self", type="posture", message="Kambur duruyor")
        """
        # Gün değiştiyse yeni log dosyası aç
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._today:
            self._file.close()
            self._today = today
            self._file = self._open_log_file()

        # Log satırını JSON nesnesi olarak oluştur
        entry = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "epoch": round(time.time(), 2),
            "person": person_id,
            "event": event_type,
        }
        if details:
            entry["details"] = details

        # Dosyaya yaz ve hemen diske boşalt (ani kapanmalarda veri kaybı önlenir)
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self):
        """Log dosyasını güvenli şekilde kapat.
        Uygulama kapanırken MUTLAKA çağrılmalıdır.
        """
        if self._file and not self._file.closed:
            self._file.close()

    # ── Dahili Yardımcı Metodlar ──────────────────────────────

    def _open_log_file(self):
        """Bugünün tarihine göre JSONL log dosyası açar.
        Dosya zaten varsa sonuna ekleme yapar (append mode).
        Dosya yoksa yeni oluşturur.
        """
        path = os.path.join(config.LOGS_DIR, f"log_{self._today}.jsonl")
        return open(path, "a", encoding="utf-8")
