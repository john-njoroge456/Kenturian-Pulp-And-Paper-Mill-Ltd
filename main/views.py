from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail
from .models import Product, NewsArticle, GalleryImage
from .forms import ContactForm

def index(request):
    products = Product.objects.all().order_by('-created_at')[:6]
    news = NewsArticle.objects.all().order_by('-published_at')[:3]
    gallery = GalleryImage.objects.all().order_by('-uploaded_at')[:8]
    return render(request, 'main/index.html', {
        'products': products,
        'news_list': news,
        'gallery': gallery,
    })

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'main/product_detail.html', {'product': product})

def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            subject = f"Website contact: {cd['subject']}"
            message = f"From: {cd['name']} <{cd['email']}>\n\n{cd['message']}"
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [settings.COMPANY_EMAIL])
            except Exception:
                # In dev, email may not be configured; ignore or log in production
                pass
            return redirect(reverse('main:contact') + '?sent=1')
    else:
        form = ContactForm()
    sent = request.GET.get('sent') == '1'
    return render(request, 'main/contact.html', {'form': form, 'sent': sent})
