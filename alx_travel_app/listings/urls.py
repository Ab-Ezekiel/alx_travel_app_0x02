# listings/urls.py
from django.urls import path
from .views import InitiatePaymentAPIView, VerifyPaymentAPIView

urlpatterns = [
    path('payments/initiate/', InitiatePaymentAPIView.as_view(), name='payments-initiate'),
    path('payments/verify/<str:tx_ref>/', VerifyPaymentAPIView.as_view(), name='payments-verify'),
]
