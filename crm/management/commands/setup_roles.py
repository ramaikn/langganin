from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password


class Command(BaseCommand):
    help = "Buat grup dan akun pengelola/kasir. Kata sandi dibaca dari environment."

    def add_arguments(self, parser):
        parser.add_argument("--manager", default="pengelola")
        parser.add_argument("--cashier", default="kasir")

    def handle(self, *args, **options):
        import os

        for group_name, field, env in [("Pengelola", "manager", "LANGGANIN_MANAGER_PASSWORD"), ("Kasir", "cashier", "LANGGANIN_CASHIER_PASSWORD")]:
            group, _ = Group.objects.get_or_create(name=group_name)
            username = options[field]
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"Akun {username} sudah ada, kata sandi tidak diubah.")
                continue
            password = os.getenv(env)
            if not password:
                raise CommandError(f"Isi {env} untuk akun baru.")
            validate_password(password, User(username=username))
            user = User.objects.create_user(username=username, password=password)
            user.groups.add(group)
            self.stdout.write(self.style.SUCCESS(f"Akun {username} dibuat sebagai {group_name}."))
