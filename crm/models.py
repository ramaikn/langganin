import uuid

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q


class Customer(models.Model):
    name = models.CharField("Nama", max_length=100)
    phone = models.CharField("Nomor telepon", max_length=15, unique=True,
                             validators=[RegexValidator(r"^62[0-9]{8,13}$", "Gunakan format 62 diikuti 8–13 digit.")])
    email = models.EmailField("Email", blank=True)
    consent = models.BooleanField("Bersedia menerima kampanye", default=False)
    points = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Sale(models.Model):
    CHANNELS = [("store", "Gerai"), ("web", "Website"), ("app", "Aplikasi")]
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales")
    reference = models.CharField("Nomor struk", max_length=64, unique=True)
    amount = models.PositiveIntegerField("Nilai transaksi (Rp)", validators=[MinValueValidator(1000)])
    channel = models.CharField("Kanal", max_length=10, choices=CHANNELS)
    points = models.PositiveIntegerField()
    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(amount__gte=1000), name="sale_min_amount")]


class Reward(models.Model):
    name = models.CharField("Nama hadiah", max_length=100, unique=True)
    description = models.CharField("Deskripsi", max_length=240, blank=True)
    cost = models.PositiveIntegerField("Poin dibutuhkan", validators=[MinValueValidator(1)])
    stock = models.PositiveIntegerField("Stok")
    active = models.BooleanField("Aktif", default=True)

    class Meta:
        ordering = ["cost", "name"]
        constraints = [models.CheckConstraint(condition=Q(cost__gte=1), name="reward_positive_cost")]

    def __str__(self):
        return f"{self.name} · {self.cost} poin"


class Redemption(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="redemptions")
    reward = models.ForeignKey(Reward, on_delete=models.PROTECT)
    cost = models.PositiveIntegerField()
    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PointEntry(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="ledger")
    delta = models.IntegerField()
    sale = models.OneToOneField(Sale, null=True, blank=True, on_delete=models.PROTECT)
    redemption = models.OneToOneField(Redemption, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.CheckConstraint(
            condition=(Q(sale__isnull=False, redemption__isnull=True, delta__gte=0) |
                       Q(sale__isnull=True, redemption__isnull=False, delta__lt=0)), name="ledger_source_direction")]


class Campaign(models.Model):
    SEGMENTS = [("all", "Semua pelanggan"), ("loyal", "Pelanggan loyal"), ("at_risk", "Perlu disapa"), ("new", "Pelanggan baru")]
    title = models.CharField("Judul", max_length=100)
    body = models.TextField("Pesan", max_length=1000)
    segment = models.CharField("Segmen", max_length=16, choices=SEGMENTS)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Notification(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="notifications")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="notifications")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["campaign", "customer"], name="campaign_once_per_customer")]


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    entity = models.CharField(max_length=80)
    entity_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class DemoMarker(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
