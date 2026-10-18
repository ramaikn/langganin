from django.contrib.auth import views as auth
from django.urls import include, path

urlpatterns = [
    path("masuk/", auth.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("keluar/", auth.LogoutView.as_view(), name="logout"),
    path("kata-sandi/", auth.PasswordChangeView.as_view(template_name="form.html", success_url="/"), name="password_change"),
    path("", include("crm.urls")),
]
