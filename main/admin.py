from django.contrib import admin
from django.utils.html import format_html
from .models import Product, NewsArticle, GalleryImage

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'owner', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'published_at', 'created_at')
    search_fields = ('title', 'excerpt', 'body')
    list_filter = ('published_at',)


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_at', 'thumbnail')
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
