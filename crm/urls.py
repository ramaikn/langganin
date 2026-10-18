from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("pelanggan/", views.customer_list, name="customers"),
    path("pelanggan/baru/", views.customer_create, name="customer_create"),
    path("pelanggan/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("pelanggan/<int:pk>/ubah/", views.customer_edit, name="customer_edit"),
    path("transaksi/", views.sales, name="sales"),
    path("transaksi/baru/", views.sale_create, name="sale_create"),
    path("hadiah/", views.rewards, name="rewards"),
    path("hadiah/baru/", views.reward_edit, name="reward_create"),
    path("hadiah/<int:pk>/ubah/", views.reward_edit, name="reward_edit"),
    path("penukaran/", views.redeem_create, name="redeem"),
    path("kampanye/", views.campaigns, name="campaigns"),
    path("kampanye/baru/", views.campaign_create, name="campaign_create"),
    path("kampanye/<int:pk>/terbitkan/", views.campaign_publish, name="campaign_publish"),
    path("aktivitas/", views.audit_log, name="audit"),
    path("health/", views.health, name="health"),
]
