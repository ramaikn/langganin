from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import AuditEvent, Campaign, Customer, Notification, PointEntry, Redemption, Reward, Sale
from .selectors import customers, segment


def audit(actor, action, instance):
    AuditEvent.objects.create(actor=actor, action=action, entity=instance._meta.model_name, entity_id=instance.pk)


@transaction.atomic
def record_sale(*, actor, customer, reference, amount, channel, request_id):
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    existing = Sale.objects.filter(request_id=request_id).first()
    if existing:
        if (existing.customer_id, existing.reference, existing.amount, existing.channel, existing.created_by_id) != (
            customer.pk, reference, amount, channel, actor.pk
        ):
            raise ValidationError("Kunci transaksi sudah dipakai untuk data berbeda.")
        return existing
    if Sale.objects.filter(reference=reference).exists():
        raise ValidationError("Nomor struk sudah tercatat. Gunakan nomor struk yang berbeda.")
    sale = Sale(customer=customer, reference=reference, amount=amount, channel=channel,
                request_id=request_id, points=amount // 10000, created_by=actor)
    sale.full_clean()
    sale.save()
    Customer.objects.filter(pk=customer.pk).update(points=F("points") + sale.points)
    PointEntry.objects.create(customer=customer, sale=sale, delta=sale.points)
    audit(actor, "Transaksi dicatat", sale)
    return sale


@transaction.atomic
def redeem(*, actor, customer, reward, request_id):
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    existing = Redemption.objects.filter(request_id=request_id).first()
    if existing:
        if (existing.customer_id, existing.reward_id, existing.created_by_id) != (customer.pk, reward.pk, actor.pk):
            raise ValidationError("Kunci penukaran sudah dipakai untuk data berbeda.")
        return existing
    reward = Reward.objects.select_for_update().get(pk=reward.pk)
    if not reward.active or reward.stock < 1:
        raise ValidationError("Hadiah tidak aktif atau stok habis.")
    if customer.points < reward.cost:
        raise ValidationError("Poin pelanggan belum cukup.")
    redemption = Redemption.objects.create(customer=customer, reward=reward, cost=reward.cost,
                                            request_id=request_id, created_by=actor)
    Customer.objects.filter(pk=customer.pk).update(points=F("points") - reward.cost)
    Reward.objects.filter(pk=reward.pk).update(stock=F("stock") - 1)
    PointEntry.objects.create(customer=customer, redemption=redemption, delta=-reward.cost)
    audit(actor, "Hadiah ditukar", redemption)
    return redemption


@transaction.atomic
def publish(*, actor, campaign_id):
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    if campaign.published_at:
        return campaign.notifications.count()
    recipients = segment(customers().filter(consent=True), campaign.segment)
    Notification.objects.bulk_create([Notification(campaign=campaign, customer=c) for c in recipients])
    campaign.published_at = timezone.now()
    campaign.save(update_fields=["published_at"])
    audit(actor, "Kampanye diterbitkan", campaign)
    return campaign.notifications.count()
