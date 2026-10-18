from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from crm.demo import refine_demo


class Command(BaseCommand):
    help = "Rapikan referensi struk dan kronologi contoh tanpa menghapus data pengguna."

    def handle(self, *args, **options):
        try:
            count = refine_demo()
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        self.stdout.write(self.style.SUCCESS(f"{count} referensi transaksi contoh dirapikan."))
