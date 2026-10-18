import hashlib

from django.core.cache import cache
from django.http import HttpResponse


class LoginThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path != "/masuk/" or request.method != "POST":
            return self.get_response(request)
        # Tidak mempercayai X-Forwarded-For dari klien.
        address = request.META.get("REMOTE_ADDR", "unknown")
        account = request.POST.get("username", "").strip().lower()
        keys = ["login:" + hashlib.sha256(v.encode()).hexdigest() for v in (address, "account:" + account)]
        if any(cache.get(key, 0) >= 10 for key in keys):
            response = HttpResponse("Terlalu banyak percobaan. Tunggu 10 menit sebelum mencoba lagi.", status=429)
            response["Retry-After"] = "600"
            return response
        # Hitung sebelum autentikasi agar percobaan paralel ikut dibatasi.
        for key in keys:
            if not cache.add(key, 1, 600):
                cache.incr(key)
        response = self.get_response(request)
        if response.status_code == 302 and request.user.is_authenticated:
            cache.delete(keys[1])
        return response
