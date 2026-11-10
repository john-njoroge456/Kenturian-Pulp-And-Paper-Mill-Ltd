import json
import re
import uuid
from datetime import timedelta
import os


from django import forms
from django.utils import timezone


from .models import OrderRequest, OrderItem, OrderItemOption
from .validators import clean_upload_name, normalize_phone, validate_upload
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, BaseInlineFormSet


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

# Colours from our own lists; anything else was typed in under "Other"
STANDARD_COLORS = (
    {value for value, _ in COLOR_CHOICES if value and value != "Other"}
    | {color for _, color in FIXED_COLORS}
)

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
MAX_ITEMS = 10
TEXT_MIN = 2    # characters for company, contact person and delivery location
INVALID_MESSAGES = {
    "length": "Enter the length as a number in millimetres, e.g. 1500.",
    "gsm": "Enter the GSM as a whole number, e.g. 80.",
    "quantity": "Enter the quantity in kilograms as a whole number, e.g. 500.",
    "email": "Enter a valid email address, e.g. name@company.co.ke.",
    "preferred_delivery_date": "Enter a valid date.",
}
CONTACT_MESSAGE_MIN = 10
CONTACT_MESSAGE_MAX = 500
MAX_LINKS = 2
CV_MAX_MB = 5
LPO_MAX_MB = 10
# First bytes of real PDF / DOCX / DOC files, so a renamed .exe can't pass as a CV
CV_SIGNATURES = {
    ".pdf": (b"%PDF",),
    ".docx": (b"PK\x03\x04",),
    ".doc": (b"\xd0\xcf\x11\xe0",),
}
NAME_RE = re.compile(r"^[^\W\d_][^\W\d_ .'\-]*(?:[ .'\-]+[^\W\d_]+)*\.?$")
TOKEN_RE = re.compile(r"[0-9a-f]{32}")


def range_message(name):
    low, high, unit, title = LIMITS[name]
    unit = f" {unit}" if unit else ""
    return (
        f"{title} must be between {low:,}{unit} and {high:,}{unit}. "
        "For anything outside this range, please contact our sales team."
    )


def clean_text(value, label):
    """Collapse spaces, then require TEXT_MIN characters and at least one letter."""
    text = " ".join((value or "").split())
    if not text:
        return text
    if len(text) < TEXT_MIN:
        raise forms.ValidationError(
            f"{label} must be at least {TEXT_MIN} characters long.")
    if not re.search(r"[^\W\d_]", text):
        raise forms.ValidationError(
            f"{label} must include at least one letter, not only numbers or symbols.")
    return text


class HoneypotInput(forms.TextInput):
    """Spam-trap input that never writes the submitted value back into the page."""

    def format_value(self, value):
        return None


class OrderRequestForm(forms.ModelForm):
    """Shared order details: who is ordering, delivery, LPO and notes."""
    # Hidden trap for spam bots: real visitors never see or fill this in (FX-35).
    # The name matches no autofill field, so browsers won't fill it for a real client
    kp_hp_check = forms.CharField(
        required=False,
        widget=HoneypotInput(
            attrs={"tabindex": "-1", "autocomplete": "off"}),
    )
    # autocomplete=off stops the browser refilling an old token into a fresh form
    submission_token = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"autocomplete": "off"}),
    )

    class Meta:
        model = OrderRequest
        fields = [
            "company_name", "contact_person", "phone", "email",
            "delivery_location", "preferred_delivery_date", "lpo_file", "notes",
        ]
        widgets = {
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
            "lpo_file": "Attach LPO (optional: PDF, JPG, PNG or Word, max 10 MB)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["submission_token"].initial = uuid.uuid4().hex

        for name, field in self.fields.items():
            label = field.label or name.replace("_", " ").capitalize()
            field.error_messages["required"] = f"Please fill in '{label}'."
            if name in INVALID_MESSAGES:
                field.error_messages["invalid"] = INVALID_MESSAGES[name]

        today = timezone.localdate()
        date_attrs = self.fields["preferred_delivery_date"].widget.attrs
        date_attrs["min"] = today.isoformat()
        date_attrs["max"] = (
            today + timedelta(days=MAX_DELIVERY_DAYS)).isoformat()

    def clean_submission_token(self):
        # A missing or malformed token just skips the duplicate check
        token = self.cleaned_data.get("submission_token") or ""
        return token if TOKEN_RE.fullmatch(token) else None

    def clean_kp_hp_check(self):
        if self.cleaned_data.get("kp_hp_check"):
            raise forms.ValidationError("This order could not be sent.")
        return ""

    def clean_company_name(self):
        return clean_text(self.cleaned_data.get("company_name"), "Company name")

    def clean_contact_person(self):
        return clean_text(self.cleaned_data.get("contact_person"), "Contact person")

    def clean_delivery_location(self):
        return clean_text(self.cleaned_data.get("delivery_location"), "Delivery location")

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))

    def clean_notes(self):
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
        validate_upload(uploaded, max_mb=LPO_MAX_MB)
        if uploaded:
            uploaded.name = clean_upload_name(uploaded.name)
        return uploaded

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                css = self.fields[name].widget.attrs.get("class", "")
                self.fields[name].widget.attrs["class"] = (
                    css + " is-invalid").strip()


class OrderItemForm(forms.ModelForm):
    """One item line: item, colour, length, GSM and quantity."""
    color = forms.ChoiceField(
        label="Colour",
        choices=COLOR_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "item-color"}),
    )
    color_other = forms.CharField(
        label="Other colour",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Dark chocolate brown",
            "class": "item-color-other",
        }),
    )

    class Meta:
        model = OrderItem
        fields = ["item_description", "color", "length", "gsm", "quantity"]
        widgets = {
            "length": forms.NumberInput(attrs={"step": "0.01", "placeholder": "e.g. 1500", "class": "item-length"}),
            "gsm": forms.NumberInput(attrs={"placeholder": "e.g. 80", "class": "item-gsm"}),
            "quantity": forms.NumberInput(attrs={"placeholder": "e.g. 500", "class": "item-quantity"}),
        }
        labels = {
            "length": "Length (mm)",
            "gsm": "GSM (paper weight)",
            "quantity": "Quantity (kg)",
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
                "class": "item-description",
                "data-color-rules": json.dumps(FIXED_COLORS),
                "data-blocked-colors": json.dumps(BLOCKED_COLORS),
            }),
            error_messages={
                "required": "Please select the item you want to order.",
                "invalid_choice": "Please pick an item from the list.",
            },
        )

        for name, field in self.fields.items():
            if name != "item_description":
                label = field.label or name.replace("_", " ").capitalize()
                field.error_messages["required"] = f"Please fill in '{label}'."
            if name in INVALID_MESSAGES:
                field.error_messages["invalid"] = INVALID_MESSAGES[name]

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

        self.fields["color"].widget.attrs["required"] = "required"

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

    def clean(self):
        cleaned = super().clean()
        item_name = cleaned.get("item_description") or ""
        item = item_name.lower()
        color = cleaned.get("color") or ""

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

        if item_name and not color:
            self.add_error("color", "Please choose a colour for this item.")
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

        blocked = [c for key,
                   colours in BLOCKED_COLORS if key in item for c in colours]
        hit = next((b for b in blocked if b.lower() in color.lower()), None)
        if hit:
            self.add_error(
                error_field, f"{item_name} is not available in {hit}. Please choose another colour.")
        return cleaned

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                css = self.fields[name].widget.attrs.get("class", "")
                self.fields[name].widget.attrs["class"] = (
                    css + " is-invalid").strip()


class BaseOrderItemFormSet(BaseInlineFormSet):
    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        # The first item must always be filled in, so let the browser
        # check it even without JavaScript (Django turns this off for formsets).
        if i < self.min_num:
            form.use_required_attribute = True
        return form

    def clean(self):
        super().clean()
        filled = [f for f in self.forms if f.has_changed()]
        if len(filled) > MAX_ITEMS:
            raise forms.ValidationError(
                f"You can order up to {MAX_ITEMS} items per order. You added {len(filled)}. "
                f"Please remove {len(filled) - MAX_ITEMS}, or place a second order for the rest."
            )
        seen = {}
        for number, form in enumerate(self.forms, start=1):
            if not form.has_changed() or form.errors:
                continue
            cd = form.cleaned_data
            key = (
                (cd.get("item_description") or "").strip().lower(),
                (cd.get("color") or "").strip().lower(),
                cd.get("length"),
                cd.get("gsm"),
            )
            if key in seen:
                first = seen[key]
                form.add_error(
                    None,
                    f"This item is the same as item {first} ({cd['item_description']}, "
                    f"{cd.get('color') or 'no colour'}, {float(cd['length']):g} mm, {cd['gsm']} GSM). "
                    f"Please remove it and add its quantity to item {first} instead, "
                    f"or change the specifications."
                )
            else:
                seen[key] = number


OrderItemFormSet = inlineformset_factory(
    OrderRequest, OrderItem,
    form=OrderItemForm,
    formset=BaseOrderItemFormSet,
    extra=0,
    min_num=1,
    max_num=MAX_ITEMS,
    absolute_max=MAX_ITEMS + 5,
    can_delete=False,
)


OWN_DOMAIN = "kenturian.co.ke"
EMAIL_IN_TEXT_RE = re.compile(r"\S+@\S+")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
# Bare domains such as indexdomain.live (FX-37). The last part must be 2-24
# lowercase letters, so "e.g.", "i.e.", "2.5" and a missed space ("end.Next")
# are not links. The lookbehind stops a match starting mid-word.
BARE_DOMAIN_RE = re.compile(
    r"(?<![\w.@-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+([a-z]{2,24})(?![\w-])")
# File names look like domains ("LPO.pdf"), so these endings never count
FILE_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png", "txt", "csv"}


def _is_own_domain(host):
    return host == OWN_DOMAIN or host.endswith("." + OWN_DOMAIN)


def _url_host(url):
    url = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    return re.split(r"[/?#:]", url, maxsplit=1)[0].lower()


def count_links(text):
    """Links in a message: http(s):// and www. URLs plus bare domains,
    leaving out email addresses, file names and our own domain."""
    text = EMAIL_IN_TEXT_RE.sub(" ", text or "")
    hosts = [_url_host(url) for url in URL_RE.findall(text)]
    text = URL_RE.sub(" ", text)
    hosts += [m.group(0).lower() for m in BARE_DOMAIN_RE.finditer(text)
              if m.group(1) not in FILE_EXTENSIONS]
    return sum(1 for host in hosts if not _is_own_domain(host))


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        error_messages={"required": "Please enter your name."},
        widget=forms.TextInput(
            attrs={"placeholder": "Your name", "autocomplete": "name"}),
    )
    email = forms.EmailField(
        max_length=254,
        error_messages={
            "required": "Please enter your email address.",
            "invalid": "Enter a valid email address, e.g. name@company.co.ke.",
            "max_length": "Please enter an email address of 254 characters or fewer.",
        },
        widget=forms.EmailInput(
            attrs={"placeholder": "you@example.com", "autocomplete": "email"}),
    )
    subject = forms.CharField(
        max_length=255,
        error_messages={"required": "Please enter a subject."},
        widget=forms.TextInput(attrs={"placeholder": "Subject"}),
    )
    message = forms.CharField(
        error_messages={"required": "Please write your message."},
        widget=forms.Textarea(attrs={
            "rows": 6,
            "placeholder": "Your message",
            "maxlength": str(CONTACT_MESSAGE_MAX),
        }),
    )
    # Hidden trap for spam bots: real visitors never see or fill this in
    fax_number = forms.CharField(
        required=False,
        widget=HoneypotInput(
            attrs={"tabindex": "-1", "autocomplete": "off"}),
    )
    # autocomplete=off stops the browser refilling an old token into a fresh form
    submission_token = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"autocomplete": "off"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["submission_token"].initial = uuid.uuid4().hex

    def clean_submission_token(self):
        # A missing or malformed token just skips the duplicate check
        token = self.cleaned_data.get("submission_token") or ""
        return token if TOKEN_RE.fullmatch(token) else None

    def clean_name(self):
        name = self.cleaned_data["name"]
        if re.search(r"[\d_]", name) or re.search(r"[^\w\s.'’-]", name):
            raise forms.ValidationError(
                "Please enter your name using letters only, with no numbers or symbols."
            )
        if len(re.findall(r"[^\W\d_]", name)) < 2:
            raise forms.ValidationError("Please enter your full name.")
        return name

    def clean_email(self):
        return self.cleaned_data["email"].lower()

    def clean_subject(self):
        subject = self.cleaned_data["subject"]
        if len(subject) < 3:
            raise forms.ValidationError(
                "Please enter a subject of at least 3 characters.")
        return subject

    def clean_message(self):
        # Browsers count a line break as 1 character but send 2, so normalise first
        text = self.cleaned_data["message"].replace("\r\n", "\n").strip()
        if len(text) < CONTACT_MESSAGE_MIN:
            raise forms.ValidationError(
                f"Your message is too short. Please write at least {CONTACT_MESSAGE_MIN} "
                "characters so we can help you properly."
            )
        if len(text) > CONTACT_MESSAGE_MAX:
            raise forms.ValidationError(
                f"Your message is {len(text):,} characters long. "
                f"Please keep it to {CONTACT_MESSAGE_MAX:,} characters or fewer."
            )
        if count_links(text) > MAX_LINKS:
            raise forms.ValidationError(
                f"Please remove some links. A message can contain at most {MAX_LINKS} links."
            )
        return text

    def clean_fax_number(self):
        if self.cleaned_data.get("fax_number"):
            raise forms.ValidationError("This message could not be sent.")
        return ""

    # ---- highlight the invalid fields ----
    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                css = self.fields[name].widget.attrs.get("class", "")
                self.fields[name].widget.attrs["class"] = (
                    css + " is-invalid").strip()


class JobApplicationForm(forms.Form):
    name = forms.CharField(
        min_length=2, max_length=120,
        widget=forms.TextInput(
            attrs={"class": "form-control", "autocomplete": "name"}),
        error_messages={
            "required": "Please enter your full name.",
            "min_length": "Your name must be at least 2 characters.",
            "max_length": "Your name must be 120 characters or fewer.",
        },
    )
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "autocomplete": "email"}),
        error_messages={
            "required": "Please enter your email address.",
            "invalid": "Please enter a valid email address, e.g. name@example.com.",
        },
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "tel",
                                      "placeholder": "e.g. 0712 345 678"}),
        error_messages={
            "required": "Please enter a phone number we can reach you on.",
            "max_length": "That phone number is too long. Please enter it as "
                          "0712 345 678 or +254 712 345 678.",
        },
    )
    message = forms.CharField(
        min_length=20, max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        error_messages={
            "required": "Please tell us a little about yourself.",
            "min_length": "Please write at least 20 characters so we can get to know you.",
            "max_length": "Please keep your message to 2,000 characters or fewer.",
        },
    )
    cv = forms.FileField(
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".pdf,.doc,.docx"}),
        error_messages={
            "required": "Please attach your CV.",
            "empty": "That file is empty. Please choose your CV again.",
        },
    )
    # Hidden spam trap: real people never see or fill this
    website = forms.CharField(
        required=False,
        widget=HoneypotInput(
            attrs={"autocomplete": "off", "tabindex": "-1"}),
    )
    # autocomplete=off stops the browser refilling an old token into a fresh form
    submission_token = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"autocomplete": "off"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["submission_token"].initial = uuid.uuid4().hex

    def clean_submission_token(self):
        # A missing or malformed token just skips the duplicate check
        token = self.cleaned_data.get("submission_token") or ""
        return token if TOKEN_RE.fullmatch(token) else None

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not NAME_RE.match(name):
            raise ValidationError(
                "Your name can only contain letters, spaces, hyphens, apostrophes and full stops.")
        return name

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if count_links(message) > MAX_LINKS:
            raise ValidationError(
                f"Please include no more than {MAX_LINKS} links in your message.")
        return message

    def clean_cv(self):
        f = self.cleaned_data.get("cv")
        if not f:
            return f
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in CV_SIGNATURES:
            raise ValidationError(
                "Your CV must be a PDF or Word document (.pdf, .doc or .docx).")
        if f.size > CV_MAX_MB * 1024 * 1024:
            raise ValidationError(
                f"Your CV is {f.size / 1048576:.1f} MB. Please upload a file of "
                f"{CV_MAX_MB} MB or less.")
        head = f.read(8)
        f.seek(0)
        if not head.startswith(CV_SIGNATURES[ext]):
            raise ValidationError(
                f"This file doesn't look like a genuine {ext} document. "
                "Please save or export your CV again and re-upload it.")
        f.name = clean_upload_name(f.name)
        return f

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError(
                "Your submission could not be sent. Please try again.")
        return ""
