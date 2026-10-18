import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest import skipUnless

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, connections
from django.db.models import Sum
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .forms import CustomerForm
from .models import AuditEvent, Campaign, Customer, DemoMarker, Notification, PointEntry, Redemption, Reward, Sale
from .selectors import customers, segment
from .services import publish, record_sale, redeem
from .demo import refine_demo


class LoyaltyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user("pemilik", password="StrongTestPassword!2026")
        cls.manager.groups.add(Group.objects.create(name="Pengelola"))
        cls.cashier = User.objects.create_user("kasir", password="StrongCashierPassword!2026")
        cls.cashier.groups.add(Group.objects.create(name="Kasir"))
        cls.customer = Customer.objects.create(name="Pelanggan uji", phone="628123456789", consent=True)
        cls.reward = Reward.objects.create(name="Kopi", cost=3, stock=2)

    def setUp(self):
        cache.clear()

    def sale(self, **kwargs):
        data = {"actor": self.cashier, "customer": self.customer, "reference": "TEST-001", "amount": 45000,
                "channel": "store", "request_id": uuid.uuid4()}
        data.update(kwargs)
        return record_sale(**data)

    def test_sale_rounding_ledger_and_audit(self):
        sale = self.sale()
        self.customer.refresh_from_db()
        self.assertEqual(sale.points, 4)
        self.assertEqual(self.customer.points, 4)
        self.assertEqual(self.customer.ledger.aggregate(total=Sum("delta"))["total"], 4)
        self.assertTrue(AuditEvent.objects.filter(entity_id=sale.pk, entity="sale").exists())

    def test_duplicate_request_is_idempotent(self):
        key = uuid.uuid4()
        first = self.sale(request_id=key)
        second = self.sale(request_id=key)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(PointEntry.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.sale(request_id=key, amount=55000)
        with self.assertRaises(ValidationError):
            self.sale(reference="TEST-001")

    def test_invalid_sale_has_no_side_effect(self):
        with self.assertRaises(ValidationError):
            self.sale(amount=-1)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(PointEntry.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_redemption_and_replay(self):
        self.sale()
        key = uuid.uuid4()
        first = redeem(actor=self.cashier, customer=self.customer, reward=self.reward, request_id=key)
        second = redeem(actor=self.cashier, customer=self.customer, reward=self.reward, request_id=key)
        self.assertEqual(first.pk, second.pk)
        self.customer.refresh_from_db()
        self.reward.refresh_from_db()
        self.assertEqual((self.customer.points, self.reward.stock), (1, 1))
        self.assertEqual(self.customer.ledger.aggregate(total=Sum("delta"))["total"], 1)
        self.assertEqual(Redemption.objects.count(), 1)

    def test_insufficient_points_and_stock_rollback(self):
        with self.assertRaises(ValidationError):
            redeem(actor=self.cashier, customer=self.customer, reward=self.reward, request_id=uuid.uuid4())
        self.sale()
        Reward.objects.filter(pk=self.reward.pk).update(stock=0)
        with self.assertRaises(ValidationError):
            redeem(actor=self.cashier, customer=self.customer, reward=self.reward, request_id=uuid.uuid4())
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.points, 4)
        self.assertEqual(Redemption.objects.count(), 0)

    def test_campaign_consent_segment_and_publish_once(self):
        for i in range(3):
            self.sale(reference=f"STRUK-{i}")
        other = Customer.objects.create(name="Tidak bersedia", phone="628111111111", consent=False)
        campaign = Campaign.objects.create(title="Promo", body="Pesan uji", segment="loyal", created_by=self.manager)
        self.assertEqual(publish(actor=self.manager, campaign_id=campaign.pk), 1)
        self.assertEqual(publish(actor=self.manager, campaign_id=campaign.pk), 1)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertFalse(Notification.objects.filter(customer=other).exists())
        self.customer.consent = False
        self.customer.save()
        another = Campaign.objects.create(title="Baru", body="B", segment="all", created_by=self.manager)
        self.assertEqual(publish(actor=self.manager, campaign_id=another.pk), 0)

    def test_segment_boundaries(self):
        self.sale()
        Sale.objects.update(created_at=timezone.now() - timedelta(days=31))
        self.assertEqual(segment(customers(), "at_risk").count(), 1)
        self.assertEqual(segment(customers(), "loyal").count(), 0)
        self.assertEqual(segment(customers(), "new").count(), 1)

    def test_phone_normalization_and_uniqueness(self):
        form = CustomerForm({"name": "Nama lain", "phone": "0812-3456-789", "consent": False})
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)
        form = CustomerForm({"name": "Nama lain", "phone": "0812-9999-999", "consent": False})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "628129999999")

    def test_roles_and_login_required(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
        self.client.force_login(self.cashier)
        for route in ["campaigns", "campaign_create", "audit", "reward_create"]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 403, route)
        self.assertEqual(self.client.get(reverse("sales")).status_code, 200)
        self.assertEqual(self.client.get(reverse("customer_edit", args=[self.customer.pk])).status_code, 403)

    def test_all_pages_render_and_escape_customer_name(self):
        self.customer.name = '<script>alert("x")</script>'
        self.customer.save()
        self.sale()
        self.client.force_login(self.manager)
        for route in ["dashboard", "customers", "sales", "rewards", "campaigns", "audit", "sale_create", "redeem", "customer_create", "campaign_create", "reward_create", "password_change"]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 200, route)
        response = self.client.get(reverse("customer_detail", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_csrf_and_post_only_mutations(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        self.assertEqual(client.post(reverse("sale_create"), {}).status_code, 403)
        campaign = Campaign.objects.create(title="A", body="B", segment="all", created_by=self.manager)
        self.assertEqual(client.get(reverse("campaign_publish", args=[campaign.pk])).status_code, 405)
        self.assertEqual(client.post(reverse("campaign_publish", args=[campaign.pk])).status_code, 403)
        self.assertEqual(client.get(reverse("logout")).status_code, 405)

    def test_full_form_flow_and_duplicate_post(self):
        self.client.force_login(self.cashier)
        data = {"customer": self.customer.pk, "reference": "FORM-001", "amount": "50000", "channel": "web", "request_id": str(uuid.uuid4())}
        self.assertRedirects(self.client.post(reverse("sale_create"), data), reverse("sales"))
        self.assertRedirects(self.client.post(reverse("sale_create"), data), reverse("sales"))
        self.assertEqual(Sale.objects.count(), 1)
        data = {"customer": self.customer.pk, "reward": self.reward.pk, "request_id": str(uuid.uuid4())}
        self.assertRedirects(self.client.post(reverse("redeem"), data), reverse("rewards"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.points, 2)

    def test_login_throttled(self):
        for _ in range(10):
            self.assertEqual(self.client.post(reverse("login"), {"username": "missing", "password": "bad"}).status_code, 200)
        self.assertEqual(self.client.post(reverse("login"), {"username": "missing", "password": "bad"}).status_code, 429)

    def test_demo_refuses_existing_business_data(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo")
        self.assertFalse(DemoMarker.objects.exists())

    def test_edit_profile_does_not_change_points(self):
        self.sale()
        self.client.force_login(self.manager)
        self.assertRedirects(self.client.post(reverse("customer_edit", args=[self.customer.pk]), {
            "name": "Nama diperbarui", "phone": self.customer.phone, "email": "", "consent": True,
        }), reverse("customer_detail", args=[self.customer.pk]))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.points, 4)
        self.assertEqual(self.customer.name, "Nama diperbarui")

    def test_stale_reward_edit_cannot_overwrite_stock(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("reward_edit", args=[self.reward.pk]), {
            "name": "Kopi", "description": "", "cost": 3, "stock": 20, "active": True, "original_stock": 3,
        })
        self.assertContains(response, "Stok berubah")
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.stock, 2)

    def test_dashboard_periods_and_clean_interface(self):
        self.sale()
        Sale.objects.update(created_at=timezone.now() - timedelta(days=20))
        DemoMarker.objects.create()
        self.client.force_login(self.manager)
        for period, count in [("7", 0), ("14", 0), ("30", 1), ("invalid", 0)]:
            response = self.client.get(reverse("dashboard"), {"period": period})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["totals"]["transactions"], count)
            self.assertNotContains(response, "Mode demo")
            self.assertNotContains(response, "data sintetis")
            self.assertNotContains(response, "Hubungan baik, usaha tumbuh")

    def test_refine_requires_demo_database(self):
        with self.assertRaises(ValidationError):
            refine_demo()


class DemoTests(TestCase):
    def test_demo_can_be_seeded_only_once(self):
        group = Group.objects.create(name="Pengelola")
        user = User.objects.create_user("demo")
        user.groups.add(group)
        call_command("seed_demo", verbosity=0)
        before = (Customer.objects.count(), Sale.objects.count(), PointEntry.objects.count())
        call_command("seed_demo", verbosity=0)
        self.assertEqual(before, (Customer.objects.count(), Sale.objects.count(), PointEntry.objects.count()))
        self.assertEqual(Customer.objects.count(), 24)
        self.assertTrue(DemoMarker.objects.exists())
        self.assertFalse(Sale.objects.filter(reference__startswith="DEMO-").exists())
        untouched = Customer.objects.create(name="Pelanggan pengguna", phone="628112222333", email="owner@example.org")
        before = (Sale.objects.count(), PointEntry.objects.count())
        refine_demo()
        refine_demo()
        self.assertEqual(before, (Sale.objects.count(), PointEntry.objects.count()))
        untouched.refresh_from_db()
        self.assertEqual(untouched.email, "owner@example.org")
        for person in Customer.objects.all():
            self.assertEqual(person.points, person.ledger.aggregate(total=Sum("delta"))["total"] or 0)
            first = person.sales.order_by("created_at").first()
            if first:
                self.assertLessEqual(person.created_at, first.created_at)


@skipUnless(connection.vendor == "postgresql", "Pengujian penguncian baris membutuhkan PostgreSQL.")
class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user("parallel")
        self.customer = Customer.objects.create(name="Concurrent", phone="628123000001")
        record_sale(actor=self.user, customer=self.customer, reference="PAR-001", amount=50000, channel="store", request_id=uuid.uuid4())
        self.reward = Reward.objects.create(name="Satu stok", cost=5, stock=1)

    def test_parallel_redemptions_cannot_overspend(self):
        def attempt(_):
            close_old_connections()
            try:
                redeem(actor=self.user, customer=self.customer, reward=self.reward, request_id=uuid.uuid4())
                return "ok"
            except ValidationError:
                return "denied"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertCountEqual(results, ["ok", "denied"])
        self.customer.refresh_from_db()
        self.reward.refresh_from_db()
        self.assertEqual((self.customer.points, self.reward.stock), (0, 0))
        self.assertEqual(Redemption.objects.count(), 1)

    def test_parallel_sales_same_key_credited_once(self):
        key = uuid.uuid4()
        def attempt(_):
            close_old_connections()
            try:
                return record_sale(actor=self.user, customer=self.customer, reference="PAR-002", amount=30000,
                                   channel="store", request_id=key).pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(results[0], results[1])
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.points, 8)
