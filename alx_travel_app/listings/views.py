# listings/views.py
import os
import requests
import uuid
from django.utils import timezone
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Payment
from .serializers import PaymentSerializer

CHAPA_BASE = "https://api.chapa.co/v1"

def gen_tx_ref(prefix="booking"):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

class InitiatePaymentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Expected body: { "booking_id": <id>, "amount": <decimal>, "currency": "ETB", "email": "user@example.com", "first_name": "...", "last_name": "..." }
        """
        data = request.data
        booking_id = data.get("booking_id")
        amount = data.get("amount")
        email = data.get("email", request.user.email)
        first_name = data.get("first_name", request.user.first_name or "")
        last_name = data.get("last_name", request.user.last_name or "")

        if not (booking_id and amount):
            return Response({"detail": "booking_id and amount are required"}, status=status.HTTP_400_BAD_REQUEST)

        tx_ref = gen_tx_ref(prefix=f"bk{booking_id}")
        payload = {
            "amount": amount,
            "currency": data.get("currency", "ETB"),
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "tx_ref": tx_ref,
            "callback_url": settings.CHAPA_CALLBACK_URL,
            "return_url": settings.CHAPA_RETURN_URL,
            # "customization": {...} optional
        }

        headers = {
            "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        init_url = f"{CHAPA_BASE}/transaction/initialize"
        try:
            resp = requests.post(init_url, json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            return Response({"detail": "Error initiating payment", "error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        resp_json = resp.json()
        # save payment record in DB
        payment = Payment.objects.create(
            booking_id=booking_id,
            tx_ref=tx_ref,
            amount=amount,
            currency=payload["currency"],
            status=Payment.STATUS_PENDING,
            raw_response=resp_json
        )

        # Chapa returns data with checkout_url or data['data']['checkout_url'] depending on API format
        checkout_url = None
        if isinstance(resp_json, dict):
            # tries common places
            checkout_url = resp_json.get("data", {}).get("checkout_url") or resp_json.get("data", {}).get("hosted_url")
        return Response({
            "checkout_url": checkout_url,
            "tx_ref": tx_ref,
            "payment_id": payment.id,
            "init_response": resp_json
        }, status=status.HTTP_201_CREATED)


class VerifyPaymentAPIView(APIView):
    permission_classes = [permissions.AllowAny]  # allow external callback OR restrict as you require

    def get(self, request, tx_ref):
        """
        Verify payment status at Chapa and update Payment model.
        """
        headers = {"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}
        verify_url = f"{CHAPA_BASE}/transaction/verify/{tx_ref}"
        try:
            resp = requests.get(verify_url, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            return Response({"detail": "Error verifying payment", "error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        resp_json = resp.json()
        # examine resp_json to determine status - adapt to actual Chapa response structure
        # Example: resp_json['data']['status'] == 'success' or 'failed'
        data = resp_json.get("data", {})
        status_str = data.get("status") or data.get("payment_status") or ""
        chapa_tx_id = data.get("id") or data.get("tx_id") or data.get("transaction_id")

        try:
            payment = Payment.objects.get(tx_ref=tx_ref)
        except Payment.DoesNotExist:
            return Response({"detail": "Payment record not found"}, status=status.HTTP_404_NOT_FOUND)

        payment.raw_response = resp_json
        payment.chapa_tx_id = chapa_tx_id

        if status_str.lower() in ["success", "completed", "paid", "paid_success"]:
            payment.status = Payment.STATUS_COMPLETED
            payment.verified_at = timezone.now()
            payment.save()
            # trigger email via Celery task (we'll add task below)
            try:
                from .tasks import send_payment_confirmation_email
                send_payment_confirmation_email.delay(payment.id)
            except Exception:
                pass
            return Response({"detail": "Payment completed", "payment_id": payment.id, "response": resp_json})
        else:
            payment.status = Payment.STATUS_FAILED
            payment.verified_at = timezone.now()
            payment.save()
            return Response({"detail": "Payment not successful", "payment_id": payment.id, "response": resp_json}, status=400)
