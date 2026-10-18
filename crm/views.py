import uuid
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CampaignForm, CustomerForm, RedeemForm, RewardForm, SaleForm
from .models import AuditEvent, Campaign, Customer, Redemption, Reward, Sale
from .selectors import customers, segment, segment_label
from .services import audit, publish, record_sale, redeem


def manager_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.groups.filter(name="Pengelola").exists()):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def paginate(request, queryset):
    return Paginator(queryset, 20).get_page(request.GET.get("page"))


def form_page(request, form, title, back, hint=""):
    return render(request, "form.html", {"form": form, "title": title, "back": back, "hint": hint})


@login_required
def dashboard(request):
    today = timezone.localdate()
    period = request.GET.get("period", "14")
    days = int(period) if period in {"7", "14", "30"} else 14
    start = today - timedelta(days=days - 1)
    recent = Sale.objects.filter(created_at__date__gte=start, created_at__date__lte=today)
    daily = {row["day"]: row["total"] for row in recent.annotate(day=TruncDate("created_at")).values("day").annotate(total=Sum("amount"))}
    ceiling = max(daily.values(), default=1) or 1
    chart = [{"day": start + timedelta(days=i), "value": daily.get(start + timedelta(days=i), 0),
              "height": round(daily.get(start + timedelta(days=i), 0) / ceiling * 100)} for i in range(days)]
    totals = recent.aggregate(revenue=Sum("amount"), transactions=Count("pk"))
    repeat = recent.values("customer").annotate(n=Count("pk")).filter(n__gte=2).count()
    buyers = recent.values("customer").distinct().count()
    people = customers()
    return render(request, "dashboard.html", {
        "title": "Ringkasan", "totals": totals, "member_count": people.count(),
        "period": days, "start": start, "today": today,
        "repeat_rate": round(repeat / buyers * 100) if buyers else 0, "chart": chart,
        "recent_sales": Sale.objects.select_related("customer")[:6],
        "loyal_count": segment(people, "loyal").count(), "risk_count": segment(people, "at_risk").count(),
        "new_count": segment(people, "new").count(),
        "top_customers": people.filter(visits__gt=0).order_by("-spend")[:5],
    })


@login_required
def customer_list(request):
    query = request.GET.get("q", "").strip()[:100]
    key = request.GET.get("segment", "all")
    people = segment(customers(), key)
    if query:
        people = people.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    page = paginate(request, people)
    for customer in page:
        customer.segment_label = segment_label(customer)
    return render(request, "customers.html", {"title": "Pelanggan", "page": page, "q": query,
                                             "selected_segment": key, "segments": Campaign.SEGMENTS})


@login_required
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            customer = form.save()
            audit(request.user, "Pelanggan ditambahkan", customer)
        messages.success(request, "Pelanggan berhasil ditambahkan.")
        return redirect("customer_detail", pk=customer.pk)
    return form_page(request, form, "Tambah pelanggan", "customers")


@manager_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Pembaruan profil tidak boleh menimpa saldo yang berubah saat transaksi.
            Customer.objects.filter(pk=pk).update(**{field: form.cleaned_data[field] for field in form.Meta.fields})
            audit(request.user, "Profil pelanggan diperbarui", customer)
        messages.success(request, "Profil diperbarui.")
        return redirect("customer_detail", pk=pk)
    return form_page(request, form, "Ubah pelanggan", "customers")


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(customers(), pk=pk)
    return render(request, "customer_detail.html", {
        "title": customer.name, "customer": customer, "segment_label": segment_label(customer),
        "ledger": customer.ledger.select_related("sale", "redemption__reward")[:30],
        "notifications": customer.notifications.select_related("campaign")[:20],
    })


@login_required
def sales(request):
    return render(request, "sales.html", {"title": "Transaksi", "page": paginate(request, Sale.objects.select_related("customer", "created_by"))})


@login_required
def sale_create(request):
    form = SaleForm(request.POST or None, initial={"request_id": uuid.uuid4(), "channel": "store", "customer": request.GET.get("customer")})
    if request.method == "POST" and form.is_valid():
        try:
            sale = record_sale(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, "Nomor struk atau kunci transaksi sudah digunakan. Periksa riwayat transaksi.")
        else:
            messages.success(request, f"Transaksi {sale.reference} tersimpan. {sale.points} poin ditambahkan.")
            return redirect("sales")
    return form_page(request, form, "Catat transaksi", "sales", "Rp10.000 = 1 poin.")


@login_required
def rewards(request):
    return render(request, "rewards.html", {"title": "Hadiah & poin", "rewards": Reward.objects.all(),
                                           "redemptions": Redemption.objects.select_related("customer", "reward")[:15]})


@manager_required
def reward_edit(request, pk=None):
    instance = get_object_or_404(Reward, pk=pk) if pk else None
    form = RewardForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Tolak formulir lama jika stok sudah berubah sejak halaman dibuka.
            if pk:
                locked = Reward.objects.select_for_update().get(pk=pk)
                if locked.stock != form.cleaned_data["original_stock"]:
                    form.add_error(None, "Stok berubah saat Anda mengedit. Muat ulang halaman dan coba lagi.")
                    return form_page(request, form, "Ubah hadiah", "rewards")
                for field, value in form.cleaned_data.items():
                    if field != "original_stock":
                        setattr(locked, field, value)
                locked.save()
                reward = locked
            else:
                reward = form.save()
            audit(request.user, "Hadiah disimpan", reward)
        messages.success(request, "Hadiah berhasil disimpan.")
        return redirect("rewards")
    return form_page(request, form, "Ubah hadiah" if pk else "Tambah hadiah", "rewards")


@login_required
def redeem_create(request):
    form = RedeemForm(request.POST or None, initial={"request_id": uuid.uuid4(), "customer": request.GET.get("customer")})
    if request.method == "POST" and form.is_valid():
        try:
            redeem(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, "Penukaran sudah diproses. Periksa riwayat sebelum mencoba lagi.")
        else:
            messages.success(request, "Hadiah berhasil ditukar. Poin dan stok sudah diperbarui.")
            return redirect("rewards")
    return form_page(request, form, "Tukar hadiah", "rewards")


@manager_required
def campaigns(request):
    items = Campaign.objects.annotate(recipient_count=Count("notifications")).order_by("-created_at", "-pk")
    return render(request, "campaigns.html", {"title": "Kampanye", "page": paginate(request, items)})


@manager_required
def campaign_create(request):
    form = CampaignForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()
            audit(request.user, "Draf kampanye dibuat", campaign)
        messages.success(request, "Draf tersimpan. Terbitkan untuk membuat notifikasi pelanggan.")
        return redirect("campaigns")
    return form_page(request, form, "Buat kampanye", "campaigns")


@manager_required
@require_POST
def campaign_publish(request, pk):
    get_object_or_404(Campaign, pk=pk)
    count = publish(actor=request.user, campaign_id=pk)
    messages.success(request, f"Kampanye diterbitkan untuk {count} pelanggan yang menyetujui kampanye.")
    return redirect("campaigns")


@manager_required
def audit_log(request):
    return render(request, "audit.html", {"title": "Log aktivitas", "page": paginate(request, AuditEvent.objects.select_related("actor"))})


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
