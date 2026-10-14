from django.urls import path

from django.contrib import admin
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils.html import format_html
from .models import LeadershipMember
from .reports import (orders_workbook, xlsx_response, PRESETS,
                      resolve_period, build_order_report, report_workbook)
from .models import Product, NewsArticle, GalleryImage, JobPosting, EmployeeStory, NewsCategory, NewsTag, OrderRequest, OrderItem, OrderItemOption, ContactMessage, JobApplication


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("position", "item_description",
              "color", "length", "gsm", "quantity")
    ordering = ("position", "id")


class HasLpoFilter(admin.SimpleListFilter):
    title = "LPO attached"
    parameter_name = "has_lpo"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        no_lpo = Q(lpo_file="") | Q(lpo_file__isnull=True)
        if self.value() == "yes":
            return queryset.exclude(no_lpo)
        if self.value() == "no":
            return queryset.filter(no_lpo)
        return queryset


@admin.action(description="Export selected orders to Excel")
def export_orders_xlsx(modeladmin, request, queryset):
    filename = f"kenturian-orders-{timezone.localdate():%Y-%m-%d}.xlsx"
    return xlsx_response(orders_workbook(queryset), filename)


@admin.register(OrderRequest)
class OrderRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "company_name", "item_count", "total_kg",
                    "preferred_delivery_date", "delivery_location",
                    "status", "client_email_sent", "created_at")
    list_filter = ("status", "items__item_description", HasLpoFilter,
                   "client_email_sent", "created_at")
    search_fields = ("reference", "company_name", "contact_person",
                     "email", "phone", "items__item_description")
    readonly_fields = ("reference", "created_at")
    list_editable = ("status",)
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    actions = [export_orders_xlsx]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("items")

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.items.count()

    @admin.display(description="Total kg")
    def total_kg(self, obj):
        return f"{obj.total_quantity:,}"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["can_view_report"] = request.user.has_perm(
            "main.view_order_report")
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            qs = response.context_data["cl"].queryset
        except (AttributeError, KeyError):
            return response   # e.g. a redirect after saving
        totals = OrderItem.objects.filter(order__in=qs.values("pk")).aggregate(
            kg=Sum("quantity"), lines=Count("id"))
        response.context_data["order_totals"] = {
            "orders": qs.count(),
            "lines": totals["lines"],
            "kg": totals["kg"] or 0,
        }
        return response

    def get_urls(self):
        custom = [
            path("report/", self.admin_site.admin_view(self.report_view),
                 name="main_orderrequest_report"),
        ]
        return custom + super().get_urls()

    def report_view(self, request):
        if not request.user.has_perm("main.view_order_report"):
            raise PermissionDenied

        preset, start, end = resolve_period(request.GET)
        report = build_order_report(start, end)

        if request.GET.get("export") == "xlsx":
            filename = f"kenturian-order-report-{start:%Y%m%d}-{end:%Y%m%d}.xlsx"
            return xlsx_response(report_workbook(report), filename)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Order report",
            "report": report,
            "preset": preset,
            "presets": PRESETS,
        }
        return TemplateResponse(request, "admin/main/orderrequest/report.html", context)


@admin.register(OrderItemOption)
class OrderItemOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'is_active')
    list_editable = ('display_order', 'is_active')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'price',
                    'theme_color_swatch', 'thumbnail', 'owner', 'created_at')
    list_editable = ('display_order',)
    search_fields = ('name', 'description')
    list_filter = ('created_at',)
    readonly_fields = ('thumbnail',)

    def thumbnail(self, obj):
        if not obj or not getattr(obj, 'image', None):
            return "No image"
        try:
            url = obj.image.url
            return format_html('<img src="{}" style="height:60px; object-fit:cover; border-radius:4px;" />', url)
        except Exception:
            return "No image"
    thumbnail.short_description = 'Preview'

    def theme_color_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block; width:20px; height:20px; '
            'border-radius:4px; background:{}; border:1px solid #ccc; vertical-align:middle;"></span> {}',
            obj.theme_color, obj.theme_color
        )
    theme_color_swatch.short_description = 'Theme color'


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'uploaded_at', 'thumbnail')
    list_filter = ('category',)
    list_editable = ('category',)
    search_fields = ('title', 'caption')
    readonly_fields = ('thumbnail',)

    def thumbnail(self, obj):
        if not obj or not getattr(obj, 'image', None):
            return "No image"
        try:
            url = obj.image.url
            return format_html('<img src="{}" style="height:60px; object-fit:cover; border-radius:4px;" />', url)
        except Exception:
            return "No image"
    thumbnail.short_description = 'Preview'


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'location',
                    'employment_type', 'qualification', 'is_open', 'posted_at')
    search_fields = ('title', 'department', 'location', 'description')
    list_filter = ('is_open', 'department', 'employment_type', 'qualification')


@admin.register(EmployeeStory)
class EmployeeStoryAdmin(admin.ModelAdmin):
    list_display = ('author_name', 'author_role',
                    'is_active', 'order', 'thumbnail')
    list_editable = ('is_active', 'order')
    search_fields = ('author_name', 'author_role', 'quote')
    readonly_fields = ('thumbnail',)

    def thumbnail(self, obj):
        if not obj or not getattr(obj, 'photo', None):
            return "No photo"
        try:
            return format_html('<img src="{}" style="height:50px; border-radius:50%; object-fit:cover;" />', obj.photo.url)
        except Exception:
            return "No photo"
    thumbnail.short_description = 'Preview'


@admin.register(NewsCategory)
class NewsCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug')


@admin.register(NewsTag)
class NewsTagAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug')


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    list_display = ('title', 'category', 'is_published', 'published_at')
    list_filter = ('category', 'tags', 'is_published')
    search_fields = ('title', 'excerpt', 'body')
    filter_horizontal = ('tags',)


@admin.register(LeadershipMember)
class LeadershipMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'is_featured', 'order')
    list_editable = ('is_featured', 'order')
    list_filter = ('is_featured',)
    ordering = ('-is_featured', 'order')


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("reference", "name", "email", "subject",
                    "client_email_sent", "created_at")
    list_filter = ("client_email_sent",)
    search_fields = ("reference", "name", "email", "subject")
    readonly_fields = ("reference", "created_at")


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("reference", "name", "job", "email",
                    "client_email_sent", "created_at")
    list_filter = ("job", "client_email_sent")
    search_fields = ("reference", "name", "email")
    readonly_fields = ("reference", "created_at")
