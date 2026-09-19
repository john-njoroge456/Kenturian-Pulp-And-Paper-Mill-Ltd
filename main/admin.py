from .models import LeadershipMember
from django.contrib import admin

from django.utils.html import format_html
from .models import Product, NewsArticle, GalleryImage, JobPosting, EmployeeStory, NewsCategory, NewsTag, OrderRequest, OrderItemOption, ContactMessage, JobApplication


@admin.register(OrderRequest)
class OrderRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "company_name", "item_description",
                    "color", "quantity", "status", "client_email_sent", "created_at")
    list_filter = ("status", "item_description",
                   "client_email_sent", "created_at")
    search_fields = ("reference", "company_name",
                     "contact_person", "email", "phone")
    readonly_fields = ("reference", "created_at")
    list_editable = ("status",)


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
    list_display = ('name', 'title', 'order')
    list_editable = ('order',)


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
