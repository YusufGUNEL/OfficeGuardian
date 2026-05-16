import json
from datetime import date
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class EmployeeConsumer(AsyncWebsocketConsumer):
    """Calisan istemci WebSocket baglantisi."""

    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.username = self.scope['url_route']['kwargs']['username']
        self.room_group = f'room_{self.room_code}'
        self.employee_group = f'employee_{self.username}'
        self._last_posture_notif = 0  # Dusuk postur bildirimi throttle

        # Gruplara katil
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.channel_layer.group_add(self.employee_group, self.channel_name)

        # Oturum olustur / guncelle
        self.session_id = await self.create_or_update_session()

        if self.session_id is None:
            await self.close()
            return

        await self.accept()

        # Oda ayarlarini calisana gonder (mola hatirlatici vb.)
        room_settings = await self.get_room_settings()
        if room_settings:
            await self.send(text_data=json.dumps({
                'type': 'room_settings',
                'settings': room_settings,
            }))

        # Yoneticilere bildir
        await self.channel_layer.group_send(
            f'admin_{self.room_code}',
            {
                'type': 'employee_connected',
                'username': self.username,
            }
        )

        # Bildirim olustur (yoneticiye)
        await self.create_notification(
            'connect', f'{self.username} baglandi',
            f'{self.username} odaya katildi.'
        )

    async def disconnect(self, close_code):
        # Oturumu kapat
        await self.close_session()

        # Gruplardan ayril
        await self.channel_layer.group_discard(self.room_group, self.channel_name)
        await self.channel_layer.group_discard(self.employee_group, self.channel_name)

        # Yoneticilere bildir
        await self.channel_layer.group_send(
            f'admin_{self.room_code}',
            {
                'type': 'employee_disconnected',
                'username': self.username,
            }
        )

        # Bildirim olustur (yoneticiye)
        await self.create_notification(
            'connect', f'{self.username} ayrildi',
            f'{self.username} odadan ayrildi.'
        )

    async def receive(self, text_data):
        import time as _time
        data = json.loads(text_data)
        msg_type = data.get('type')

        if msg_type == 'status_update':
            # Veritabanina kaydet
            await self.save_status(data.get('data', {}))

            # Dusuk postur bildirimi (5dk'da en fazla 1)
            posture = data.get('data', {}).get('posture', {})
            score = posture.get('score', 100)
            now = _time.time()
            if score < 30 and (now - self._last_posture_notif) > 300:
                self._last_posture_notif = now
                await self.create_notification(
                    'posture', f'{self.username} - Dusuk Postur!',
                    f'{self.username} postur skoru {score} seviyesine dustu.'
                )

            # Yonetici grubuna ilet
            await self.channel_layer.group_send(
                f'admin_{self.room_code}',
                {
                    'type': 'employee_status',
                    'username': self.username,
                    'data': data.get('data', {}),
                }
            )

        elif msg_type == 'office_update':
            # Ofis modu - coklu kisi
            await self.channel_layer.group_send(
                f'admin_{self.room_code}',
                {
                    'type': 'office_status',
                    'username': self.username,
                    'data': data.get('data', {}),
                }
            )

    async def warning_message(self, event):
        """Yoneticiden gelen uyari."""
        await self.send(text_data=json.dumps({
            'type': 'warning',
            'message': event['message'],
            'from': event['from_user'],
        }))

    async def break_reminder(self, event):
        """Mola hatirlatici mesaji."""
        await self.send(text_data=json.dumps({
            'type': 'break_reminder',
            'message': event.get('message', 'Mola zamani! Lutfen bir mola verin.'),
        }))

    # --- DB islemleri ---

    @database_sync_to_async
    def create_notification(self, notif_type, title, message):
        from dashboard.models import Room, Notification
        try:
            room = Room.objects.get(code=self.room_code)
            # Yoneticiye bildirim olustur
            Notification.objects.create(
                user=room.created_by,
                notif_type=notif_type,
                title=title,
                message=message,
                related_room=room,
            )
        except Room.DoesNotExist:
            pass

    @database_sync_to_async
    def get_room_settings(self):
        from dashboard.models import Room
        try:
            room = Room.objects.get(code=self.room_code)
            return {
                'break_reminder_enabled': room.break_reminder_enabled,
                'break_work_minutes': room.break_work_minutes,
                'break_rest_minutes': room.break_rest_minutes,
            }
        except Room.DoesNotExist:
            return None

    @database_sync_to_async
    def create_or_update_session(self):
        from dashboard.models import Room, EmployeeSession
        from accounts.models import CustomUser

        try:
            room = Room.objects.get(code=self.room_code, is_active=True)
        except Room.DoesNotExist:
            return None

        try:
            user = CustomUser.objects.get(username=self.username)
        except CustomUser.DoesNotExist:
            return None

        # Mevcut aktif oturumu kapat
        EmployeeSession.objects.filter(
            user=user, room=room, is_online=True
        ).update(is_online=False, ended_at=timezone.now())

        # Yeni oturum olustur
        session = EmployeeSession.objects.create(user=user, room=room, is_online=True)
        return session.id

    @database_sync_to_async
    def close_session(self):
        from dashboard.models import EmployeeSession
        if hasattr(self, 'session_id') and self.session_id:
            EmployeeSession.objects.filter(id=self.session_id).update(
                is_online=False, ended_at=timezone.now()
            )

    @database_sync_to_async
    def save_status(self, data):
        from dashboard.models import EmployeeSession, PostureLog, WorkStatusLog, DailyStats
        if not hasattr(self, 'session_id') or not self.session_id:
            return

        try:
            session = EmployeeSession.objects.get(id=self.session_id)
        except EmployeeSession.DoesNotExist:
            return

        posture = data.get('posture')
        gaze = data.get('gaze')

        if posture:
            PostureLog.objects.create(
                session=session,
                neck_angle=posture.get('neck_angle', 0),
                torso_angle=posture.get('torso_angle', 0),
                is_good=posture.get('is_good', True),
                score=posture.get('score', 0),
            )

        if gaze:
            WorkStatusLog.objects.create(
                session=session,
                is_working=gaze.get('is_working', True),
                yaw=gaze.get('yaw', 0),
                pitch=gaze.get('pitch', 0),
            )

        # Gunluk istatistikleri guncelle
        today = date.today()
        stats, _ = DailyStats.objects.get_or_create(
            user=session.user,
            room=session.room,
            date=today,
        )

        interval = 1.0  # ~1 sn aralikla gonderiliyor

        if gaze and gaze.get('is_working', True):
            stats.work_seconds += interval
        else:
            stats.break_seconds += interval

        if posture and posture.get('is_good', True):
            stats.good_posture_seconds += interval
        elif posture:
            stats.bad_posture_seconds += interval

        stats.save()


class AdminConsumer(AsyncWebsocketConsumer):
    """Yonetici dashboard WebSocket baglantisi."""

    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.admin_group = f'admin_{self.room_code}'

        # Yetki kontrolu
        user = self.scope.get('user')
        if user and user.is_authenticated and hasattr(user, 'role') and user.role in ('super_admin', 'yonetici', 'takim_lideri'):
            await self.channel_layer.group_add(self.admin_group, self.channel_name)
            await self.accept()

            # Mevcut cevrimici calisanlari gonder
            online_users = await self.get_online_users()
            await self.send(text_data=json.dumps({
                'type': 'initial_state',
                'online_users': online_users,
            }))
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.admin_group, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type')

        if msg_type == 'send_warning':
            target_username = data.get('username')
            message = data.get('message', '')
            user = self.scope.get('user')

            if target_username and message and user:
                # Uyariyi kaydet
                await self.save_warning(user.username, target_username, message)

                # Calisana ilet
                await self.channel_layer.group_send(
                    f'employee_{target_username}',
                    {
                        'type': 'warning_message',
                        'message': message,
                        'from_user': user.username,
                    }
                )

    async def employee_status(self, event):
        """Calisan durum guncellemesini yoneticiye ilet."""
        await self.send(text_data=json.dumps({
            'type': 'employee_status',
            'username': event['username'],
            'data': event['data'],
        }))

    async def office_status(self, event):
        """Ofis modu guncellemesini yoneticiye ilet."""
        await self.send(text_data=json.dumps({
            'type': 'office_status',
            'username': event['username'],
            'data': event['data'],
        }))

    async def employee_connected(self, event):
        """Calisan baglandi bildirimi."""
        await self.send(text_data=json.dumps({
            'type': 'employee_connected',
            'username': event['username'],
        }))

    async def employee_disconnected(self, event):
        """Calisan ayrildi bildirimi."""
        await self.send(text_data=json.dumps({
            'type': 'employee_disconnected',
            'username': event['username'],
        }))

    # --- DB islemleri ---

    @database_sync_to_async
    def get_online_users(self):
        from dashboard.models import Room, EmployeeSession
        try:
            room = Room.objects.get(code=self.room_code)
            sessions = EmployeeSession.objects.filter(room=room, is_online=True).select_related('user')
            return [s.user.username for s in sessions]
        except Room.DoesNotExist:
            return []

    @database_sync_to_async
    def save_warning(self, from_username, to_username, message):
        from dashboard.models import Warning, EmployeeSession
        from accounts.models import CustomUser

        try:
            from_user = CustomUser.objects.get(username=from_username)
            session = EmployeeSession.objects.filter(
                user__username=to_username,
                room__code=self.room_code,
                is_online=True
            ).first()

            if session:
                Warning.objects.create(
                    from_user=from_user,
                    to_session=session,
                    message=message,
                )
        except CustomUser.DoesNotExist:
            pass
