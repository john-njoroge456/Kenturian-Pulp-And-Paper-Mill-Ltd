from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

STAFF_GROUPS = {
    "Sales": [
        ("main", "view_orderrequest"), ("main",
                                        "change_orderrequest"), ("main", "add_orderrequest"),
        ("main", "view_orderitem"), ("main",
                                     "change_orderitem"), ("main", "add_orderitem"),
        ("main", "view_order_report"),
        ("main", "view_contactmessage"),
    ],
    "HR": [
        ("main", "view_jobapplication"), ("main", "change_jobapplication"),
        ("main", "view_jobposting"), ("main",
                                      "add_jobposting"), ("main", "change_jobposting"),
        ("main", "view_employeestory"), ("main",
                                         "add_employeestory"), ("main", "change_employeestory"),
    ],
}


class Command(BaseCommand):
    help = "Create or update the Sales and HR staff groups with their limited permissions."

    def handle(self, *args, **options):
        for name, codes in STAFF_GROUPS.items():
            group, created = Group.objects.get_or_create(name=name)
            perms = []
            for app_label, codename in codes:
                try:
                    perms.append(Permission.objects.get(
                        content_type__app_label=app_label, codename=codename))
                except Permission.DoesNotExist:
                    self.stderr.write(self.style.WARNING(
                        f"Missing permission {app_label}.{codename} — run migrate first."))
            group.permissions.set(perms)
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(
                f"{action} '{name}' group with {len(perms)} permissions."))
