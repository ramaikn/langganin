from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, Customer, DemoMarker, Sale


@transaction.atomic
def refine_demo():
    """Rapikan hanya record sintetis yang dikenali, tanpa menghapus data pengguna."""
    if not DemoMarker.objects.exists():
        raise ValidationError("Perintah ini hanya untuk database contoh.")
    people = Customer.objects.filter(phone__startswith="62000000").order_by("pk")
    total = 0
    for person in people:
        if person.email.endswith("@example.invalid"):
            person.email = person.name.lower().replace(" ", ".") + "@example.com"
            person.save(update_fields=["email"])
        first = person.sales.order_by("created_at").first()
        if first and person.created_at > first.created_at:
            Customer.objects.filter(pk=person.pk).update(created_at=first.created_at - timedelta(days=2))
        for sale in person.sales.filter(reference__startswith="DEMO-"):
            day = timezone.localtime(sale.created_at).strftime("%y%m%d")
            Sale.objects.filter(pk=sale.pk).update(reference=f"TRX-{day}-{sale.pk:05d}")
            AuditEvent.objects.filter(entity="sale", entity_id=sale.pk).update(created_at=sale.created_at)
            total += 1
        for entry in person.redemptions.select_related("reward"):
            AuditEvent.objects.filter(entity="redemption", entity_id=entry.pk).update(created_at=entry.created_at)
    return total
