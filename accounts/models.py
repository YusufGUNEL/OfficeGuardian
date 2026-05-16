from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('super_admin', 'Süper Admin'),
        ('yonetici', 'Yönetici'),
        ('takim_lideri', 'Takım Lideri'),
        ('calisan', 'Çalışan'),
    ]
    THEME_CHOICES = [
        ('dark', 'Koyu'),
        ('light', 'Açık'),
    ]
    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default='calisan')
    theme = models.CharField(max_length=5, choices=THEME_CHOICES, default='dark', verbose_name='Tema')
    avatar_initial = models.CharField(max_length=2, blank=True, verbose_name='Avatar Baş Harfi')

    # Takim lideri icin: hangi odalara erisimi var
    assigned_rooms = models.ManyToManyField(
        'dashboard.Room', blank=True,
        related_name='assigned_leaders', verbose_name='Atanan Odalar'
    )

    def is_super_admin(self):
        return self.role == 'super_admin'

    def is_yonetici(self):
        return self.role in ('yonetici', 'super_admin')

    def is_takim_lideri(self):
        return self.role == 'takim_lideri'

    def is_calisan(self):
        return self.role == 'calisan'

    def can_create_room(self):
        return self.role in ('super_admin', 'yonetici')

    def can_delete_room(self):
        return self.role in ('super_admin', 'yonetici')

    def can_send_warning(self):
        return self.role in ('super_admin', 'yonetici', 'takim_lideri')

    def can_view_logs(self):
        return self.role in ('super_admin', 'yonetici', 'takim_lideri')

    def can_export(self):
        return self.role in ('super_admin', 'yonetici')

    def can_manage_users(self):
        return self.role == 'super_admin'

    def get_accessible_rooms(self):
        """Kullanicinin erisebilecegi odalari dondur."""
        from dashboard.models import Room
        if self.role == 'super_admin':
            return Room.objects.all()
        elif self.role == 'yonetici':
            return Room.objects.filter(created_by=self)
        elif self.role == 'takim_lideri':
            return self.assigned_rooms.all()
        return Room.objects.none()

    def get_initials(self):
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        return self.username[:2].upper()

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
