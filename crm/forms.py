import re

from django import forms

from .models import Campaign, Customer, Reward, Sale


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "consent"]

    def clean_phone(self):
        phone = re.sub(r"[\s()+-]", "", self.cleaned_data["phone"])
        if phone.startswith("0"):
            phone = "62" + phone[1:]
        return phone


class SaleForm(forms.Form):
    customer = forms.ModelChoiceField(label="Pelanggan", queryset=Customer.objects.all())
    reference = forms.CharField(label="Nomor struk", max_length=64)
    amount = forms.IntegerField(label="Nilai transaksi (Rp)", min_value=1000, max_value=100000000)
    channel = forms.ChoiceField(label="Kanal", choices=Sale.CHANNELS)
    request_id = forms.UUIDField(widget=forms.HiddenInput)


class RedeemForm(forms.Form):
    customer = forms.ModelChoiceField(label="Pelanggan", queryset=Customer.objects.all())
    reward = forms.ModelChoiceField(label="Hadiah", queryset=Reward.objects.filter(active=True, stock__gt=0))
    request_id = forms.UUIDField(widget=forms.HiddenInput)


class RewardForm(forms.ModelForm):
    original_stock = forms.IntegerField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["original_stock"].required = True
            self.initial["original_stock"] = self.instance.stock

    class Meta:
        model = Reward
        fields = ["name", "description", "cost", "stock", "active"]


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["title", "body", "segment"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}
