"""
WebSocket Routing for Django Channels
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/leaderboard/(?P<quiz_uuid>[0-9a-f-]+)/$', consumers.LeaderboardConsumer.as_asgi()),
]
