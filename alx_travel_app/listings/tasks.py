# listings/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Payment

@shared_task
def send_payment_confirmation_email(payment_id):
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return {"status": "not_found"}

    booking = payment.booking  # adjust according to your Booking relation
    user_email = booking.user.email if hasattr(booking, "user") else booking.email

    subject = f"Payment confirmation: {booking}"
    message = f"Hello,\n\nYour payment for booking {booking.id} was successful.\nTransaction ref: {payment.tx_ref}\nAmount: {payment.amount} {payment.currency}\n\nThank you!"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])
    return {"status": "sent"}
