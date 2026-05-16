"""Kamera Yönetim Modülü

Bu modül, bilgisayara bağlı tüm kameraları (dahili webcam, USB kamera,
DroidCam gibi sanal kameralar) yöneten CameraManager sınıfını içerir.

Desteklenen kamera türleri:
    - Dahili webcam (laptop kamerası)
    - USB webcam (harici kamera)
    - Sanal kameralar (DroidCam, EpocCam vb.)

Thread Güvenliği:
    Tüm kamera işlemleri threading.Lock ile korunur.
    Bu sayede birden fazla thread aynı anda kameraya erişmeye
    çalıştığında veri bozulması önlenir.
"""

import cv2
import threading


class CameraManager:
    """Kamera yönetimi — dahili webcam ve sanal kameraları (DroidCam vb.) destekler.

    Bu sınıf bir kamerayı açar, frame (görüntü karesi) okur ve kapatır.

    Kamera açma stratejisi:
        1. Öncelikle DirectShow (CAP_DSHOW) ile dener — Windows'ta en stabil
        2. Başarısız olursa DSHOW'suz tekrar dener — sanal kameralar için

    Kullanım:
        kamera = CameraManager(index=0, width=640, height=480)
        if kamera.open():
            basarili, frame = kamera.read()
            if basarili:
                # frame ile işlem yap...
            kamera.release()
    """

    def __init__(self, index: int = 0, width: int = 640, height: int = 480):
        """CameraManager oluşturur.

        Parametreler:
            index  : Kamera indeksi (0 = varsayılan kamera, 1 = ikinci kamera vb.)
            width  : İstenen görüntü genişliği (piksel)
            height : İstenen görüntü yüksekliği (piksel)
        """
        self.index = index
        self.width = width
        self.height = height
        self._cap = None                # OpenCV VideoCapture nesnesi
        self._lock = threading.Lock()   # Thread güvenlik kilidi

    @staticmethod
    def list_cameras(max_check: int = 5) -> list[dict]:
        """Kullanılabilir kameraları listeler.

        0'dan max_check'e kadar tüm kamera indekslerini dener.
        Her birini açmaya çalışır, açılanın bilgilerini döner.

        Parametreler:
            max_check: Kontrol edilecek maksimum kamera indeksi

        Döner:
            Sözlük listesi. Her sözlük: {"index": 0, "name": "Kamera 0", "resolution": "640x480"}
        """
        cameras = []
        for i in range(max_check):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cameras.append({"index": i, "name": f"Kamera {i}", "resolution": f"{w}x{h}"})
                cap.release()
        return cameras

    def open(self) -> bool:
        """Kamerayı açar ve ayarları uygular.

        Açma stratejisi:
            1. Öncelikle DirectShow (DSHOW) ile dener — Windows'ta en stabil yöntem
            2. Başarısız olursa DSHOW olmadan tekrar dener — DroidCam gibi sanal
               kameralar bazen DirectShow'u desteklemez

        Döner:
            True = kamera başarıyla açıldı, False = açılamadı
        """
        with self._lock:
            # Önceki kamera açıksa kapat
            if self._cap and self._cap.isOpened():
                self._cap.release()

            # İlk deneme: DirectShow ile aç (Windows'ta en stabil)
            self._cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                # İkinci deneme: DSHOW olmadan aç (sanal kameralar için)
                self._cap = cv2.VideoCapture(self.index)

            if self._cap.isOpened():
                # Çözünürlük ve buffer ayarlarını uygula
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                # Buffer boyutunu 1 yap — en güncel frame'i al (gecikmeyi azaltır)
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                return True
            return False

    def read(self):
        """Kameradan bir görüntü karesi (frame) okur.

        Döner:
            (True, frame) = başarılı okuma, frame BGR formatında numpy dizisi
            (False, None) = okuma başarısız (kamera kapalı veya hata)
        """
        with self._lock:
            if self._cap and self._cap.isOpened():
                ret, frame = self._cap.read()
                if ret:
                    return True, frame
            return False, None

    def release(self):
        """Kamerayı serbest bırakır ve kaynakları temizler.
        Uygulama kapanırken veya kamera değiştirilirken çağrılmalıdır.
        """
        with self._lock:
            if self._cap:
                self._cap.release()
                self._cap = None

    @property
    def is_opened(self) -> bool:
        """Kameranın açık olup olmadığını kontrol eder."""
        with self._lock:
            return self._cap is not None and self._cap.isOpened()
