import customtkinter as ctk
import requests
import sys
import os
import threading
import asyncio
from tkinter import messagebox
from PIL import Image

# Proje kok dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.employee_client import EmployeeClient

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class EmployeeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OfficeGuardian - Çalışan Girişi")
        self.geometry("400x550")
        self.resizable(False, False)

        # Logo / Baslik
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=20)
        
        self.logo_label = ctk.CTkLabel(self.header_frame, text="🛡️", font=("Arial", 40))
        self.logo_label.pack()
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="OfficeGuardian", font=("Roboto", 24, "bold"))
        self.title_label.pack()

        # Form Alani
        self.form_frame = ctk.CTkFrame(self)
        self.form_frame.pack(pady=10, padx=20, fill="both", expand=True)

        # Sunucu Adresi
        self.server_label = ctk.CTkLabel(self.form_frame, text="Sunucu Adresi:", anchor="w")
        self.server_label.pack(fill="x", padx=10, pady=(10, 0))
        self.server_entry = ctk.CTkEntry(self.form_frame, placeholder_text="localhost:8000")
        self.server_entry.insert(0, "localhost:8000")
        self.server_entry.pack(fill="x", padx=10, pady=(0, 10))

        # Odayi Listele Butonu
        self.refresh_btn = ctk.CTkButton(self.form_frame, text="🔄 Odaları Listele", command=self.fetch_rooms, fg_color="#2b2b2b", hover_color="#3a3a3a")
        self.refresh_btn.pack(fill="x", padx=10, pady=5)

        # Oda Secimi
        self.room_label = ctk.CTkLabel(self.form_frame, text="Oda Seçin:", anchor="w")
        self.room_label.pack(fill="x", padx=10, pady=(10, 0))
        self.room_combo = ctk.CTkComboBox(self.form_frame, values=["Önce listeyi yenileyin..."])
        self.room_combo.pack(fill="x", padx=10, pady=(0, 10))

        # Ad Soyad
        self.user_label = ctk.CTkLabel(self.form_frame, text="Adınız Soyadınız:", anchor="w")
        self.user_label.pack(fill="x", padx=10, pady=(10, 0))
        self.user_entry = ctk.CTkEntry(self.form_frame, placeholder_text="Örn: Ahmet Yılmaz")
        self.user_entry.pack(fill="x", padx=10, pady=(0, 10))

        # Kamera Secimi
        self.cam_label = ctk.CTkLabel(self.form_frame, text="Kamera İndeksi:", anchor="w")
        self.cam_label.pack(fill="x", padx=10, pady=(10, 0))
        self.cam_combo = ctk.CTkComboBox(self.form_frame, values=["0", "1", "2"])
        self.cam_combo.pack(fill="x", padx=10, pady=(0, 20))

        # Baslat Butonu
        self.start_btn = ctk.CTkButton(self.form_frame, text="🚀 Odaya Katıl", command=self.start_client, font=("Roboto", 16, "bold"), height=40)
        self.start_btn.pack(fill="x", padx=10, pady=20)

        # Durum Cubugu
        self.status_label = ctk.CTkLabel(self, text="Hazır", text_color="gray", font=("Arial", 12))
        self.status_label.pack(side="bottom", pady=5)
        
        self.rooms_data = []

    def fetch_rooms(self):
        server = self.server_entry.get().strip()
        if not server:
            messagebox.showerror("Hata", "Sunucu adresi giriniz!")
            return

        url = f"http://{server}/dashboard/api/active-rooms/"
        self.status_label.configure(text="Odalar aranıyor...", text_color="orange")
        self.update()

        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                self.rooms_data = data.get('rooms', [])
                
                if not self.rooms_data:
                    self.room_combo.configure(values=["Aktif oda bulunamadı"])
                    self.status_label.configure(text="Aktif oda yok", text_color="yellow")
                    return

                # ComboBox'a "Oda Adı (KOD) - Kurucu" formatinda ekle
                options = [f"{r['name']} ({r['code']}) - {r['created_by__username']}" for r in self.rooms_data]
                self.room_combo.configure(values=options)
                self.room_combo.set(options[0])
                self.status_label.configure(text=f"{len(options)} oda bulundu", text_color="green")
            else:
                self.status_label.configure(text="Sunucu hatası", text_color="red")
        except Exception as e:
            self.status_label.configure(text="Bağlantı hatası", text_color="red")
            messagebox.showerror("Bağlantı Hatası", f"Sunucuya erişilemedi:\n{e}")

    def start_client(self):
        server = self.server_entry.get().strip()
        user = self.user_entry.get().strip()
        room_selection = self.room_combo.get()
        camera_idx = int(self.cam_combo.get())

        if not user:
            messagebox.showwarning("Eksik Bilgi", "Lütfen adınızı girin!")
            return

        if not self.rooms_data or "listeyi yenileyin" in room_selection or "bulunamadı" in room_selection:
            messagebox.showwarning("Oda Seçimi", "Lütfen geçerli bir oda seçin!")
            return
            
        # Secilen metinden oda kodunu ayikla: "Yazilim (ABC123) - yonetici" -> "ABC123"
        try:
            code_start = room_selection.find('(') + 1
            code_end = room_selection.find(')')
            room_code = room_selection[code_start:code_end]
        except:
            messagebox.showerror("Hata", "Oda kodu ayrıştırılamadı!")
            return

        self.withdraw()  # Pencereyi gizle
        
        # Client'i ayri thread'de baslat (GUI donmasin diye ama asil is OpenCV penceresinde olacak)
        # Not: EmployeeClient asyncio kullaniyor, bunu thread icinde run ile calistiracagiz.
        threading.Thread(target=self.run_client_logic, args=(server, room_code, user, camera_idx), daemon=True).start()

    def run_client_logic(self, server, room_code, user, camera_idx):
        # Yeni bir event loop oluştur ve bu thread için ayarla
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            client = EmployeeClient(
                server=server,
                room_code=room_code,
                username=user,
                mode='personal',  # Calisan modu her zaman personal
                camera_index=camera_idx,
            )
            loop.run_until_complete(client.run())
        except Exception as e:
            print(f"Hata: {e}")
        finally:
            loop.close()
            # GUI thread'inde (ana thread) calismasi icin after metodu kullanilabilir 
            # ancak burada basitce self.deiconify() cagiriyoruz, thread-safe olmayabilir ama genellikle calisir.
            # Daha guvenli bir yol:
            self.after(0, self.on_client_close)

    def on_client_close(self):
        self.deiconify()
        self.status_label.configure(text="Bağlantı sonlandı", text_color="gray")

if __name__ == "__main__":
    app = EmployeeApp()
    app.mainloop()
