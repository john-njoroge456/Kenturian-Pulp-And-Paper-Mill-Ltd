import logging
import mimetypes
import os
from django.template.loader import render_to_string
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail, EmailMessage, EmailMultiAlternatives
from django.utils.text import Truncator
from django.core.paginator import Paginator
from django.db import transaction
from .models import OrderRequest
from .forms import OrderRequestForm, OrderItemFormSet, MAX_ITEMS


from .models import (
    Product, NewsArticle, NewsCategory, NewsTag, GalleryImage,
    JobPosting, EmployeeStory, LeadershipMember, ContactMessage, JobApplication
)
from .forms import ContactForm, JobApplicationForm

logger = logging.getLogger(__name__)


def _order_item_lines(items):
    return "\n".join(
        f"  {n}. {i.item_description} | Colour: {i.color or '-'} | "
        f"Length: {i.length} mm | GSM: {i.gsm} | Qty: {i.quantity} kg"
        for n, i in enumerate(items, 1)
    )


def order_request_view(request):
    hero_image = GalleryImage.objects.filter(
        category='order_hero').order_by("-uploaded_at").first()

    if request.method == "POST":
        form = OrderRequestForm(request.POST, request.FILES)
        formset = OrderItemFormSet(
            request.POST, instance=OrderRequest(), prefix="items")
        form_ok = form.is_valid()
        items_ok = formset.is_valid()   # run both so every error shows at once

        if form_ok and items_ok:
            with transaction.atomic():
                order = form.save()
                formset.instance = order
                items = formset.save(commit=False)
                for position, item in enumerate(items, start=1):
                    item.position = position
                    item.save()

            items = list(order.items.all())
            item_lines = _order_item_lines(items)
            total_kg = sum(i.quantity for i in items)
            email_ctx = {"order": order, "items": items, "total_kg": total_kg}
            html_company = render_to_string(
                "emails/order_summary.html", {**email_ctx, "for_client": False})
            html_client = render_to_string(
                "emails/order_summary.html", {**email_ctx, "for_client": True})
            subject = (f"New order request — {order.company_name} — "
                       f"{len(items)} item{'s' if len(items) != 1 else ''} (Ref {order.reference})")
            message = (
                f"Reference: {order.reference}\n"
                f"Items ({len(items)}):\n{item_lines}\n"
                f"Total quantity: {total_kg} kg\n\n"
                f"Delivery location: {order.delivery_location or '-'} | "
                f"Preferred date: {order.preferred_delivery_date or '-'}\n"
                f"Contact: {order.contact_person}, {order.phone}, {order.email}\n"
                f"Notes: {order.notes or '-'}\n"
                f"LPO attached: {'Yes' if order.lpo_file else 'No'}"
            )
            try:
                staff_email = EmailMultiAlternatives(
                    subject, message, settings.DEFAULT_FROM_EMAIL,
                    [settings.COMPANY_EMAIL], reply_to=[order.email])
                staff_email.attach_alternative(html_company, "text/html")
                if order.lpo_file:
                    lpo_name = os.path.basename(order.lpo_file.name)
                    lpo_type = mimetypes.guess_type(
                        lpo_name)[0] or "application/octet-stream"
                    with order.lpo_file.open("rb") as f:
                        staff_email.attach(lpo_name, f.read(), lpo_type)
                staff_email.send()
            except Exception:
                logger.exception(
                    "Staff email failed for order %s", order.reference)
            client_subject = f"Your order request {order.reference} — Kenturian Pulp & Paper Mills Limited"
            client_message = (
                f"Hi {order.contact_person},\n\n"
                f"Thanks for your order request — here's a copy for your records.\n\n"
                f"Reference: {order.reference}\n"
                f"Items ({len(items)}):\n{item_lines}\n"
                f"Total quantity: {total_kg} kg\n\n"
                f"Delivery location: {order.delivery_location or '-'} | "
                f"Preferred date: {order.preferred_delivery_date or '-'}\n\n"
                f"Our team will review your request and follow up shortly. "
                f"Please quote reference {order.reference} in any correspondence.\n\n"
                f"— Kenturian Pulp & Paper Mills Limited"
            )
            try:
                send_mail(client_subject, client_message,
                          settings.DEFAULT_FROM_EMAIL, [order.email], html_message=html_client)
                order.client_email_sent = True
                order.save(update_fields=["client_email_sent"])
            except Exception:
                pass

            return redirect(reverse("main:order_success", args=[order.reference]))
    else:
        form = OrderRequestForm()
        formset = OrderItemFormSet(instance=OrderRequest(), prefix="items")

    return render(request, "main/order.html", {
        "form": form,
        "formset": formset,
        "max_items": MAX_ITEMS,
        "hero_image": hero_image,
    })


def order_success_view(request, reference):
    order = get_object_or_404(
        OrderRequest.objects.prefetch_related("items"), reference=reference)
    return render(request, "main/order_success.html", {"order": order})


def about_view(request):
    hero_image = GalleryImage.objects.filter(category='about_hero').first()
    story_image = GalleryImage.objects.filter(category='about_story').first()
    leadership = LeadershipMember.objects.filter(is_featured=True)
    team = LeadershipMember.objects.filter(is_featured=False)
    return render(request, 'main/about.html', {
        'hero_image': hero_image,
        'story_image': story_image,
        'leadership': leadership,
        'team': team,
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


def _process_application(form, job=None):
    """Save a valid application, then email HR and the applicant.
    Email failures are logged but never hide a saved application."""
    cd = form.cleaned_data
    record = JobApplication.objects.create(
        job=job, name=cd["name"], email=cd["email"],
        phone=cd["phone"], message=cd["message"], cv_file=cd["cv"],
    )

    if job:
        subject = f"New job application — {job.title} — {cd['name']} (Ref {record.reference})"
    else:
        subject = f"New CV (speculative) — {cd['name']} (Ref {record.reference})"
    body = (
        f"Reference: {record.reference}\n"
        f"Applicant: {cd['name']}\n"
        f"Email: {cd['email']}\n"
        f"Phone: {cd['phone']}\n\n"
        f"Message:\n{cd['message']}"
    )
    email_ctx = {"application": record, "job": job}
    html_staff = render_to_string(
        "emails/application.html", {**email_ctx, "for_client": False})
    html_client = render_to_string(
        "emails/application.html", {**email_ctx, "for_client": True})
    try:
        hr_email = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL,
                                          [settings.COMPANY_EMAIL], reply_to=[cd["email"]])
        hr_email.attach_alternative(html_staff, "text/html")
        # Re-open the saved file: the upload stream was already consumed by save()
        filename = os.path.basename(record.cv_file.name)
        content_type = mimetypes.guess_type(
            filename)[0] or "application/octet-stream"
        with record.cv_file.open("rb") as f:
            hr_email.attach(filename, f.read(), content_type)
        hr_email.send()
    except Exception:
        logger.exception("HR email failed for application %s",
                         record.reference)

    position_line = f"Position: {job.title}\n" if job else ""
    intro = (f"Thanks for applying for {job.title}" if job
             else "Thanks for your interest")
    closing = ("Our team will review your application and reach out if it's a good fit."
               if job else "We'll reach out if a matching opportunity opens up.")
    client_message = (
        f"Hi {cd['name']},\n\n"
        f"{intro} — here's a copy for your records.\n\n"
        f"Reference: {record.reference}\n"
        f"{position_line}"
        f"Phone: {cd['phone']}\n\n"
        f"Your message:\n{cd['message']}\n\n"
        f"{closing} Please quote reference {record.reference} in any follow-up.\n\n"
        f"— Kenturian Pulp & Paper Mills Limited"
    )
    try:
        send_mail(f"We've received your application — Ref {record.reference}",
                  client_message, settings.DEFAULT_FROM_EMAIL, [cd["email"]],
                  html_message=html_client)
        record.client_email_sent = True
        record.save(update_fields=["client_email_sent"])
    except Exception:
        logger.exception(
            "Applicant email failed for application %s", record.reference)

    return record


def job_detail_view(request, pk):
    job = get_object_or_404(JobPosting, pk=pk, is_open=True)
    hero_image = GalleryImage.objects.filter(
        category='careers_hero').order_by('-uploaded_at').first()
    if request.method == 'POST':
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            _process_application(form, job=job)
            return redirect(reverse('main:job_detail', args=[job.pk]) + '?sent=1')
    else:
        form = JobApplicationForm()
    sent = request.GET.get('sent') == '1'
    return render(request, 'main/job_detail.html', {
        'job': job, 'form': form, 'sent': sent, 'hero_image': hero_image,
    })


def general_application_view(request):
    hero_image = GalleryImage.objects.filter(
        category='careers_hero').order_by('-uploaded_at').first()
    if request.method == 'POST':
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            _process_application(form)
            return redirect(reverse('main:general_application') + '?sent=1')
    else:
        form = JobApplicationForm()
    sent = request.GET.get('sent') == '1'
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
            subject = f"New enquiry from {cd['name']} — {cd['subject']} (Ref {record.reference})"
            message = f"Reference: {record.reference}\nFrom: {cd['name']} <{cd['email']}>\n\n{cd['message']}"
            html_staff = render_to_string(
                "emails/contact_message.html", {"record": record, "for_client": False})
            html_client = render_to_string(
                "emails/contact_message.html", {"record": record, "for_client": True})
            try:
                staff_email = EmailMultiAlternatives(
                    subject, message, settings.DEFAULT_FROM_EMAIL,
                    [settings.COMPANY_EMAIL], reply_to=[cd['email']])
                staff_email.attach_alternative(html_staff, "text/html")
                staff_email.send()
            except Exception:
                logger.exception(
                    "Staff email failed for contact %s", record.reference)

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
                send_mail(client_subject, client_message, settings.DEFAULT_FROM_EMAIL,
                          [cd['email']], html_message=html_client)
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
