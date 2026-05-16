"""OfficeGuardian Calisan Istemci

Bu script, calisanin PC'sinde calisir:
  - Kamerayi acar, postur ve bakis analizi yapar
  - Sonuclari WebSocket ile Django sunucusuna gonderir
  - Yoneticiden gelen uyarilari gosterir
  - OpenCV penceresi ile canli onizleme saglar

Kullanim:
  python client/employee_client.py --server localhost:8000 --room ABC123 --user calisan1
  python client/employee_client.py --server localhost:8000 --room ABC123 --user calisan1 --mode office
"""

import argparse
import asyncio
import json
import sys
import os
import threading
import time
import platform

import cv2
import numpy as np

# Proje kok dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import (
    CameraManager,
    PostureAnalyzer,
    GazeAnalyzer,
    PersonTracker,
)

try:
    import websockets
except ImportError:
    print("[HATA] websockets paketi bulunamadi. Kurmak icin: pip install websockets")
    sys.exit(1)


class EmployeeClient:
    """Calisan istemci uygulamasi."""

    def __init__(self, server, room_code, username, mode='personal', camera_index=0):
        self.server = server
        self.room_code = room_code
        self.username = username
        self.mode = mode
        self.camera_index = camera_index
        self.running = False
        self.ws = None
        self.warnings = []  # Gelen uyarilar
        self.warning_display_until = 0  # Uyari gosterim zamani

        # Kalibrasyon
        self.calibration_mode = False
        self.calibration_data = {
            'neck_angles': [], 'torso_angles': [],
            'yaws': [], 'pitches': [],
        }
        self.personal_thresholds = None  # Kisisel esik degerleri

        # Yuz tanima
        self.face_recognition_enabled = False
        self.known_faces = {}  # {username: encoding}
        self.recognized_user = None

        # Mola hatirlatici
        self.break_reminder_enabled = False
        self.break_work_minutes = 25
        self.break_rest_minutes = 5
        self.break_timer_start = 0  # Calisma sayaci baslangic zamani
        self.on_break = False  # Mola modunda mi?
        self.break_until = 0  # Mola bitis zamani
        self.break_display_until = 0  # Mola uyarisi gosterim zamani

        # Core moduller
        self.camera = CameraManager(
            index=camera_index,
            width=config.FRAME_WIDTH,
            height=config.FRAME_HEIGHT,
        )

        max_persons = 1 if mode == 'personal' else config.MAX_PERSONS
        self.posture_analyzer = PostureAnalyzer(
            neck_threshold=config.NECK_ANGLE_THRESHOLD,
            torso_threshold=config.TORSO_ANGLE_THRESHOLD,
            max_persons=max_persons,
        )
        self.gaze_analyzer = GazeAnalyzer(
            yaw_threshold=config.GAZE_YAW_THRESHOLD,
            pitch_threshold=config.GAZE_PITCH_THRESHOLD,
            max_faces=max_persons,
        )

        self.person_tracker = None
        if mode == 'office':
            self.person_tracker = PersonTracker(
                max_persons=config.MAX_PERSONS,
                disappear_timeout=config.PERSON_DISAPPEAR_TIMEOUT,
                match_threshold=config.PERSON_MATCH_THRESHOLD,
            )

    def play_beep(self, frequency=800, duration=200):
        """Platform bagimsiz bip sesi cal."""
        def _beep():
            try:
                if platform.system() == 'Windows':
                    import winsound
                    winsound.Beep(frequency, duration)
                else:
                    sys.stdout.write('\a')
                    sys.stdout.flush()
            except Exception:
                pass
        threading.Thread(target=_beep, daemon=True).start()

    async def load_personal_model(self):
        """Sunucudan kisisel model verilerini yukle."""
        import urllib.request
        try:
            url = f'http://{self.server}/api/personal-model/{self.username}/'
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
                if data.get('calibrated'):
                    self.personal_thresholds = data
                    # Analyzer esik degerlerini guncelle
                    self.posture_analyzer.neck_threshold = data['neck_threshold']
                    self.posture_analyzer.torso_threshold = data['torso_threshold']
                    self.gaze_analyzer.yaw_threshold = data['yaw_threshold']
                    self.gaze_analyzer.pitch_threshold = data['pitch_threshold']
                    print(f'[KALIBRASYON] Kisisel model yuklendi: '
                          f'boyun={data["neck_threshold"]:.1f} '
                          f'govde={data["torso_threshold"]:.1f} '
                          f'yaw={data["yaw_threshold"]:.1f} '
                          f'pitch={data["pitch_threshold"]:.1f}')
                    return True
        except Exception as e:
            print(f'[KALIBRASYON] Model yuklenemedi: {e}')
        return False

    async def run_calibration(self):
        """Kalibrasyon modu - 15 saniye boyunca dogal pozisyon olcumu."""
        self.calibration_mode = True
        self.calibration_data = {
            'neck_angles': [], 'torso_angles': [],
            'yaws': [], 'pitches': [],
        }
        duration = 15  # saniye
        start_time = time.time()
        print(f'[KALIBRASYON] Basladi! {duration} saniye boyunca duz oturun ve ekrana bakin...')

        while time.time() - start_time < duration:
            ret, frame = self.camera.read()
            if not ret:
                await asyncio.sleep(0.01)
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            posture = self.posture_analyzer.analyze(frame_rgb)
            gaze = self.gaze_analyzer.analyze(frame_rgb)

            if posture:
                self.calibration_data['neck_angles'].append(posture.neck_angle)
                self.calibration_data['torso_angles'].append(posture.torso_angle)
            if gaze:
                self.calibration_data['yaws'].append(gaze.yaw)
                self.calibration_data['pitches'].append(gaze.pitch)

            # Overlay
            elapsed = time.time() - start_time
            remaining = max(0, duration - elapsed)
            h, w = frame.shape[:2]
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 70), (0, 100, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            cv2.putText(frame, 'KALIBRASYON - Duz oturun, ekrana bakin',
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f'Kalan: {remaining:.0f}sn | Ornek: {len(self.calibration_data["neck_angles"])}',
                        (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 255, 200), 1)

            # Progress bar
            progress = elapsed / duration
            bar_w = int(w * 0.8)
            bar_x = int(w * 0.1)
            cv2.rectangle(frame, (bar_x, 65), (bar_x + bar_w, 68), (100, 100, 100), -1)
            cv2.rectangle(frame, (bar_x, 65), (bar_x + int(bar_w * progress), 68), (0, 255, 0), -1)

            cv2.imshow('OfficeGuardian - Kalibrasyon', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.calibration_mode = False
                return False
            await asyncio.sleep(0.03)

        self.calibration_mode = False

        # Ortalama ve standart sapma hesapla
        cd = self.calibration_data
        if len(cd['neck_angles']) < 10:
            print('[KALIBRASYON] Yeterli veri toplanamadi!')
            return False

        result = {
            'username': self.username,
            'neck_angle_mean': float(np.mean(cd['neck_angles'])),
            'neck_angle_std': float(np.std(cd['neck_angles'])),
            'torso_angle_mean': float(np.mean(cd['torso_angles'])),
            'torso_angle_std': float(np.std(cd['torso_angles'])),
            'yaw_mean': float(np.mean(cd['yaws'])) if cd['yaws'] else 0,
            'yaw_std': float(np.std(cd['yaws'])) if cd['yaws'] else 5,
            'pitch_mean': float(np.mean(cd['pitches'])) if cd['pitches'] else 0,
            'pitch_std': float(np.std(cd['pitches'])) if cd['pitches'] else 5,
            'samples': len(cd['neck_angles']),
        }

        # Sunucuya gonder
        import urllib.request
        try:
            url = f'http://{self.server}/api/calibration/save/'
            req_data = json.dumps(result).encode('utf-8')
            req = urllib.request.Request(url, data=req_data,
                                        headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp_data = json.loads(resp.read())
                if resp_data.get('status') == 'ok':
                    print(f'[KALIBRASYON] Basarili! Kisisel esikler:')
                    print(f'  Boyun: {resp_data["neck_threshold"]:.1f}')
                    print(f'  Govde: {resp_data["torso_threshold"]:.1f}')
                    print(f'  Yaw: {resp_data["yaw_threshold"]:.1f}')
                    print(f'  Pitch: {resp_data["pitch_threshold"]:.1f}')
                    # Analyzer'lari guncelle
                    self.posture_analyzer.neck_threshold = resp_data['neck_threshold']
                    self.posture_analyzer.torso_threshold = resp_data['torso_threshold']
                    self.gaze_analyzer.yaw_threshold = resp_data['yaw_threshold']
                    self.gaze_analyzer.pitch_threshold = resp_data['pitch_threshold']
                    self.play_beep(1000, 200)
                    return True
        except Exception as e:
            print(f'[KALIBRASYON] Kayit hatasi: {e}')

        return False

    def register_face(self, frame):
        """Mevcut frame'den yuz encoding'i cikar ve sunucuya kaydet."""
        import urllib.request
        import base64
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            gaze = self.gaze_analyzer.analyze(frame_rgb)
            if gaze and gaze.face_landmarks:
                # MediaPipe face landmarks'i encoding olarak kullan
                landmarks = []
                for lm in gaze.face_landmarks:
                    landmarks.extend([lm.x, lm.y, lm.z])
                encoding_bytes = np.array(landmarks, dtype=np.float32).tobytes()
                encoding_b64 = base64.b64encode(encoding_bytes).decode('utf-8')

                url = f'http://{self.server}/api/face/register/'
                data = json.dumps({
                    'username': self.username,
                    'encoding': encoding_b64,
                }).encode('utf-8')
                req = urllib.request.Request(url, data=data,
                                            headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp_data = json.loads(resp.read())
                    if resp_data.get('status') == 'ok':
                        print(f'[YUZ] Yuz verisi kaydedildi: {self.username}')
                        return True
        except Exception as e:
            print(f'[YUZ] Kayit hatasi: {e}')
        return False

    def load_face_encodings(self):
        """Odadaki yuz encoding'lerini yukle."""
        import urllib.request
        import base64
        try:
            url = f'http://{self.server}/api/face/encodings/{self.room_code}/'
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
                for entry in data.get('encodings', []):
                    encoding_bytes = base64.b64decode(entry['encoding'])
                    encoding = np.frombuffer(encoding_bytes, dtype=np.float32)
                    self.known_faces[entry['username']] = encoding
                if self.known_faces:
                    print(f'[YUZ] {len(self.known_faces)} kisi yuklendi: {list(self.known_faces.keys())}')
                    self.face_recognition_enabled = True
        except Exception as e:
            print(f'[YUZ] Encoding yuklenemedi: {e}')

    def recognize_face(self, frame):
        """Frame'deki yuzu taniyarak kullanici adi dondur."""
        if not self.face_recognition_enabled or not self.known_faces:
            return None
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            gaze = self.gaze_analyzer.analyze(frame_rgb)
            if gaze and gaze.face_landmarks:
                landmarks = []
                for lm in gaze.face_landmarks:
                    landmarks.extend([lm.x, lm.y, lm.z])
                current = np.array(landmarks, dtype=np.float32)

                # En yakin yuz encoding'i bul
                best_match = None
                best_dist = float('inf')
                for uname, known in self.known_faces.items():
                    if len(current) == len(known):
                        dist = np.linalg.norm(current - known)
                        if dist < best_dist:
                            best_dist = dist
                            best_match = uname

                # Esik degeri (MediaPipe landmark mesafesi)
                if best_match and best_dist < 0.5:
                    return best_match
        except Exception:
            pass
        return None

    async def connect(self):
        """WebSocket baglantisi kur."""
        protocol = 'ws'
        url = f'{protocol}://{self.server}/ws/employee/{self.room_code}/{self.username}/'
        print(f'[BAGLANTI] {url} adresine baglaniliyor...')

        try:
            self.ws = await websockets.connect(url)
            print(f'[BAGLANTI] Basarili! Oda: {self.room_code}, Kullanici: {self.username}')
            return True
        except Exception as e:
            print(f'[HATA] Baglanti kurulamadi: {e}')
            return False

    async def receive_messages(self):
        """Sunucudan gelen mesajlari dinle."""
        try:
            async for message in self.ws:
                data = json.loads(message)
                if data.get('type') == 'warning':
                    warning_msg = data.get('message', '')
                    from_user = data.get('from', 'Yonetici')
                    self.warnings.append({
                        'message': warning_msg,
                        'from': from_user,
                        'time': time.time(),
                    })
                    self.warning_display_until = time.time() + 3.0
                    self.play_beep(800, 300)
                    print(f'\n[!!! UYARI !!!] {from_user}: {warning_msg}')
                elif data.get('type') == 'room_settings':
                    settings = data.get('settings', {})
                    self.break_reminder_enabled = settings.get('break_reminder_enabled', False)
                    self.break_work_minutes = settings.get('break_work_minutes', 25)
                    self.break_rest_minutes = settings.get('break_rest_minutes', 5)
                    if self.break_reminder_enabled:
                        self.break_timer_start = time.time()
                        print(f'[MOLA] Hatirlatici aktif: {self.break_work_minutes}dk calis / {self.break_rest_minutes}dk mola')
                elif data.get('type') == 'break_reminder':
                    msg = data.get('message', 'Mola zamani!')
                    self.break_display_until = time.time() + 5.0
                    print(f'\n[MOLA HATIRLATMA] {msg}')
        except websockets.exceptions.ConnectionClosed:
            print('[BAGLANTI] Sunucu baglantisi kapandi')
            self.running = False

    async def send_status(self, data):
        """Durum guncelleme gonder."""
        if self.ws:
            try:
                await self.ws.send(json.dumps(data))
            except Exception:
                pass

    def analyze_frame(self, frame):
        """Tek frame analiz et, sonuclari dondur."""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if self.mode == 'personal':
            posture = self.posture_analyzer.analyze(frame_rgb)
            gaze = self.gaze_analyzer.analyze(frame_rgb)

            # Gorsel cizimler
            if posture and posture.landmarks:
                color = (0, 200, 0) if posture.is_good else (0, 0, 255)
                self.posture_analyzer.draw_landmarks(frame, posture.landmarks, color)
            if gaze and gaze.face_landmarks:
                color = (0, 200, 0) if gaze.looking_at_screen else (0, 165, 255)
                self.gaze_analyzer.draw_landmarks(frame, gaze.face_landmarks, color)

            return {
                'type': 'status_update',
                'data': {
                    'posture': {
                        'neck_angle': round(posture.neck_angle, 1) if posture else 0,
                        'torso_angle': round(posture.torso_angle, 1) if posture else 0,
                        'is_good': posture.is_good if posture else True,
                        'score': posture.score if posture else 0,
                    },
                    'gaze': {
                        'yaw': round(gaze.yaw, 1) if gaze else 0,
                        'pitch': round(gaze.pitch, 1) if gaze else 0,
                        'is_working': gaze.looking_at_screen if gaze else True,
                    },
                    'mode': 'personal',
                }
            }
        else:
            # Ofis modu
            postures = self.posture_analyzer.analyze_all(frame_rgb)
            gazes = self.gaze_analyzer.analyze_all(frame_rgb)

            # PersonTracker guncelle
            self.person_tracker.update(postures, gazes)
            persons = self.person_tracker.get_persons()

            # Gorsel cizimler
            for pid, person in persons.items():
                if person.posture and person.posture.landmarks:
                    self.posture_analyzer.draw_landmarks(
                        frame, person.posture.landmarks, person.color_bgr)
                if person.gaze and person.gaze.face_landmarks:
                    self.gaze_analyzer.draw_landmarks(
                        frame, person.gaze.face_landmarks, person.color_bgr)

            persons_data = []
            for pid, person in persons.items():
                persons_data.append({
                    'label': person.label,
                    'posture': {
                        'neck_angle': round(person.posture.neck_angle, 1) if person.posture else 0,
                        'torso_angle': round(person.posture.torso_angle, 1) if person.posture else 0,
                        'is_good': person.posture.is_good if person.posture else True,
                        'score': person.posture.score if person.posture else 0,
                    },
                    'gaze': {
                        'yaw': round(person.gaze.yaw, 1) if person.gaze else 0,
                        'pitch': round(person.gaze.pitch, 1) if person.gaze else 0,
                        'is_working': person.is_working,
                    },
                    'is_working': person.is_working,
                })

            return {
                'type': 'office_update',
                'data': {
                    'persons': persons_data,
                }
            }

    def draw_overlay(self, frame, status_data):
        """Frame uzerine bilgi overlay'i ciz."""
        h, w = frame.shape[:2]

        if self.mode == 'personal':
            data = status_data.get('data', {})
            posture = data.get('posture', {})
            gaze = data.get('gaze', {})

            # Postur durumu
            posture_text = "Dik" if posture.get('is_good') else "Kambur"
            posture_color = (0, 200, 0) if posture.get('is_good') else (0, 0, 255)
            cv2.putText(frame, f"Postur: {posture_text} ({posture.get('score', 0)})",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, posture_color, 2)
            cv2.putText(frame, f"Boyun: {posture.get('neck_angle', 0):.1f} Govde: {posture.get('torso_angle', 0):.1f}",
                        (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            # Calisma durumu
            work_text = "Calisiyor" if gaze.get('is_working') else "Mola"
            work_color = (0, 200, 0) if gaze.get('is_working') else (0, 165, 255)
            cv2.putText(frame, f"Durum: {work_text}",
                        (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, work_color, 2)

        # Uyari goster
        if time.time() < self.warning_display_until and self.warnings:
            last_warning = self.warnings[-1]
            msg = last_warning['message']
            # Buyuk kirmizi uyari
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, h - 80), (w, h), (0, 0, 180), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            cv2.putText(frame, f"UYARI: {msg}",
                        (20, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            cv2.putText(frame, f"- {last_warning['from']}",
                        (20, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # Mola hatirlatici overlay
        if time.time() < self.break_display_until and self.on_break:
            remaining = int(self.break_until - time.time())
            mins, secs = divmod(max(0, remaining), 60)
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 60), (0, 120, 180), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            cv2.putText(frame, f"MOLA ZAMANI! Kalan: {mins:02d}:{secs:02d}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        elif self.break_reminder_enabled and not self.on_break and self.break_timer_start > 0:
            elapsed = int(time.time() - self.break_timer_start)
            total = self.break_work_minutes * 60
            remaining = max(0, total - elapsed)
            mins, secs = divmod(remaining, 60)
            cv2.putText(frame, f"Mola: {mins:02d}:{secs:02d}",
                        (w - 150, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 200, 200), 1)

        # Kisisel model gostergesi
        if self.personal_thresholds:
            cv2.putText(frame, "ML:Kisisel", (w - 130, h - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 200, 100), 1)

        # Baglanti durumu
        cv2.putText(frame, f"Oda: {self.room_code} | {self.username}",
                    (w - 280, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

    async def run(self):
        """Ana dongu."""
        # Kamerayi ac
        if not self.camera.open():
            print('[HATA] Kamera acilamadi!')
            return

        print(f'[KAMERA] Acildi (index={self.camera_index})')

        # Kisisel model yukle veya kalibrasyon yap
        has_model = await self.load_personal_model()
        if not has_model:
            print('[KALIBRASYON] Kisisel model bulunamadi. Kalibrasyon baslatiliyor...')
            await self.run_calibration()

        # Yuz kaydi yap (ilk frame'den)
        ret, first_frame = self.camera.read()
        if ret:
            self.register_face(first_frame)

        # Ofis modunda yuz encoding'lerini yukle
        if self.mode == 'office':
            self.load_face_encodings()

        # WebSocket baglan
        if not await self.connect():
            self.camera.release()
            return

        self.running = True

        # Mesaj alma gorevi
        receive_task = asyncio.create_task(self.receive_messages())

        print('[ANALIZ] Baslatildi. Cikmak icin Q tusuna basin.')
        print(f'[MOD] {self.mode.upper()}')
        print('-' * 50)

        last_send_time = 0
        send_interval = 1.0  # 1 saniye aralikla gonder

        try:
            while self.running:
                ret, frame = self.camera.read()
                if not ret:
                    await asyncio.sleep(0.01)
                    continue

                # Analiz
                status_data = self.analyze_frame(frame)

                # Overlay ciz
                self.draw_overlay(frame, status_data)

                # OpenCV penceresi goster
                cv2.imshow('OfficeGuardian - Calisan', frame)

                # Mola hatirlatici kontrolu
                now = time.time()
                if self.break_reminder_enabled:
                    if self.on_break:
                        if now >= self.break_until:
                            self.on_break = False
                            self.break_timer_start = now
                            self.break_display_until = 0
                            print('\n[MOLA] Mola bitti, calisma zamani!')
                    else:
                        elapsed = now - self.break_timer_start
                        if elapsed >= self.break_work_minutes * 60:
                            self.on_break = True
                            self.break_until = now + self.break_rest_minutes * 60
                            self.break_display_until = now + self.break_rest_minutes * 60
                            self.play_beep(600, 500)
                            print(f'\n[MOLA] Mola zamani! {self.break_rest_minutes} dakika mola verin.')

                # WebSocket ile gonder (~1 sn aralikla)
                if now - last_send_time >= send_interval:
                    await self.send_status(status_data)
                    last_send_time = now

                    # Terminal ciktisi
                    if self.mode == 'personal':
                        d = status_data.get('data', {})
                        p = d.get('posture', {})
                        g = d.get('gaze', {})
                        sys.stdout.write(
                            f"\r[{'Dik' if p.get('is_good') else 'Kambur'}] "
                            f"Skor:{p.get('score', 0)} "
                            f"Boyun:{p.get('neck_angle', 0):.1f} "
                            f"| [{'Calisiyor' if g.get('is_working') else 'Mola'}] "
                            f"Yaw:{g.get('yaw', 0):.1f}  "
                        )
                        sys.stdout.flush()

                # 'q' ile cik
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print('\n[CIKIS] Kullanici tarafindan sonlandirildi')
                    break

                await asyncio.sleep(0.01)

        except KeyboardInterrupt:
            print('\n[CIKIS] Ctrl+C ile sonlandirildi')
        finally:
            self.running = False
            receive_task.cancel()
            if self.ws:
                await self.ws.close()
            cv2.destroyAllWindows()
            self.camera.release()
            self.posture_analyzer.close()
            self.gaze_analyzer.close()
            print('[TEMIZLIK] Kaynaklar serbest birakildi')


def main():
    parser = argparse.ArgumentParser(description='OfficeGuardian Calisan Istemci')
    parser.add_argument('--server', default='localhost:8000', help='Django sunucu adresi (varsayilan: localhost:8000)')
    parser.add_argument('--room', required=True, help='Oda kodu (6 haneli)')
    parser.add_argument('--user', required=True, help='Kullanici adi')
    parser.add_argument('--mode', choices=['personal', 'office'], default='personal',
                        help='Analiz modu (varsayilan: personal)')
    parser.add_argument('--camera', type=int, default=0, help='Kamera indeksi (varsayilan: 0)')
    parser.add_argument('--calibrate', action='store_true', help='Zorla yeniden kalibrasyon yap')
    args = parser.parse_args()

    client = EmployeeClient(
        server=args.server,
        room_code=args.room,
        username=args.user,
        mode=args.mode,
        camera_index=args.camera,
    )

    asyncio.run(client.run())


if __name__ == '__main__':
    main()
