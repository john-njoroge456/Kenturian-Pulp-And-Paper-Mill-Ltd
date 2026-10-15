import os
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
