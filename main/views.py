from django.shortcuts import render
from .models import Product, NewsArticle, GalleryImage

def index(request):
    products = Product.objects.all().order_by('-created_at')[:6]
    news = NewsArticle.objects.all().order_by('-published_at')[:3]
    gallery = GalleryImage.objects.all().order_by('-uploaded_at')[:8]
    return render(request, 'main/index.html', {
        'products': products,
        'news_list': news,
        'gallery': gallery,
    })
