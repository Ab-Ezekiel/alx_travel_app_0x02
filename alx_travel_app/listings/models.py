# listings/models.py
from django.db import models
from django.conf import settings

class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    booking = models.ForeignKey('bookings.Booking', on_delete=models.CASCADE, related_name='payments', null=True)
    tx_ref = models.CharField(max_length=255, unique=True)   # transaction reference you generate
    chapa_tx_id = models.CharField(max_length=255, blank=True, null=True)  # chapa transaction id/tx id if returned
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='ETB')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    initiated_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    raw_response = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.booking} - {self.tx_ref} - {self.status}"
