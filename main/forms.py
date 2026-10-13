import json
import re
from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import OrderRequest, OrderItemOption
from .validators import validate_upload


COLOR_CHOICES = [
    ("", "- Select a colour -"),
    ("Brown", "Brown"),
    ("Green", "Green"),
    ("Pink", "Pink"),
    ("White", "White"),
    ("Other", "Other (specify)"),
]

# (word found in the item name, colour that item is always made in)
FIXED_COLORS = [
    ("test liner", "Brown"),
    ("duplex", "Brown"),
    ("tissue", "White"),
]

# (word found in the item name, colours that item is never made in)
BLOCKED_COLORS = [
    ("mg cover", ["White"]),
]

# field: (smallest, largest, unit, name used in messages)
LIMITS = {
    "length": (100, 3000, "mm", "Length"),
    "gsm": (10, 400, "", "GSM"),
    "quantity": (1, 100000, "kg", "Quantity"),
}

NOTES_MAX = 500         # characters allowed in Additional Notes
MAX_DELIVERY_DAYS = 60    # furthest ahead a client can ask for delivery

INVALID_MESSAGES = {
    "length": "Enter the length as a number in millimetres, e.g. 1500.",
    "gsm": "Enter the GSM as a whole number, e.g. 80.",
    "quantity": "Enter the quantity in kilograms as a whole number, e.g. 500.",
    "email": "Enter a valid email address, e.g. name@company.co.ke.",
    "preferred_delivery_date": "Enter a valid date.",
}


def range_message(name):
    low, high, unit, title = LIMITS[name]
    unit = f" {unit}" if unit else ""
    return (
        f"{title} must be between {low:,}{unit} and {high:,}{unit}. "
        "For anything outside this range, please contact our sales team."
    )


class OrderRequestForm(forms.ModelForm):
    color = forms.ChoiceField(
        label="Colour",
        choices=COLOR_CHOICES,
        required=False,
        widget=forms.Select(attrs={"id": "id_color"}),
    )
    color_other = forms.CharField(
        label="Other colour",
        max_length=100,
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
            "contact_person": forms.TextInput(attrs={"placeholder": "e.g. Jane Doe"}),
            "phone": forms.TextInput(attrs={
                "placeholder": "07XX XXX XXX",
                "type": "tel",
                "inputmode": "tel",
                "autocomplete": "tel",
                "maxlength": "25",
            }),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "delivery_location": forms.TextInput(attrs={"placeholder": "e.g. Thika, Kiambu County"}),
            "preferred_delivery_date": forms.DateInput(attrs={"type": "date"}),
            "lpo_file": forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png,.doc,.docx"}),
            "notes": forms.Textarea(attrs={
                "rows": 4,
                "maxlength": str(NOTES_MAX),
                "placeholder": "Anything else we should know?",
            }),
        }
        labels = {
            "length": "Length (mm)",
            "gsm": "GSM (paper weight)",
            "quantity": "Quantity (kg)",
            "lpo_file": "Attach LPO (optional: PDF, JPG, PNG or Word, max 5 MB)",
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
            widget=forms.Select(attrs={
                "id": "id_item_description",
                "data-color-rules": json.dumps(FIXED_COLORS),
                "data-blocked-colors": json.dumps(BLOCKED_COLORS),
            }),
            error_messages={
                "required": "Please select the item you want to order.",
                "invalid_choice": "Please pick an item from the list.",
            },
        )

        # Clear, specific messages instead of Django's generic ones
        for name, field in self.fields.items():
            if name != "item_description":
                label = field.label or name.replace("_", " ").capitalize()
                field.error_messages["required"] = f"Please fill in '{label}'."
            if name in INVALID_MESSAGES:
                field.error_messages["invalid"] = INVALID_MESSAGES[name]

        # Size limits: browser hint + clear message if the number is out of range
        for name, (low, high, unit, title) in LIMITS.items():
            field = self.fields[name]
            field.widget.attrs["min"] = low
            field.widget.attrs["max"] = high
            field.widget.attrs["data-range-message"] = range_message(name)
            for code in ("min_value", "max_value", "max_digits", "max_whole_digits"):
                field.error_messages[code] = range_message(name)
        self.fields["length"].error_messages["max_decimal_places"] = (
            "Enter the length with at most 2 decimal places, e.g. 1500.50."
        )

        # Delivery date: today up to MAX_DELIVERY_DAYS ahead
        today = timezone.localdate()
        date_attrs = self.fields["preferred_delivery_date"].widget.attrs
        date_attrs["min"] = today.isoformat()
        date_attrs["max"] = (
            today + timedelta(days=MAX_DELIVERY_DAYS)).isoformat()

        # Colour is required (locked colours are filled in by clean())
        self.fields["color"].widget.attrs["required"] = "required"

    # ---- field checks ----
    def _check_range(self, name):
        value = self.cleaned_data.get(name)
        if value is not None:
            low, high = LIMITS[name][0], LIMITS[name][1]
            if not (low <= value <= high):
                raise forms.ValidationError(range_message(name))
        return value

    def clean_length(self):
        return self._check_range("length")

    def clean_gsm(self):
        return self._check_range("gsm")

    def clean_quantity(self):
        return self._check_range("quantity")

    def clean_phone(self):
        raw = (self.cleaned_data.get("phone") or "").strip()
        if not raw:
            return raw
        if not re.fullmatch(r"\+?[0-9\s\-().]+", raw):
            raise forms.ValidationError(
                "The phone number can only contain digits, spaces, dashes and a leading +. "
                "Please remove any letters or symbols."
            )
        digits = re.sub(r"\D", "", raw)

        # International number that is not Kenyan
        if raw.startswith("+") and not digits.startswith("254"):
            if not 8 <= len(digits) <= 15:
                raise forms.ValidationError(
                    "International numbers need 8 to 15 digits including the country code, "
                    "e.g. +256 700 123 456."
                )
            return "+" + digits

        # Kenyan number written with the country code
        if digits.startswith("254"):
            if len(digits) != 12:
                raise forms.ValidationError(
                    "A Kenyan number starting with +254 needs 9 digits after the code, "
                    "e.g. +254 712 345 678."
                )
            return "+" + digits

        # Kenyan number written with a leading 0
        if digits.startswith("0"):
            if len(digits) != 10:
                raise forms.ValidationError(
                    "A Kenyan number starting with 0 must have 10 digits, e.g. 0712 345 678."
                )
            return "+254" + digits[1:]

        raise forms.ValidationError(
            "Start the number with 0 (e.g. 0712 345 678) or with the country code "
            "(e.g. +254 712 345 678)."
        )

    def clean_notes(self):
        # Browsers count a line break as 1 character but send 2, so normalise first
        text = (self.cleaned_data.get("notes")
                or "").replace("\r\n", "\n").strip()
        if len(text) > NOTES_MAX:
            raise forms.ValidationError(
                f"Additional notes are {len(text):,} characters long. "
                f"Please keep them to {NOTES_MAX:,} characters or fewer."
            )
        return text

    def clean_preferred_delivery_date(self):
        value = self.cleaned_data.get("preferred_delivery_date")
        if value:
            today = timezone.localdate()
            latest = today + timedelta(days=MAX_DELIVERY_DAYS)
            if value < today:
                raise forms.ValidationError(
                    "The preferred delivery date can't be in the past. Please pick today or a later date."
                )
            if value > latest:
                raise forms.ValidationError(
                    f"The preferred delivery date can't be more than {MAX_DELIVERY_DAYS} days ahead "
                    f"(latest: {latest:%d %b %Y}). For a later delivery, pick the latest date "
                    "and mention the timing in the notes."
                )
        return value

    def clean_lpo_file(self):
        uploaded = self.cleaned_data.get("lpo_file")
        validate_upload(uploaded)
        return uploaded

    # ---- cross-field checks ----
    def clean(self):
        cleaned = super().clean()
        item_name = cleaned.get("item_description") or ""
        item = item_name.lower()
        color = cleaned.get("color") or ""

        # Items that are always one colour
        fixed = next((c for key, c in FIXED_COLORS if key in item), None)
        if fixed:
            if color and color != fixed:
                self.add_error(
                    "color",
                    f"{item_name} is only supplied in {fixed}. Please leave the colour as {fixed}."
                )
            else:
                cleaned["color"] = fixed
            return cleaned

        # Everything else needs a colour
        if item_name and not color:
            self.add_error("color", "Please choose a colour for your order.")
            return cleaned

        error_field = "color"
        if color == "Other":
            other = (cleaned.get("color_other") or "").strip()
            if not other:
                self.add_error(
                    "color_other", "Please type the colour you need, or choose one from the list.")
                return cleaned
            cleaned["color"] = other
            color = other
            error_field = "color_other"

        # Colours an item is never made in (e.g. MG Cover is never white)
        blocked = [c for key,
                   colours in BLOCKED_COLORS if key in item for c in colours]
        hit = next((b for b in blocked if b.lower() in color.lower()), None)
        if hit:
            self.add_error(
                error_field, f"{item_name} is not available in {hit}. Please choose another colour.")
        return cleaned

    # ---- highlight the invalid fields ----
    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                css = self.fields[name].widget.attrs.get("class", "")
                self.fields[name].widget.attrs["class"] = (
                    css + " is-invalid").strip()


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
