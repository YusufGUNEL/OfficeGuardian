"""Oturum ve İstatistik Takip Modülü

Bu modül, kullanıcının çalışma süresi, mola süresi ve postür kalitesini
gerçek zamanlı olarak takip eder ve günlük JSON dosyalarına kaydeder.

Kaydedilen veriler:
    - work_seconds         : Ekrana bakılan toplam süre (saniye)
    - break_seconds        : Ekrandan uzak kalınan toplam süre
    - good_posture_seconds : İyi postürde geçirilen süre
    - bad_posture_seconds  : Kötü postürde geçirilen süre

Dosya konumu: data/session_YYYY-MM-DD.json
Gün değiştiğinde otomatik olarak yeni dosya oluşturulur.
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime

import config


@dataclass
class DailyStats:
    """Günlük istatistik verileri.

    Bu sınıf, bir günlük çalışma seansının tüm istatistiklerini tutar.
    JSON dosyasından yüklenir ve JSON dosyasına kaydedilir.

    Alanlar:
        date                 : Tarih (YYYY-MM-DD formatı)
        work_seconds         : Toplam çalışma süresi (saniye)
        break_seconds        : Toplam mola süresi (saniye)
        good_posture_seconds : İyi postürde geçirilen süre (saniye)
        bad_posture_seconds  : Kötü postürde geçirilen süre (saniye)

    Hesaplanan özellikler:
        total_seconds  : Toplam süre (çalışma + mola)
        posture_score  : Postür kalite skoru (%0-%100)
        work_ratio     : Verimlilik oranı (%0-%100)
    """
    date: str = ""
    work_seconds: float = 0.0
    break_seconds: float = 0.0
    good_posture_seconds: float = 0.0
    bad_posture_seconds: float = 0.0

    @property
    def total_seconds(self) -> float:
        """Toplam geçen süre (çalışma + mola)."""
        return self.work_seconds + self.break_seconds

    @property
    def posture_score(self) -> int:
        """Postür kalite skoru (yüzde).
        Formül: iyi_postür_süresi / toplam_süre * 100
        Yeterli veri yoksa %100 döner.
        """
        total = self.good_posture_seconds + self.bad_posture_seconds
        if total < 1:
            return 100
        return int((self.good_posture_seconds / total) * 100)

    @property
    def work_ratio(self) -> int:
        """Verimlilik oranı (yüzde).
        Formül: çalışma_süresi / (çalışma + mola) * 100
        Yeterli veri yoksa %0 döner.
        """
        total = self.work_seconds + self.break_seconds
        if total < 1:
            return 0
        return int((self.work_seconds / total) * 100)


class SessionTracker:
    """Çalışma/mola ve postür istatistiklerini takip eder, günlük JSON'a kaydeder.

    Her frame'de tick() metodu çağrılır. tick(), önceki çağrıdan
    bu yana geçen süreyi hesaplar ve ilgili sayaca ekler.

    Durum değişiklikleri (çalışma<->mola, iyi<->kötü postür) otomatik
    olarak EventLogger'a yazılır (eğer logger verilmişse).

    Kullanım:
        tracker = SessionTracker(logger=event_logger)
        # Her frame'de:
        tracker.tick(is_working=True, is_good_posture=True)
        # Durdurulduğunda:
        tracker.pause()
        tracker.save()
    """

    def __init__(self, logger=None):
        """SessionTracker oluşturur.

        Parametreler:
            logger: EventLogger nesnesi (opsiyonel). Verilirse durum
                    değişiklikleri otomatik loglanır.
        """
        # Veri klasörünü oluştur (yoksa)
        os.makedirs(config.DATA_DIR, exist_ok=True)
        # Bugünün tarihini sakla (gün değişimini algılamak için)
        self._today = datetime.now().strftime("%Y-%m-%d")
        # Mevcut veriyi yükle veya yeni sıfır istatistik oluştur
        self._stats = self._load_or_create()
        # Olay kaydedici (opsiyonel)
        self._logger = logger

        # Anlık durum izleme
        self._last_tick = None          # Son tick zamanı (ilk frame'de None)
        self._is_working = False        # Şu an çalışıyor mu?
        self._is_good_posture = True    # Şu an postürü iyi mi?

        # Önceki durum (durum değişikliğini tespit etmek için)
        self._prev_working = None
        self._prev_good_posture = None

    def tick(self, is_working: bool, is_good_posture: bool):
        """Her frame'de çağrılır. Geçen süreyi ilgili sayaçlara ekler.

        Parametreler:
            is_working      : Kullanıcı şu an çalışıyor mu? (ekrana bakıyor mu?)
            is_good_posture : Kullanıcının postürü iyi mi? (dik duruyor mu?)

        Bu metod şu işlemleri yapar:
            1. Gün değiştiyse mevcut veriyi kaydeder ve yeni dosya oluşturur
            2. Önceki tick'ten bu yana geçen süreyi hesaplar
            3. Geçen süreyi çalışma veya mola sayacına ekler
            4. Geçen süreyi iyi veya kötü postür sayacına ekler
            5. Durum değişikliği varsa EventLogger'a yazar
        """
        now = time.time()

        # Gün değişimi kontrolü (gece yarısı geçince yeni dosya aç)
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._today:
            self.save()
            self._today = today
            self._stats = self._load_or_create()

        # Geçen süreyi hesapla ve ilgili sayaca ekle
        if self._last_tick is not None:
            # Max 2 saniye: uygulama donması durumunda büyük atlamaları önle
            delta = min(now - self._last_tick, 2.0)

            # Çalışma/mola sayacı
            if is_working:
                self._stats.work_seconds += delta
            else:
                self._stats.break_seconds += delta

            # Postür sayacı
            if is_good_posture:
                self._stats.good_posture_seconds += delta
            else:
                self._stats.bad_posture_seconds += delta

        # Durum değişikliğini logla (sadece değişim olduğunda, her frame'de değil)
        if self._logger:
            if self._prev_working is not None and is_working != self._prev_working:
                status = "working" if is_working else "break"
                self._logger.log("work_status_change", "self", status=status)
            if self._prev_good_posture is not None and is_good_posture != self._prev_good_posture:
                status = "good" if is_good_posture else "bad"
                self._logger.log("posture_change", "self", posture=status)

        # Durumu güncelle
        self._last_tick = now
        self._is_working = is_working
        self._is_good_posture = is_good_posture
        self._prev_working = is_working
        self._prev_good_posture = is_good_posture

    def pause(self):
        """Takibi duraklatır.
        Kamera kapandığında veya durdurma butonuna basıldığında çağrılır.
        Bir sonraki tick() çağrısında süre atlaması olmaz.
        """
        self._last_tick = None

    def get_stats(self) -> DailyStats:
        """Anlık günlük istatistikleri döner."""
        return self._stats

    def save(self):
        """Mevcut istatistikleri JSON dosyasına kaydeder.
        Dosya adı: data/session_YYYY-MM-DD.json
        """
        path = self._file_path(self._today)
        data = {
            "date": self._stats.date,
            "work_seconds": round(self._stats.work_seconds, 1),
            "break_seconds": round(self._stats.break_seconds, 1),
            "good_posture_seconds": round(self._stats.good_posture_seconds, 1),
            "bad_posture_seconds": round(self._stats.bad_posture_seconds, 1),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── Dahili Yardımcı Metodlar ──────────────────────────────

    def _load_or_create(self) -> DailyStats:
        """Bugünün istatistik dosyasını yükler. Dosya yoksa sıfır değerlerle oluşturur."""
        path = self._file_path(self._today)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return DailyStats(
                date=data.get("date", self._today),
                work_seconds=data.get("work_seconds", 0),
                break_seconds=data.get("break_seconds", 0),
                good_posture_seconds=data.get("good_posture_seconds", 0),
                bad_posture_seconds=data.get("bad_posture_seconds", 0),
            )
        return DailyStats(date=self._today)

    @staticmethod
    def _file_path(date_str: str) -> str:
        """Verilen tarih için istatistik dosya yolunu döner."""
        return os.path.join(config.DATA_DIR, f"session_{date_str}.json")
