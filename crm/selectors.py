from datetime import timedelta

from django.db.models import Count, Max, Sum
from django.utils import timezone

from .models import Customer


def customers():
    return Customer.objects.annotate(visits=Count("sales"), spend=Sum("sales__amount"), last_visit=Max("sales__created_at")).order_by("name", "pk")


def segment(queryset, key):
    now = timezone.now()
    if key == "loyal":
        return queryset.filter(visits__gte=3, last_visit__gte=now - timedelta(days=30))
    if key == "at_risk":
        return queryset.filter(last_visit__lt=now - timedelta(days=30))
    if key == "new":
        return queryset.filter(created_at__gte=now - timedelta(days=14), visits__lt=3)
    return queryset


def segment_label(customer):
    now = timezone.now()
    if customer.last_visit and customer.last_visit < now - timedelta(days=30):
        return "Perlu disapa"
    if customer.visits >= 3:
        return "Loyal"
    if customer.created_at >= now - timedelta(days=14):
        return "Baru"
    return "Reguler"
