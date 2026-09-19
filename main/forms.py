from django import forms

from .models import OrderRequest, OrderItemOption


COLOR_CHOICES = [
    ("", "- Select a color -"),
    ("Natural / Unbleached", "Natural / Unbleached"),
    ("Brown", "Brown"),
    ("Green", "Green"),
    ("Pink", "Pink"),
    ("Other", "Other (specify)"),
]


class OrderRequestForm(forms.ModelForm):
    color = forms.ChoiceField(
        choices=COLOR_CHOICES,
        required=False,
        widget=forms.Select(attrs={"id": "id_color"}),
    )
    color_other = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Dark chocolate brown",
            "id": "id_color_other",
        }),
    )

    class Meta:
        model = OrderRequest
        fields = [
            "item_description", "color", "length", "gsm", "quantity",
            "company_name", "contact_person", "phone", "email",
            "delivery_location", "preferred_delivery_date", "lpo_file", "notes",
        ]
        widgets = {
            "length": forms.NumberInput(attrs={"step": "0.01", "placeholder": "e.g. 1500", "id": "id_length"}),
            "gsm": forms.NumberInput(attrs={"placeholder": "e.g. 80", "id": "id_gsm"}),
            "quantity": forms.NumberInput(attrs={"placeholder": "e.g. 500", "id": "id_quantity"}),
            "company_name": forms.TextInput(attrs={"placeholder": "e.g. Kenturian Traders Ltd"}),
            "contact_person": forms.TextInput(attrs={"placeholder": "e.g. Jane Wanjiru"}),
            "phone": forms.TextInput(attrs={"placeholder": "07XX XXX XXX"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "delivery_location": forms.TextInput(attrs={"placeholder": "e.g. Thika, Kiambu County"}),
            "preferred_delivery_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4, "placeholder": "Anything else we should know?"}),
        }
        labels = {
            "length": "Length (mm)",
            "gsm": "GSM (paper weight)",
            "quantity": "Quantity (kg)",
            "lpo_file": "Attach LPO (optional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        item_choices = [
            (o.name, o.name)
            for o in OrderItemOption.objects.filter(is_active=True)
        ]
        choices = (
            [("", "- Select an option -")]
            + item_choices
            + [("Custom / Other", "Custom / Other (describe in notes)")]
        )
        self.fields["item_description"] = forms.ChoiceField(
            choices=choices,
            label="Item Description",
            widget=forms.Select(attrs={"id": "id_item_description"}),
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("color") == "Other":
            other = cleaned.get("color_other", "").strip()
            if other:
                cleaned["color"] = other
        return cleaned


class ContactForm(forms.Form):
    name = forms.CharField(max_length=120, widget=forms.TextInput(
        attrs={'placeholder': 'Your name'}))
    email = forms.EmailField(widget=forms.EmailInput(
        attrs={'placeholder': 'you@example.com'}))
    subject = forms.CharField(max_length=255, widget=forms.TextInput(
        attrs={'placeholder': 'Subject'}))
    message = forms.CharField(widget=forms.Textarea(
        attrs={'rows': 6, 'placeholder': 'Your message'}))


class JobApplicationForm(forms.Form):
    name = forms.CharField(max_length=120, widget=forms.TextInput(
        attrs={'placeholder': 'Your name'}))
    email = forms.EmailField(widget=forms.EmailInput(
        attrs={'placeholder': 'you@example.com'}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(
        attrs={'placeholder': 'Phone number (optional)'}))
    message = forms.CharField(widget=forms.Textarea(
        attrs={'rows': 6, 'placeholder': "Tell us why you're a good fit"}))
    cv = forms.FileField(label='Upload CV (PDF or Word)', widget=forms.ClearableFileInput(
        attrs={'accept': '.pdf,.doc,.docx'}))
