import os

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image

from main.models import EmployeeStory, GalleryImage, LeadershipMember, NewsArticle, Product

# (model, image field, maximum width in pixels)
JOBS = [
    (GalleryImage, "image", 1920),
    (NewsArticle, "featured_image", 1600),
    (Product, "image", 1400),
    (EmployeeStory, "photo", 800),
    (LeadershipMember, "photo", 800),
]
SMALL_ENOUGH = 300_000  # bytes; smaller files within the width limit are left alone


class Command(BaseCommand):
    help = ("Resize large uploaded images and convert them to web-friendly formats: "
            "JPEG for photos, WebP for images with transparency. Updates the database.")

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change without changing anything.")

    def handle(self, *args, dry_run=False, **options):
        root = str(settings.MEDIA_ROOT)
        before_total = after_total = 0

        for model, field, max_w in JOBS:
            for obj in model.objects.all():
                f = getattr(obj, field)
                if not f:
                    continue
                path = os.path.join(root, f.name)
                if not os.path.exists(path):
                    self.stdout.write(self.style.WARNING(f"Missing: {f.name}"))
                    continue

                before = os.path.getsize(path)
                im = Image.open(path)
                if before < SMALL_ENOUGH and im.width <= max_w:
                    continue

                has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
                if has_alpha:
                    im = im.convert("RGBA")
                    if im.getchannel("A").getextrema()[0] == 255:
                        has_alpha = False  # transparency not actually used

                if im.width > max_w:
                    im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)

                base = os.path.splitext(f.name)[0]
                new_name = base + (".webp" if has_alpha else ".jpg")
                new_path = os.path.join(root, new_name)

                if dry_run:
                    self.stdout.write(f"Would convert {f.name} ({before / 1e6:.1f} MB) -> {new_name}")
                    continue

                if has_alpha:
                    im.save(new_path, "WEBP", quality=82, method=6)
                else:
                    im.convert("RGB").save(new_path, "JPEG", quality=82, optimize=True, progressive=True)
                after = os.path.getsize(new_path)

                if new_name != f.name:
                    setattr(obj, field, new_name)
                    obj.save(update_fields=[field])
                    os.remove(path)

                before_total += before
                after_total += after
                self.stdout.write(f"{f.name}: {before / 1e6:.1f} MB -> {new_name.split('/')[-1]}: {after / 1e6:.2f} MB")

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"Done: {before_total / 1e6:.1f} MB -> {after_total / 1e6:.1f} MB"))
