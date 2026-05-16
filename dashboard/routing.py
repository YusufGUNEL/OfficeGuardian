from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/employee/(?P<room_code>\w+)/(?P<username>\w+)/$', consumers.EmployeeConsumer.as_asgi()),
    re_path(r'ws/admin/(?P<room_code>\w+)/$', consumers.AdminConsumer.as_asgi()),
]
