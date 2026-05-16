from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('rooms/', views.room_manage, name='room_manage'),
    path('rooms/<int:room_id>/toggle/', views.room_toggle, name='room_toggle'),
    path('employee/<str:username>/', views.employee_detail, name='employee_detail'),
    path('logs/', views.logs_view, name='logs'),
    path('export/', views.export_csv, name='export_csv'),
    path('export-excel/', views.export_excel, name='export_excel'),
    path('room/<str:room_code>/launcher/', views.download_launcher, name='download_launcher'),
    path('download-script/', views.download_client_script, name='download_client_script'),
    path('room/<int:room_id>/delete/', views.room_delete, name='room_delete'),
    path('join/', views.join_room, name='join_room'),
    path('panel/', views.employee_panel, name='employee_panel'),
    path('warning/<int:warning_id>/read/', views.mark_warning_read, name='mark_warning_read'),
    path('daily-report/', views.daily_report, name='daily_report'),
    path('users/', views.user_manage, name='user_manage'),
    path('api/notifications/', views.notifications_api, name='notifications_api'),
    path('api/notifications/read-all/', views.notifications_read, name='notifications_read'),
    path('api/notifications/<int:notif_id>/read/', views.notification_read_single, name='notification_read_single'),
    path('api/personal-model/<str:username>/', views.api_personal_model, name='api_personal_model'),
    path('api/calibration/save/', views.api_calibration_save, name='api_calibration_save'),
    path('api/face/register/', views.api_face_register, name='api_face_register'),
    path('api/face/encodings/<str:room_code>/', views.api_face_encodings, name='api_face_encodings'),
    path('api/active-rooms/', views.get_active_rooms, name='get_active_rooms'),
]
