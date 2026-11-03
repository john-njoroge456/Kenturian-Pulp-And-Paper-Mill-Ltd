import os
import re
from django.core.exceptions import ValidationError

SIGNATURES = {
    ".pdf": [b"%PDF"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".doc": [b"\xd0\xcf\x11\xe0"],
    ".docx": [b"PK\x03\x04"],
}


def validate_upload(uploaded, allowed=(".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"), max_mb=5):
    """Raise a ValidationError that says exactly what is wrong with the file."""
    if not uploaded:
        return
    ext = os.path.splitext(uploaded.name)[1].lower()
    nice = ", ".join(e.lstrip(".").upper() for e in allowed)

    if ext not in allowed:
        raise ValidationError(
            f"'{uploaded.name}' is not an accepted file type. Please upload one of: {nice}."
        )
    if uploaded.size > max_mb * 1_000_000:
        size_mb = uploaded.size / 1_000_000
        raise ValidationError(
            f"'{uploaded.name}' is {size_mb:.1f} MB. The maximum is {max_mb} MB, "
            "so please compress the file or upload a smaller one."
        )
    head = uploaded.read(8)
    uploaded.seek(0)
    if not any(head.startswith(sig) for sig in SIGNATURES[ext]):
        raise ValidationError(
            f"'{uploaded.name}' does not look like a real {ext.lstrip('.').upper()} file. "
            "Please re-save it and try again."
        )


def normalize_phone(raw):
    """Check a phone number and return it as +<digits> (Kenyan numbers as +254...)."""
    raw = (raw or "").strip()
    if not raw:
        return raw
    if not re.fullmatch(r"\+?[0-9\s\-().]+", raw):
        raise ValidationError(
            "The phone number can only contain digits, spaces, dashes and a leading +. "
            "Please remove any letters or symbols."
        )
    digits = re.sub(r"\D", "", raw)

    national = digits.removeprefix("254")
    if not national.strip("0"):
        raise ValidationError(
            "This doesn't look like a real phone number. Please check it and try again."
        )

    if raw.startswith("+") and digits.startswith("0"):
        raise ValidationError(
            "A country code can't start with 0. For a Kenyan number, enter "
            "0712 345 678 or +254 712 345 678."
        )

    if raw.startswith("+") and not digits.startswith("254"):
        if not 8 <= len(digits) <= 15:
            raise ValidationError(
                "International numbers need 8 to 15 digits including the country code, "
                "e.g. +256 700 123 456."
            )
        return "+" + digits

    if digits.startswith("254"):
        if digits[3] == "0":
            raise ValidationError(
                "Leave out the 0 after +254, e.g. +254 712 345 678.")
        if len(digits) != 12:
            raise ValidationError(
                "A Kenyan number starting with +254 needs 9 digits after the code, "
                "e.g. +254 712 345 678."
            )
        return "+" + digits

    if digits.startswith("0"):
        if digits[1] == "0":
            raise ValidationError(
                "A Kenyan number starts with a single 0, e.g. 0712 345 678. "
                "For an international number, use + and the country code instead of 00."
            )
        if len(digits) != 10:
            raise ValidationError(
                "A Kenyan number starting with 0 must have 10 digits, e.g. 0712 345 678."
            )
        return "+254" + digits[1:]

    raise ValidationError(
        "Start the number with 0 (e.g. 0712 345 678) or with the country code "
        "(e.g. +254 712 345 678)."
    )
