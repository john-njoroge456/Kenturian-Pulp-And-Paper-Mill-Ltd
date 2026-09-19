from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.utils.text import Truncator
from .models import OrderRequest
from .forms import OrderRequestForm

from .forms import ContactForm, JobApplicationForm
from django.core.paginator import Paginator
from .models import (
    Product, NewsArticle, NewsCategory, NewsTag, GalleryImage,
    JobPosting, EmployeeStory, LeadershipMember, ContactMessage, JobApplication
)


def order_request_view(request):
    hero_image = GalleryImage.objects.filter(
        category='order_hero').order_by("-uploaded_at").first()
    if request.method == "POST":
        form = OrderRequestForm(request.POST, request.FILES)
        if form.is_valid():
            order = form.save()
            subject = f"New order request {order.reference} — {order.company_name}"
            message = (
                f"Reference: {order.reference}\n"
                f"Item: {order.item_description} | Color: {order.color or '-'}\n"
                f"Length: {order.length} mm | GSM: {order.gsm} | "
                f"Quantity: {order.quantity} kg\n"
                f"Delivery location: {order.delivery_location or '-'} | "
                f"Preferred date: {order.preferred_delivery_date or '-'}\n"
                f"Contact: {order.contact_person}, {order.phone}, {order.email}\n"
                f"Notes: {order.notes or '-'}\n"
                f"LPO attached: {'Yes' if order.lpo_file else 'No'}"
            )
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [
                          settings.COMPANY_EMAIL])
            except Exception:
                pass

            # Send a confirmation copy to the client for their own records
            client_subject = f"Your order request {order.reference} — Kenturian Pulp & Paper Mills Limited"
            client_message = (
                f"Hi {order.contact_person},\n\n"
                f"Thanks for your order request — here's a copy for your records.\n\n"
                f"Reference: {order.reference}\n"
                f"Item: {order.item_description} | Color: {order.color or '-'}\n"
                f"Length: {order.length} mm | GSM: {order.gsm} | "
                f"Quantity: {order.quantity} kg\n"
                f"Delivery location: {order.delivery_location or '-'} | "
                f"Preferred date: {order.preferred_delivery_date or '-'}\n\n"
                f"Our team will review your request and follow up shortly. "
                f"Please quote reference {order.reference} in any correspondence.\n\n"
                f"— Kenturian Pulp & Paper Mills Limited"
            )
            try:
                send_mail(client_subject, client_message, settings.DEFAULT_FROM_EMAIL, [
                          order.email])
                order.client_email_sent = True
                order.save(update_fields=["client_email_sent"])
            except Exception:
                pass

            return redirect(reverse("main:order_success", args=[order.reference]))
    else:
        form = OrderRequestForm()
    return render(request, "main/order.html", {"form": form, "hero_image": hero_image})


def order_success_view(request, reference):
    order = get_object_or_404(OrderRequest, reference=reference)
    return render(request, "main/order_success.html", {"order": order})


def about_view(request):
    hero_image = GalleryImage.objects.filter(category='about_hero').first()
    story_image = GalleryImage.objects.filter(category='about_story').first()
    leadership = LeadershipMember.objects.all()
    return render(request, 'main/about.html', {
        'hero_image': hero_image,
        'story_image': story_image,
        'leadership': leadership,
    })


def careers_view(request):
    hero_image = GalleryImage.objects.filter(
        category='careers_hero').order_by('-uploaded_at').first()
    jobs = JobPosting.objects.filter(is_open=True).order_by('-posted_at')
    stories_qs = EmployeeStory.objects.filter(is_active=True)
    employee_stories_data = [
        {
            'quote': Truncator(s.quote).words(70, truncate='…'),
            'author_name': s.author_name,
            'author_role': s.author_role,
        }
        for s in stories_qs
    ]
    return render(request, 'main/careers.html', {
        'hero_image': hero_image,
        'jobs': jobs,
        'employee_stories_data': employee_stories_data,
    })


def news_list_view(request):
    hero_image = GalleryImage.objects.filter(category='news_hero').first()
    news = NewsArticle.objects.filter(
        is_published=True).order_by('-published_at')

    category_slug = request.GET.get('category')
    tag_slug = request.GET.get('tag')

    if category_slug:
        news = news.filter(category__slug=category_slug)
    if tag_slug:
        news = news.filter(tags__slug=tag_slug)

    paginator = Paginator(news, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'main/news.html', {
        'news_list': page_obj,
        'page_obj': page_obj,
        'categories': NewsCategory.objects.all(),
        'tags': NewsTag.objects.all(),
        'active_category': category_slug,
        'active_tag': tag_slug,
        'hero_image': hero_image,
    })


def news_detail_view(request, slug):
    article = get_object_or_404(NewsArticle, slug=slug, is_published=True)
    related = NewsArticle.objects.filter(
        is_published=True, category=article.category
    ).exclude(pk=article.pk)[:3]
    return render(request, 'main/news_detail.html', {
        'article': article,
        'related': related,
    })


def index(request):
    products = Product.objects.all().order_by('display_order')[:6]
    news = NewsArticle.objects.all().order_by('-published_at')[:3]
    gallery = GalleryImage.objects.filter(
        category='home_hero').order_by('uploaded_at')[:6]
    return render(request, 'main/index.html', {
        'products': products,
        'news_list': news,
        'gallery': gallery,
    })


def job_detail_view(request, pk):
    job = get_object_or_404(JobPosting, pk=pk, is_open=True)
    hero_image = GalleryImage.objects.filter(
        category='careers_hero').order_by('-uploaded_at').first()
    sent = False
    if request.method == 'POST':
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
            record = JobApplication.objects.create(
                job=job, name=cd['name'], email=cd['email'],
                phone=cd.get('phone', ''), message=cd['message'],
                cv_file=cd['cv'],
            )
            subject = f"Job Application: {job.title} — {cd['name']} (Ref {record.reference})"
            body = (
                f"Reference: {record.reference}\n"
                f"Applicant: {cd['name']}\n"
                f"Email: {cd['email']}\n"
                f"Phone: {cd.get('phone') or 'N/A'}\n\n"
                f"Message:\n{cd['message']}"
            )
            email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [
                                 settings.COMPANY_EMAIL])
            cv_file = cd['cv']
            email.attach(cv_file.name, cv_file.read(), cv_file.content_type)
            try:
                email.send()
                sent = True

                client_subject = f"We've received your application — Ref {record.reference}"
                client_message = (
                    f"Hi {cd['name']},\n\n"
                    f"Thanks for applying for {job.title} — here's a copy for your records.\n\n"
                    f"Reference: {record.reference}\n"
                    f"Position: {job.title}\n"
                    f"Phone: {cd.get('phone') or 'N/A'}\n\n"
                    f"Your message:\n{cd['message']}\n\n"
                    f"Our team will review your application and reach out if it's a good fit. "
                    f"Please quote reference {record.reference} in any follow-up.\n\n"
                    f"— Kenturian Pulp & Paper Mills Limited"
                )
                try:
                    send_mail(client_subject, client_message, settings.DEFAULT_FROM_EMAIL, [
                              cd['email']])
                    record.client_email_sent = True
                    record.save(update_fields=["client_email_sent"])
                except Exception:
                    pass

                form = JobApplicationForm()
            except Exception:
                pass
    else:
        form = JobApplicationForm()
    return render(request, 'main/job_detail.html', {
        'job': job, 'form': form, 'sent': sent, 'hero_image': hero_image,
    })


def general_application_view(request):
    hero_image = GalleryImage.objects.filter(
        category='careers_hero').order_by('-uploaded_at').first()
    sent = False
    if request.method == 'POST':
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
            record = JobApplication.objects.create(
                job=None, name=cd['name'], email=cd['email'],
                phone=cd.get('phone', ''), message=cd['message'],
                cv_file=cd['cv'],
            )
            subject = f"Speculative Application: {cd['name']} (Ref {record.reference})"
            body = (
                f"Reference: {record.reference}\n"
                f"Applicant: {cd['name']}\n"
                f"Email: {cd['email']}\n"
                f"Phone: {cd.get('phone') or 'N/A'}\n\n"
                f"Message:\n{cd['message']}"
            )
            email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [
                settings.COMPANY_EMAIL])
            cv_file = cd['cv']
            email.attach(cv_file.name, cv_file.read(), cv_file.content_type)
            try:
                email.send()
                sent = True

                client_subject = f"We've received your application — Ref {record.reference}"
                client_message = (
                    f"Hi {cd['name']},\n\n"
                    f"Thanks for your interest — here's a copy for your records.\n\n"
                    f"Reference: {record.reference}\n"
                    f"Phone: {cd.get('phone') or 'N/A'}\n\n"
                    f"Your message:\n{cd['message']}\n\n"
                    f"We'll reach out if a matching opportunity opens up. "
                    f"Please quote reference {record.reference} in any follow-up.\n\n"
                    f"— Kenturian Pulp & Paper Mills Limited"
                )
                try:
                    send_mail(client_subject, client_message, settings.DEFAULT_FROM_EMAIL, [
                              cd['email']])
                    record.client_email_sent = True
                    record.save(update_fields=["client_email_sent"])
                except Exception:
                    pass

                form = JobApplicationForm()
            except Exception:
                pass
    else:
        form = JobApplicationForm()
    return render(request, 'main/general_application.html', {
        'form': form, 'sent': sent, 'hero_image': hero_image,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'main/product_detail.html', {'product': product})


def contact_view(request):
    hero_image = GalleryImage.objects.filter(
        category='contact_hero').order_by('-uploaded_at').first()
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            record = ContactMessage.objects.create(
                name=cd['name'], email=cd['email'],
                subject=cd['subject'], message=cd['message'],
            )
            subject = f"Website contact: {cd['subject']}"
            message = f"Reference: {record.reference}\nFrom: {cd['name']} <{cd['email']}>\n\n{cd['message']}"
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [
                          settings.COMPANY_EMAIL])
            except Exception:
                pass

            client_subject = f"We've received your message — Ref {record.reference}"
            client_message = (
                f"Hi {cd['name']},\n\n"
                f"Thanks for reaching out — here's a copy for your records.\n\n"
                f"Reference: {record.reference}\n"
                f"Subject: {cd['subject']}\n\n"
                f"{cd['message']}\n\n"
                f"Our team will get back to you shortly. Please quote reference {record.reference} "
                f"in any follow-up.\n\n"
                f"— Kenturian Pulp & Paper Mills Limited"
            )
            try:
                send_mail(client_subject, client_message, settings.DEFAULT_FROM_EMAIL, [
                          cd['email']])
                record.client_email_sent = True
                record.save(update_fields=["client_email_sent"])
            except Exception:
                pass

            return redirect(reverse('main:contact') + '?sent=1')
    else:
        initial_subject = request.GET.get('subject', '')
        form = ContactForm(initial={'subject': initial_subject})
    sent = request.GET.get('sent') == '1'
    return render(request, 'main/contact.html', {'form': form, 'sent': sent, 'hero_image': hero_image})


def privacy_view(request):
    return render(request, 'privacy.html')


def terms_view(request):
    return render(request, 'terms.html')
