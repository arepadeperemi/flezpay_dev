from django.urls import path
from arc_payments.views import (
    ArcPaymentCreateView,
    ArcPaymentStatusView,
    ArcHealthView,
)

urlpatterns = [
    # Create or retrieve a payment session
    path(
        'api/store/checkout/crypto/arc/create/',
        ArcPaymentCreateView.as_view(),
        name='arc-payment-create',
    ),
    # Poll payment status (REST fallback)
    path(
        'api/store/checkout/crypto/arc/<str:payment_id>/',
        ArcPaymentStatusView.as_view(),
        name='arc-payment-status',
    ),
    # Health check
    path(
        'api/arc/health/',
        ArcHealthView.as_view(),
        name='arc-health',
    ),
]
