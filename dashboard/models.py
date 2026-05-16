import random
import string
from django.db import models
from django.conf import settings


def generate_room_code():
    """6 haneli benzersiz oda kodu üretir."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Room.objects.filter(code=code).exists():
            return code


class Room(models.Model):
    name = models.CharField(max_length=100, verbose_name='Oda Adı')
    code = models.CharField(max_length=6, unique=True, default=generate_room_code, verbose_name='Oda Kodu')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='rooms', verbose_name='Oluşturan'
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    created_at = models.DateTimeField(auto_now_add=True)

    # Mola hatırlatıcı ayarları
    break_reminder_enabled = models.BooleanField(default=False, verbose_name='Mola Hatırlatıcı')
    break_work_minutes = models.PositiveIntegerField(default=25, verbose_name='Çalışma Süresi (dk)')
    break_rest_minutes = models.PositiveIntegerField(default=5, verbose_name='Mola Süresi (dk)')

    class Meta:
        verbose_name = 'Oda'
        verbose_name_plural = 'Odalar'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def online_count(self):
        return self.sessions.filter(is_online=True).count()


class EmployeeSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='employee_sessions', verbose_name='Çalışan'
    )
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE,
        related_name='sessions', verbose_name='Oda'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=True, verbose_name='Çevrimiçi')

    class Meta:
        verbose_name = 'Çalışan Oturumu'
        verbose_name_plural = 'Çalışan Oturumları'
        ordering = ['-started_at']

    def __str__(self):
        status = "Aktif" if self.is_online else "Kapalı"
        return f"{self.user.username} @ {self.room.name} [{status}]"


class PostureLog(models.Model):
    session = models.ForeignKey(
        EmployeeSession, on_delete=models.CASCADE,
        related_name='posture_logs', verbose_name='Oturum'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    neck_angle = models.FloatField(verbose_name='Boyun Açısı')
    torso_angle = models.FloatField(verbose_name='Gövde Açısı')
    is_good = models.BooleanField(verbose_name='İyi Postür')
    score = models.IntegerField(verbose_name='Skor')

    class Meta:
        verbose_name = 'Postür Logu'
        verbose_name_plural = 'Postür Logları'
        ordering = ['-timestamp']

    def __str__(self):
        status = "İyi" if self.is_good else "Kötü"
        return f"{self.session.user.username} - {status} ({self.score})"


class WorkStatusLog(models.Model):
    session = models.ForeignKey(
        EmployeeSession, on_delete=models.CASCADE,
        related_name='work_logs', verbose_name='Oturum'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    is_working = models.BooleanField(verbose_name='Çalışıyor')
    yaw = models.FloatField(verbose_name='Yaw Açısı')
    pitch = models.FloatField(verbose_name='Pitch Açısı')

    class Meta:
        verbose_name = 'Çalışma Logu'
        verbose_name_plural = 'Çalışma Logları'
        ordering = ['-timestamp']

    def __str__(self):
        status = "Çalışıyor" if self.is_working else "Mola"
        return f"{self.session.user.username} - {status}"


class Warning(models.Model):
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sent_warnings', verbose_name='Gönderen'
    )
    to_session = models.ForeignKey(
        EmployeeSession, on_delete=models.CASCADE,
        related_name='warnings', verbose_name='Hedef Oturum'
    )
    message = models.CharField(max_length=500, verbose_name='Mesaj')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False, verbose_name='Okundu')

    class Meta:
        verbose_name = 'Uyarı'
        verbose_name_plural = 'Uyarılar'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.from_user.username} -> {self.to_session.user.username}: {self.message[:50]}"


class Notification(models.Model):
    NOTIF_TYPES = [
        ('warning', 'Uyarı'),
        ('info', 'Bilgi'),
        ('success', 'Başarı'),
        ('system', 'Sistem'),
        ('posture', 'Postür Uyarısı'),
        ('connect', 'Bağlantı'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='Kullanıcı'
    )
    notif_type = models.CharField(max_length=10, choices=NOTIF_TYPES, default='info', verbose_name='Tip')
    title = models.CharField(max_length=200, verbose_name='Başlık')
    message = models.CharField(max_length=500, verbose_name='Mesaj')
    is_read = models.BooleanField(default=False, verbose_name='Okundu')
    created_at = models.DateTimeField(auto_now_add=True)
    related_room = models.ForeignKey(
        'Room', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notifications', verbose_name='İlgili Oda'
    )

    class Meta:
        verbose_name = 'Bildirim'
        verbose_name_plural = 'Bildirimler'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_notif_type_display()}] {self.title}"


class PersonalModel(models.Model):
    """Kisiye ozel ML kalibrasyon modeli.
    Calisanin dogal postür ve bakis degerlerini kaydeder.
    Kalibrasyon sirasinda olculen ortalamalar ve standart sapmalar tutulur.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='personal_model', verbose_name='Çalışan'
    )
    is_calibrated = models.BooleanField(default=False, verbose_name='Kalibre Edildi')
    calibrated_at = models.DateTimeField(null=True, blank=True, verbose_name='Kalibrasyon Tarihi')
    calibration_samples = models.IntegerField(default=0, verbose_name='Örnek Sayısı')

    # Postür kalibrasyon degerleri
    neck_angle_mean = models.FloatField(default=0, verbose_name='Boyun Açısı Ort.')
    neck_angle_std = models.FloatField(default=5, verbose_name='Boyun Açısı Std')
    torso_angle_mean = models.FloatField(default=0, verbose_name='Gövde Açısı Ort.')
    torso_angle_std = models.FloatField(default=3, verbose_name='Gövde Açısı Std')

    # Bakış kalibrasyon degerleri
    yaw_mean = models.FloatField(default=0, verbose_name='Yaw Ort.')
    yaw_std = models.FloatField(default=5, verbose_name='Yaw Std')
    pitch_mean = models.FloatField(default=0, verbose_name='Pitch Ort.')
    pitch_std = models.FloatField(default=5, verbose_name='Pitch Std')

    # Kisisel esik degerleri (kalibrasyon sonrasi hesaplanir)
    neck_threshold = models.FloatField(default=25, verbose_name='Kişisel Boyun Eşiği')
    torso_threshold = models.FloatField(default=15, verbose_name='Kişisel Gövde Eşiği')
    yaw_threshold = models.FloatField(default=25, verbose_name='Kişisel Yaw Eşiği')
    pitch_threshold = models.FloatField(default=20, verbose_name='Kişisel Pitch Eşiği')

    class Meta:
        verbose_name = 'Kişisel Model'
        verbose_name_plural = 'Kişisel Modeller'

    def __str__(self):
        status = "Kalibre" if self.is_calibrated else "Bekliyor"
        return f"{self.user.username} - {status}"

    def calculate_thresholds(self):
        """Kalibrasyon verilerinden kisisel esik degerlerini hesapla.
        Esik = ortalama + 2 * standart sapma (ile minimum genel esik arasinda buyuk olan)
        """
        self.neck_threshold = max(15, self.neck_angle_mean + 2 * self.neck_angle_std)
        self.torso_threshold = max(10, self.torso_angle_mean + 2 * self.torso_angle_std)
        self.yaw_threshold = max(15, abs(self.yaw_mean) + 2 * self.yaw_std)
        self.pitch_threshold = max(12, abs(self.pitch_mean) + 2 * self.pitch_std)


class FaceEncoding(models.Model):
    """Yuz tanima icin kullanicinin yuz encoding verisi."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='face_encoding', verbose_name='Çalışan'
    )
    encoding_data = models.BinaryField(verbose_name='Yüz Encoding Verisi')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Yüz Encoding'
        verbose_name_plural = 'Yüz Encodingleri'

    def __str__(self):
        return f"{self.user.username} - Yüz Verisi"


class DailyStats(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='daily_stats', verbose_name='Çalışan'
    )
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE,
        related_name='daily_stats', verbose_name='Oda'
    )
    date = models.DateField(verbose_name='Tarih')
    work_seconds = models.FloatField(default=0, verbose_name='Çalışma Süresi (sn)')
    break_seconds = models.FloatField(default=0, verbose_name='Mola Süresi (sn)')
    good_posture_seconds = models.FloatField(default=0, verbose_name='İyi Postür Süresi (sn)')
    bad_posture_seconds = models.FloatField(default=0, verbose_name='Kötü Postür Süresi (sn)')

    class Meta:
        verbose_name = 'Günlük İstatistik'
        verbose_name_plural = 'Günlük İstatistikler'
        unique_together = ['user', 'room', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} - {self.date}"

    @property
    def total_seconds(self):
        return self.work_seconds + self.break_seconds

    @property
    def posture_score(self):
        total = self.good_posture_seconds + self.bad_posture_seconds
        if total == 0:
            return 0
        return round(self.good_posture_seconds / total * 100)

    @property
    def work_ratio(self):
        if self.total_seconds == 0:
            return 0
        return round(self.work_seconds / self.total_seconds * 100)
