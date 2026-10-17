from django.urls import re_path
from api.user_data.data_views import UserDataConsumer
from api.livechat_consumers import AgentChatConsumer, VisitorChatConsumer
from arc_payments.consumers import ArcPaymentConsumer

websocket_urlpatterns = [
    re_path(r"ws/user_data/$", UserDataConsumer.as_asgi()),
    re_path(r"ws/livechat/agent/$", AgentChatConsumer.as_asgi()),
    re_path(r"ws/livechat/visitor/(?P<store_slug>[^/]+)/(?P<session_id>[^/]+)/$", VisitorChatConsumer.as_asgi()),
    re_path(r"ws/store/payment/(?P<payment_id>[^/]+)/$", ArcPaymentConsumer.as_asgi()),
]
