from django.contrib import admin
from .models import Room, EmployeeSession, PostureLog, WorkStatusLog, Warning, DailyStats


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'created_by', 'is_active', 'created_at')
    list_filter = ('is_active',)
    readonly_fields = ('code', 'created_at')


@admin.register(EmployeeSession)
class EmployeeSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'is_online', 'started_at', 'ended_at')
    list_filter = ('is_online', 'room')


@admin.register(PostureLog)
class PostureLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'neck_angle', 'torso_angle', 'is_good', 'score', 'timestamp')
    list_filter = ('is_good',)


@admin.register(WorkStatusLog)
class WorkStatusLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'is_working', 'yaw', 'pitch', 'timestamp')
    list_filter = ('is_working',)


@admin.register(Warning)
class WarningAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_session', 'message', 'is_read', 'created_at')
    list_filter = ('is_read',)


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'date', 'work_seconds', 'break_seconds', 'posture_score', 'work_ratio')
    list_filter = ('date', 'room')
