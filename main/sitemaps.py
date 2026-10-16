from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import JobPosting, NewsArticle


class StaticPagesSitemap(Sitemap):
    changefreq = "monthly"

    def items(self):
        return ["main:index", "main:about", "main:careers", "main:news_list",
                "main:contact", "main:order", "main:general_application",
                "main:privacy", "main:terms"]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == "main:index" else 0.6


class NewsSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return NewsArticle.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.published_at or obj.created_at


class JobSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return JobPosting.objects.filter(is_open=True)

    def location(self, obj):
        return reverse("main:job_detail", args=[obj.pk])


sitemaps = {"pages": StaticPagesSitemap,
            "news": NewsSitemap, "jobs": JobSitemap}
