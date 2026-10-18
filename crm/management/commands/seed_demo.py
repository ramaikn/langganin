import random
import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from crm.models import Campaign, Customer, DemoMarker, PointEntry, Reward, Sale
from crm.services import publish, record_sale, redeem
from crm.demo import refine_demo


class Command(BaseCommand):
    help = "Isi data sintetis hanya pada database usaha yang masih kosong."

    @transaction.atomic
    def handle(self, *args, **options):
        if DemoMarker.objects.exists():
            self.stdout.write("Data demo sudah tersedia, tidak ditambahkan ulang.")
            return
        if Customer.objects.exists() or Sale.objects.exists() or Reward.objects.exists() or Campaign.objects.exists():
            raise CommandError("Database sudah berisi data usaha. Demo hanya boleh di database kosong.")
        actor = User.objects.filter(groups__name="Pengelola").first()
        if not actor:
            raise CommandError("Jalankan setup_roles dahulu.")
        rng = random.Random(42)
        now = timezone.now()
        names = ["Nadia Putri", "Arif Pratama", "Dewi Lestari", "Rizky Aditya", "Siti Rahma", "Bima Saputra",
                 "Ayu Wulandari", "Dimas Maulana", "Rani Permata", "Fajar Hidayat", "Intan Maharani", "Raka Wijaya",
                 "Maya Safitri", "Andi Kurniawan", "Putri Amelia", "Reza Firmansyah", "Citra Larasati", "Yoga Prakoso",
                 "Nisa Azzahra", "Bayu Ramadhan", "Tara Anggraini", "Ilham Akbar", "Laras Puspita", "Satria Nugraha"]
        people = []
        number = 0
        for i, name in enumerate(names):
            # Nomor sengaja sintetis; jangan dipakai menghubungi siapa pun.
            customer = Customer.objects.create(name=name, phone=f"62000000{i:04d}", email=f"member{i+1}@example.invalid", consent=i % 5 != 0)
            people.append(customer)
            joined = now - timedelta(days=rng.randint(72, 95) if i < 18 else 7)
            Customer.objects.filter(pk=customer.pk).update(created_at=joined)
            count = rng.randint(4, 8) if i < 12 else rng.randint(1, 2)
            for visit in range(count):
                number += 1
                sale = record_sale(actor=actor, customer=customer, reference=f"DEMO-{number:04d}",
                                   amount=rng.choice([35000, 48000, 65000, 95000, 125000, 180000, 250000]),
                                   channel=rng.choices(["store", "web", "app"], weights=[7, 2, 1])[0], request_id=uuid.uuid4())
                age = rng.randint(35, 60) if 12 <= i < 18 else rng.randint(0, 4 if i >= 18 else 13)
                occurred = timezone.localtime(now - timedelta(days=age)).replace(
                    hour=rng.randint(8, 19), minute=rng.randint(0, 59), second=0, microsecond=0)
                if occurred > now:
                    occurred -= timedelta(days=1)
                Sale.objects.filter(pk=sale.pk).update(created_at=occurred)
                PointEntry.objects.filter(sale=sale).update(created_at=occurred)
        coffee = Reward.objects.create(name="Kopi pilihanmu", description="Satu kopi reguler untuk menemani hari.", cost=15, stock=40)
        Reward.objects.create(name="Potongan Rp25.000", description="Apresiasi untuk pembelian berikutnya.", cost=30, stock=25)
        Reward.objects.create(name="Tumbler Langganin", description="Bawa kembali, isi cerita yang baru.", cost=80, stock=12)
        redeem(actor=actor, customer=people[1], reward=coffee, request_id=uuid.uuid4())
        campaign = Campaign.objects.create(title="Senang Anda kembali", body="Terima kasih sudah menjadi bagian dari perjalanan kami. Cek saldo poin dan pilih hadiah favorit Anda saat berkunjung.", segment="loyal", created_by=actor)
        publish(actor=actor, campaign_id=campaign.pk)
        Campaign.objects.create(title="Sudah lama tidak berjumpa", body="Ada cerita baru di gerai kami. Mampir kembali dan temukan pilihan favorit Anda.", segment="at_risk", created_by=actor)
        DemoMarker.objects.create()
        refine_demo()
        self.stdout.write(self.style.SUCCESS(f"Demo sintetis dibuat: {len(people)} pelanggan, {number} transaksi. Tidak ada pesan eksternal yang dikirim."))
