import os
import shutil
import tempfile
from unittest import mock

from django.core import mail
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from .forms import ContactForm, JobApplicationForm, OrderRequestForm, count_links
from .models import (
    ContactMessage,
    JobApplication,
    JobPosting,
    NewsArticle,
    OrderItem,
    OrderItemOption,
    OrderRequest,
)


class OrderFormMixin:
    """Shared setup for the order form tests."""

    def setUp(self):
        OrderItemOption.objects.create(name="Kraft Liner")
        self.order_url = reverse("main:order")

    def get_token(self, client=None):
        response = (client or self.client).get(self.order_url)
        return response.context["form"]["submission_token"].value()

    def order_data(self, token, quantity=500, gsms=("80",)):
        # One Kraft Liner item per GSM; different GSMs keep the items distinct
        data = {
            "submission_token": token,
            "company_name": "Acme Traders Ltd",
            "contact_person": "Jane Doe",
            "phone": "0712345678",
            "email": "jane@example.com",
            "delivery_location": "Thika",
            "notes": "",
            "items-TOTAL_FORMS": str(len(gsms)),
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "10",
        }
        for n, gsm in enumerate(gsms):
            data.update({
                f"items-{n}-item_description": "Kraft Liner",
                f"items-{n}-color": "Brown",
                f"items-{n}-color_other": "",
                f"items-{n}-length": "1500",
                f"items-{n}-gsm": gsm,
                f"items-{n}-quantity": str(quantity),
            })
        return data

    def success_url(self, order):
        return reverse("main:order_success", args=[order.reference])


class OrderResubmitTests(OrderFormMixin, TestCase):
    """FX-25: a form sent once (Back, then Submit) must not create a second order."""

    def test_order_page_is_not_stored(self):
        response = self.client.get(self.order_url)
        self.assertIn("no-store", response["Cache-Control"])

    def test_order_form_turns_off_restore(self):
        response = self.client.get(self.order_url)
        self.assertRegex(
            response.content.decode(), r'<form [^>]*id="orderForm"[^>]*autocomplete="off"')

    def test_back_and_resubmit_with_changed_quantity_does_not_duplicate(self):
        token = self.get_token()
        response = self.client.post(self.order_url, self.order_data(token))
        order = OrderRequest.objects.get()
        self.assertRedirects(response, self.success_url(order))
        self.assertEqual(len(mail.outbox), 2)

        # Back restores the old form; the client changes the quantity and submits
        response = self.client.post(
            self.order_url, self.order_data(token, quantity=900))
        self.assertRedirects(
            response, self.success_url(order), fetch_redirect_response=False)
        self.assertEqual(OrderRequest.objects.count(), 1)
        self.assertEqual(order.items.get().quantity, 500)
        self.assertEqual(len(mail.outbox), 2)

        page = self.client.get(self.success_url(order))
        self.assertContains(page, "already sent")
        self.assertContains(page, "Place Another Order")
        # The notice shows once
        self.assertNotContains(
            self.client.get(self.success_url(order)), "already sent")

        # Place Another Order gives a fresh form that creates a new order
        new_token = self.get_token()
        self.assertNotEqual(new_token, token)
        response = self.client.post(
            self.order_url, self.order_data(new_token, quantity=900))
        self.assertEqual(OrderRequest.objects.count(), 2)
        new_order = OrderRequest.objects.get(submission_token=new_token)
        self.assertNotEqual(new_order.reference, order.reference)
        self.assertRedirects(response, self.success_url(new_order))

    def test_duplicate_token_from_other_session_shows_no_order(self):
        token = self.get_token()
        self.client.post(self.order_url, self.order_data(token))

        response = Client().post(self.order_url, self.order_data(token))
        self.assertRedirects(response, self.order_url)
        self.assertEqual(OrderRequest.objects.count(), 1)

    def test_invalid_post_keeps_token(self):
        token = self.get_token()
        data = self.order_data(token)
        data["company_name"] = ""
        response = self.client.post(self.order_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"]["submission_token"].value(), token)
        self.assertFalse(OrderRequest.objects.exists())

    def test_simultaneous_submit_hits_unique_token(self):
        token = self.get_token()
        existing = OrderRequest.objects.create(
            company_name="Acme Traders Ltd", contact_person="Jane Doe",
            phone="0712345678", email="jane@example.com",
            delivery_location="Thika", submission_token=token)
        session = self.client.session
        session["placed_orders"] = [existing.reference]
        session.save()

        # The other request saves between our lookup and our insert
        with mock.patch("main.views._order_for_token",
                        side_effect=[None, existing]):
            response = self.client.post(self.order_url, self.order_data(token))
        self.assertRedirects(
            response, self.success_url(existing), fetch_redirect_response=False)
        self.assertEqual(OrderRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)


class ContactResubmitTests(TestCase):
    """FX-32: a contact form sent once (Back, then Submit) must not create a second message."""

    def setUp(self):
        self.contact_url = reverse("main:contact")
        self.sent_url = self.contact_url + "?sent=1"

    def get_token(self, client=None):
        response = (client or self.client).get(self.contact_url)
        return response.context["form"]["submission_token"].value()

    def contact_data(self, token, message="Please send us a quote for kraft liner rolls."):
        return {
            "submission_token": token,
            "name": "Jane Doe",
            "email": "jane@example.com",
            "subject": "Quote request",
            "message": message,
            "fax_number": "",
        }

    def test_contact_page_is_not_stored(self):
        response = self.client.get(self.contact_url)
        self.assertIn("no-store", response["Cache-Control"])

    def test_contact_form_turns_off_restore(self):
        response = self.client.get(self.contact_url)
        self.assertRegex(
            response.content.decode(),
            r'<form [^>]*class="application-form"[^>]*autocomplete="off"')

    def test_back_and_resubmit_with_changed_message_does_not_duplicate(self):
        token = self.get_token()
        response = self.client.post(self.contact_url, self.contact_data(token))
        self.assertRedirects(response, self.sent_url)
        record = ContactMessage.objects.get()
        self.assertEqual(len(mail.outbox), 2)

        # Back restores the old form; the visitor edits the message and submits
        response = self.client.post(self.contact_url, self.contact_data(
            token, message="Actually, please quote for fluting medium instead."))
        self.assertRedirects(
            response, self.sent_url, fetch_redirect_response=False)
        self.assertEqual(ContactMessage.objects.count(), 1)
        record.refresh_from_db()
        self.assertIn("kraft liner", record.message)
        self.assertEqual(len(mail.outbox), 2)

        # Send Another Message gives a fresh form that creates a new message
        new_token = self.get_token()
        self.assertNotEqual(new_token, token)
        response = self.client.post(self.contact_url, self.contact_data(new_token))
        self.assertRedirects(response, self.sent_url)
        self.assertEqual(ContactMessage.objects.count(), 2)

    def test_duplicate_token_from_other_session_redirects_to_sent(self):
        # The sent page shows nothing private, so no session check is needed
        token = self.get_token()
        self.client.post(self.contact_url, self.contact_data(token))

        response = Client().post(self.contact_url, self.contact_data(token))
        self.assertRedirects(
            response, self.sent_url, fetch_redirect_response=False)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_invalid_post_keeps_token(self):
        token = self.get_token()
        data = self.contact_data(token)
        data["subject"] = ""
        response = self.client.post(self.contact_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"]["submission_token"].value(), token)
        self.assertFalse(ContactMessage.objects.exists())

    def test_simultaneous_submit_hits_unique_token(self):
        token = self.get_token()
        existing = ContactMessage.objects.create(
            name="Jane Doe", email="jane@example.com", subject="Quote request",
            message="Please send us a quote for kraft liner rolls.",
            submission_token=token)

        # The other request saves between our lookup and our insert
        with mock.patch("main.views._contact_for_token",
                        side_effect=[None, existing]):
            response = self.client.post(self.contact_url, self.contact_data(token))
        self.assertRedirects(
            response, self.sent_url, fetch_redirect_response=False)
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)


class ContactEmailLengthTests(TestCase):
    """FX-24: the contact email allows 254 characters, like the order and application forms."""

    def data(self, email):
        return {
            "name": "Jane Doe",
            "email": email,
            "subject": "Quote request",
            "message": "Please send us a quote for kraft liner rolls.",
            "fax_number": "",
        }

    def test_254_characters_accepted(self):
        email = "a" * 242 + "@example.com"
        self.assertEqual(len(email), 254)
        form = ContactForm(data=self.data(email))
        self.assertTrue(form.is_valid(), form.errors)

    def test_255_characters_rejected(self):
        email = "a" * 243 + "@example.com"
        self.assertEqual(len(email), 255)
        form = ContactForm(data=self.data(email))
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["email"],
            ["Please enter an email address of 254 characters or fewer."])

    def test_input_maxlength_is_254(self):
        response = self.client.get(reverse("main:contact"))
        self.assertRegex(
            response.content.decode(),
            r'<input [^>]*name="email"[^>]*maxlength="254"')


HONEYPOT_MARKER = "hp-bot-7f3a"


class ContactHoneypotTests(TestCase):
    """FX-16: a filled honeypot looks like success, keeps nothing and is never echoed."""

    def setUp(self):
        self.contact_url = reverse("main:contact")
        self.sent_url = self.contact_url + "?sent=1"

    def contact_data(self, fax_number=HONEYPOT_MARKER, **overrides):
        data = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "subject": "Quote request",
            "message": "Please send us a quote for kraft liner rolls.",
            "fax_number": fax_number,
        }
        data.update(overrides)
        return data

    def test_filled_honeypot_redirects_to_sent_and_keeps_nothing(self):
        response = self.client.post(self.contact_url, self.contact_data())
        self.assertRedirects(response, self.sent_url)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_filled_honeypot_with_invalid_fields_still_redirects(self):
        response = self.client.post(self.contact_url, self.contact_data(name=""))
        self.assertRedirects(response, self.sent_url)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_sent_page_does_not_echo_value(self):
        response = self.client.post(
            self.contact_url, self.contact_data(), follow=True)
        self.assertContains(response, "Message Sent!")
        self.assertNotContains(response, HONEYPOT_MARKER)

    def test_bound_form_never_renders_value(self):
        form = ContactForm(data=self.contact_data())
        self.assertFalse(form.is_valid())
        self.assertNotIn(HONEYPOT_MARKER, str(form["fax_number"]))

    def test_spaces_only_honeypot_is_treated_as_empty(self):
        response = self.client.post(self.contact_url, self.contact_data(fax_number="   "))
        self.assertRedirects(response, self.sent_url)
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)


class OrderHoneypotTests(OrderFormMixin, TestCase):
    """FX-35: a filled order honeypot looks like success, keeps nothing (no order,
    no emails, no LPO) and never shows the value or any order back."""

    def setUp(self):
        super().setUp()
        self.sent_url = self.order_url + "?sent=1"
        # private_storage fixes its location at import, so point the LPO field
        # at a temporary folder instead of the real private_media/
        self.lpo_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.lpo_dir, ignore_errors=True)
        patcher = mock.patch.object(
            OrderRequest._meta.get_field("lpo_file"), "storage",
            FileSystemStorage(location=self.lpo_dir))
        patcher.start()
        self.addCleanup(patcher.stop)

    def stored_lpos(self):
        return [name for _, _, files in os.walk(self.lpo_dir) for name in files]

    def two_item_data(self, kp_hp_check=HONEYPOT_MARKER, **overrides):
        data = self.order_data(self.get_token(), gsms=("80", "100"))
        # A new file each time: an uploaded file is consumed once posted
        data["lpo_file"] = SimpleUploadedFile(
            "lpo.pdf", b"%PDF-1.4 test lpo", content_type="application/pdf")
        data["kp_hp_check"] = kp_hp_check
        data.update(overrides)
        return data

    def assert_nothing_kept(self):
        self.assertFalse(OrderRequest.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.stored_lpos(), [])
        self.assertNotIn("placed_orders", self.client.session)

    def test_filled_honeypot_redirects_to_sent_and_keeps_nothing(self):
        response = self.client.post(self.order_url, self.two_item_data())
        self.assertRedirects(response, self.sent_url)
        self.assert_nothing_kept()

    def test_filled_honeypot_with_invalid_fields_still_redirects(self):
        data = self.two_item_data(company_name="", **{"items-0-gsm": "9999"})
        response = self.client.post(self.order_url, data)
        self.assertRedirects(response, self.sent_url)
        self.assert_nothing_kept()

    def test_sent_page_does_not_echo_value(self):
        response = self.client.post(
            self.order_url, self.two_item_data(), follow=True)
        self.assertTrue(response.context["sent"])
        self.assertContains(response, "Order Request Received")
        # Generic card only: no form, no reference, nothing that was posted
        self.assertNotContains(response, 'id="orderForm"')
        for text in (HONEYPOT_MARKER, "KPM-", "Acme Traders", "jane@example.com"):
            self.assertNotContains(response, text)

    def test_bound_form_never_renders_value(self):
        form = OrderRequestForm(data={"kp_hp_check": HONEYPOT_MARKER})
        self.assertFalse(form.is_valid())
        self.assertIn("kp_hp_check", form.errors)
        self.assertNotIn(HONEYPOT_MARKER, str(form["kp_hp_check"]))

    def test_spaces_only_honeypot_is_treated_as_empty(self):
        response = self.client.post(
            self.order_url, self.two_item_data(kp_hp_check="   "))
        order = OrderRequest.objects.get()
        self.assertRedirects(response, self.success_url(order))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(len(self.stored_lpos()), 1)

    def test_multi_item_order_unaffected(self):
        response = self.client.post(
            self.order_url, self.two_item_data(kp_hp_check=""))
        order = OrderRequest.objects.get()
        self.assertRedirects(response, self.success_url(order))
        self.assertEqual(
            [(i.position, i.gsm) for i in order.items.all()], [(1, 80), (2, 100)])

    def test_trap_rendered_outside_item_rows(self):
        content = self.client.get(self.order_url).content.decode()
        self.assertEqual(content.count('name="kp_hp_check"'), 1)
        self.assertRegex(
            content,
            r'<div class="hp-field" aria-hidden="true">\s*<label[^>]*>[^<]*</label>\s*'
            r'<input [^>]*name="kp_hp_check"[^>]*tabindex="-1"')
        row_template = content.split('<template id="itemRowTemplate">', 1)[1]
        row_template = row_template.split("</template>", 1)[0]
        self.assertNotIn("kp_hp_check", row_template)
        # The no-JS note is still there
        self.assertContains(
            self.client.get(self.order_url), "JavaScript is turned off")


class ApplicationFormMixin:
    """Shared setup for the careers form tests. Subclasses set up self.url and self.job."""

    job = None

    def setUp(self):
        self.sent_url = self.url + "?sent=1"
        # private_storage fixes its location at import, so point the CV field
        # at a temporary folder instead of the real private_media/
        self.cv_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cv_dir, ignore_errors=True)
        patcher = mock.patch.object(
            JobApplication._meta.get_field("cv_file"), "storage",
            FileSystemStorage(location=self.cv_dir))
        patcher.start()
        self.addCleanup(patcher.stop)

    def stored_cvs(self):
        return [name for _, _, files in os.walk(self.cv_dir) for name in files]

    def get_token(self, client=None):
        response = (client or self.client).get(self.url)
        return response.context["form"]["submission_token"].value()

    def app_data(self, token, message="I have five years of experience running paper machines.",
                 cv=True):
        data = {
            "submission_token": token,
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "0712345678",
            "message": message,
            "website": "",
        }
        if cv:
            # A new file each time: an uploaded file is consumed once posted
            data["cv"] = SimpleUploadedFile(
                "cv.pdf", b"%PDF-1.4 test cv", content_type="application/pdf")
        return data


class ApplicationHoneypotMixin(ApplicationFormMixin):
    """FX-16: a filled honeypot looks like success, keeps nothing and is never echoed."""

    def test_filled_honeypot_redirects_to_sent_and_keeps_nothing(self):
        data = self.app_data(self.get_token())
        data["website"] = HONEYPOT_MARKER
        response = self.client.post(self.url, data)
        self.assertRedirects(response, self.sent_url)
        self.assertFalse(JobApplication.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.stored_cvs(), [])

    def test_filled_honeypot_with_invalid_fields_still_redirects(self):
        data = self.app_data(self.get_token())
        data.update(website=HONEYPOT_MARKER, name="")
        response = self.client.post(self.url, data)
        self.assertRedirects(response, self.sent_url)
        self.assertFalse(JobApplication.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.stored_cvs(), [])

    def test_sent_page_does_not_echo_value(self):
        data = self.app_data(self.get_token())
        data["website"] = HONEYPOT_MARKER
        response = self.client.post(self.url, data, follow=True)
        self.assertTrue(response.context["sent"])
        self.assertNotContains(response, HONEYPOT_MARKER)

    def test_bound_form_never_renders_value(self):
        form = JobApplicationForm(data={"website": HONEYPOT_MARKER})
        self.assertFalse(form.is_valid())
        self.assertNotIn(HONEYPOT_MARKER, str(form["website"]))


class ApplicationResubmitMixin(ApplicationFormMixin):
    """FX-32: an application form sent once (Back, then Submit) must not create a
    second application."""

    def test_page_is_not_stored(self):
        response = self.client.get(self.url)
        self.assertIn("no-store", response["Cache-Control"])

    def test_form_turns_off_restore(self):
        response = self.client.get(self.url)
        self.assertRegex(
            response.content.decode(),
            r'<form [^>]*class="application-form"[^>]*autocomplete="off"')

    def test_back_and_resubmit_with_changed_message_does_not_duplicate(self):
        token = self.get_token()
        response = self.client.post(self.url, self.app_data(token))
        self.assertRedirects(response, self.sent_url)
        record = JobApplication.objects.get()
        self.assertEqual(record.job, self.job)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(len(mail.outbox[0].attachments), 1)
        self.assertEqual(len(self.stored_cvs()), 1)

        # Back restores the old form; the applicant edits the message, picks
        # the CV again and submits
        response = self.client.post(self.url, self.app_data(
            token, message="Actually, I would also like to mention my forklift licence."))
        self.assertRedirects(
            response, self.sent_url, fetch_redirect_response=False)
        self.assertEqual(JobApplication.objects.count(), 1)
        record.refresh_from_db()
        self.assertIn("paper machines", record.message)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(len(self.stored_cvs()), 1)

        # A fresh form creates a new application
        new_token = self.get_token()
        self.assertNotEqual(new_token, token)
        response = self.client.post(self.url, self.app_data(new_token))
        self.assertRedirects(response, self.sent_url)
        self.assertEqual(JobApplication.objects.count(), 2)

    def test_resubmit_without_cv_goes_to_sent(self):
        # Browsers clear the file field on Back
        token = self.get_token()
        self.client.post(self.url, self.app_data(token))

        response = self.client.post(self.url, self.app_data(token, cv=False))
        self.assertRedirects(
            response, self.sent_url, fetch_redirect_response=False)
        self.assertEqual(JobApplication.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_duplicate_token_from_other_session_shows_no_reference(self):
        # The sent page shows nothing private, so no session check is needed
        token = self.get_token()
        self.client.post(self.url, self.app_data(token))

        other = Client()
        response = other.post(self.url, self.app_data(token))
        self.assertRedirects(
            response, self.sent_url, fetch_redirect_response=False)
        self.assertEqual(JobApplication.objects.count(), 1)
        page = other.get(self.sent_url)
        self.assertNotContains(page, JobApplication.objects.get().reference)
        self.assertNotContains(page, "APP-")

    def test_invalid_post_keeps_token(self):
        token = self.get_token()
        data = self.app_data(token)
        data["name"] = ""
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"]["submission_token"].value(), token)
        self.assertFalse(JobApplication.objects.exists())
        self.assertEqual(self.stored_cvs(), [])

    def test_simultaneous_submit_hits_unique_token(self):
        token = self.get_token()
        existing = JobApplication.objects.create(
            job=self.job, name="Jane Doe", email="jane@example.com",
            phone="0712345678",
            message="I have five years of experience running paper machines.",
            cv_file=SimpleUploadedFile("cv.pdf", b"%PDF-1.4 first"),
            submission_token=token)

        # The other request saves between our lookup and our insert
        with mock.patch("main.views._application_for_token",
                        side_effect=[None, existing]):
            response = self.client.post(self.url, self.app_data(token))
        self.assertRedirects(
            response, self.sent_url, fetch_redirect_response=False)
        self.assertEqual(JobApplication.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        # Only the first request's CV is left on disk
        self.assertEqual(len(self.stored_cvs()), 1)


class JobApplicationResubmitTests(ApplicationResubmitMixin, TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Machine Operator", description="Runs the paper machine.")
        self.url = reverse("main:job_detail", args=[self.job.pk])
        super().setUp()


class GeneralApplicationResubmitTests(ApplicationResubmitMixin, TestCase):
    def setUp(self):
        self.url = reverse("main:general_application")
        super().setUp()


class JobApplicationHoneypotTests(ApplicationHoneypotMixin, TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Machine Operator", description="Runs the paper machine.")
        self.url = reverse("main:job_detail", args=[self.job.pk])
        super().setUp()


class GeneralApplicationHoneypotTests(ApplicationHoneypotMixin, TestCase):
    def setUp(self):
        self.url = reverse("main:general_application")
        super().setUp()


class NavActiveTests(TestCase):
    """FX-21: News and Careers stay active on their sub-pages."""

    def setUp(self):
        self.article = NewsArticle.objects.create(
            title="Mill expansion", body="New paper machine installed.")
        self.job = JobPosting.objects.create(
            title="Machine Operator", description="Runs the paper machine.")
        self.news_link = f'class="nav-link active" href="{reverse("main:news_list")}"'
        self.careers_link = f'class="nav-link active" href="{reverse("main:careers")}"'

    def assertActive(self, url, news, careers):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(self.news_link in html, news, f"News active on {url}")
        self.assertEqual(
            self.careers_link in html, careers, f"Careers active on {url}")

    def test_news_pages(self):
        self.assertActive(reverse("main:news_list"), news=True, careers=False)
        self.assertActive(
            reverse("main:news_detail", args=[self.article.slug]),
            news=True, careers=False)

    def test_careers_pages(self):
        for url in (
            reverse("main:careers"),
            reverse("main:job_detail", args=[self.job.pk]),
            reverse("main:general_application"),
        ):
            self.assertActive(url, news=False, careers=True)

    def test_other_pages_unaffected(self):
        self.assertActive(reverse("main:about"), news=False, careers=False)


class ConfirmationEmailMixin:
    """FX-37: the visitor's copy goes to whatever address was typed in, so it
    carries no visitor text apart from the first name."""

    def emails_to(self, address):
        sent = [m for m in mail.outbox if m.to == [address]]
        self.assertEqual(len(sent), 1)
        message = sent[0]
        return message.body, message.alternatives[0][0]

    def assert_client_copy_clean(self, address, markers, greeting="Hi Jane,"):
        for part in self.emails_to(address):
            self.assertIn(greeting, part)
            for marker in markers:
                self.assertNotIn(marker, part)

    def assert_staff_copy_full(self, markers):
        staff = [m for m in mail.outbox if m.to != ["jane@example.com"]]
        self.assertEqual(len(staff), 1)
        # The plain contact body leaves the subject to the email's subject line
        plain = f"{staff[0].subject}\n{staff[0].body}"
        for part in (plain, staff[0].alternatives[0][0]):
            for marker in markers:
                self.assertIn(marker, part)


class ContactConfirmationEmailTests(ConfirmationEmailMixin, TestCase):
    def post(self, name="Jane Doe"):
        return self.client.post(reverse("main:contact"), {
            "name": name,
            "email": "jane@example.com",
            "subject": "Subjectmarker for kenturian.co.ke",
            "message": "Messagemarker: Submit kenturian.co.ke now: indexhelper.live",
            "fax_number": "",
        })

    def test_client_copy_has_no_visitor_text(self):
        self.post()
        record = ContactMessage.objects.get()
        self.assert_client_copy_clean(
            "jane@example.com", ["Jane Doe", "Subjectmarker", "Messagemarker", "indexhelper"])
        for part in self.emails_to("jane@example.com"):
            self.assertIn(record.reference, part)
        self.assert_staff_copy_full(["Jane Doe", "Subjectmarker", "Messagemarker"])

    def test_name_that_is_not_a_name_gets_plain_greeting(self):
        self.post(name="indexhelper.live Smith")
        self.assert_client_copy_clean(
            "jane@example.com", ["indexhelper", "Smith"], greeting="Hello,")


class OrderConfirmationEmailTests(OrderFormMixin, ConfirmationEmailMixin, TestCase):
    def test_client_copy_has_no_visitor_text(self):
        data = self.order_data(self.get_token(), gsms=("80", "100"))
        data.update({
            "delivery_location": "Locationmarker",
            "notes": "Notesmarker indexdomain.live",
            "items-1-color": "Other",
            "items-1-color_other": "Colourmarker",
        })
        self.client.post(self.order_url, data)
        order = OrderRequest.objects.get()
        markers = ["Jane Doe", "Locationmarker", "Notesmarker", "indexdomain", "Colourmarker"]
        self.assert_client_copy_clean("jane@example.com", markers)
        for part in self.emails_to("jane@example.com"):
            self.assertIn(order.reference, part)
            self.assertIn("Kraft Liner", part)
            self.assertIn("Brown", part)
            self.assertIn("Other (as specified)", part)
        self.assert_staff_copy_full(["Jane Doe", "Locationmarker", "Notesmarker", "Colourmarker"])


class ApplicationConfirmationEmailMixin(ApplicationFormMixin, ConfirmationEmailMixin):
    def test_client_copy_has_no_visitor_text(self):
        self.client.post(self.url, self.app_data(
            self.get_token(), message="Messagemarker: see indexhelper.live for my work."))
        record = JobApplication.objects.get()
        self.assert_client_copy_clean(
            "jane@example.com", ["Jane Doe", record.phone, "Messagemarker", "indexhelper"])
        for part in self.emails_to("jane@example.com"):
            self.assertIn(record.reference, part)
            if self.job:
                self.assertIn(self.job.title, part)
        self.assert_staff_copy_full(["Jane Doe", record.phone, "Messagemarker"])


class JobApplicationConfirmationEmailTests(ApplicationConfirmationEmailMixin, TestCase):
    def setUp(self):
        self.job = JobPosting.objects.create(
            title="Machine Operator", description="Runs the paper machine.")
        self.url = reverse("main:job_detail", args=[self.job.pk])
        super().setUp()


class GeneralApplicationConfirmationEmailTests(ApplicationConfirmationEmailMixin, TestCase):
    def setUp(self):
        self.url = reverse("main:general_application")
        super().setUp()


# The two real spam messages received through the contact form (FX-37)
SPAM_MESSAGES = (
    "Submit kenturian.co.ke now: indexhelper.live",
    "Include kenturian.co.ke today: indexdomain.live",
)


class LinkCountTests(TestCase):
    """FX-37: bare domains count as links; ordinary text does not."""

    def test_real_spam_counts_one_link_each(self):
        for text in SPAM_MESSAGES:
            self.assertEqual(count_links(text), 1, text)

    def test_counted(self):
        cases = {
            "http://a.com www.b.com c.live": 3,
            "HTTPS://Spam.Example.COM/path": 1,
            "see spam.co.ke, then indexdomain.live.": 2,
            "indexhelper.live/submit?x=1": 1,
        }
        for text, expected in cases.items():
            self.assertEqual(count_links(text), expected, text)

    def test_not_counted(self):
        for text in (
            "Visit kenturian.co.ke for details",
            "https://kenturian.co.ke/products and www.kenturian.co.ke",
            "Email me at jane@example.com or sales@kenturian.co.ke",
            "We need 2.5 tonnes, i.e. about 2,500 kg",
            "Kraft liner, e.g. 80 GSM rolls",
            "I attached LPO.pdf and quote.docx",
            "Thanks for the quote.Next week works.",
            "Size 1.5kg, Ph.D. holder, U.S.A. based",
        ):
            self.assertEqual(count_links(text), 0, text)


class LinkLimitFormTests(ApplicationFormMixin, TestCase):
    """FX-37: over the limit keeps the visible error so a real visitor can fix
    and resend; one link or our own domain still goes through."""

    def setUp(self):
        self.url = reverse("main:general_application")
        super().setUp()
        self.contact_url = reverse("main:contact")

    def post_contact(self, message):
        return self.client.post(self.contact_url, {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "subject": "Quote request",
            "message": message,
            "fax_number": "",
        })

    def test_contact_three_bare_domains_show_error(self):
        message = "Please list us on a.live b.live c.live"
        response = self.post_contact(message)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please remove some links")
        self.assertContains(response, message)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_one_link_goes_through(self):
        response = self.post_contact("Our specs are at https://example.com/specs")
        self.assertRedirects(response, self.contact_url + "?sent=1")
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_contact_mentioning_our_domain_goes_through(self):
        response = self.post_contact(
            "I found your prices on kenturian.co.ke and would like a quote.")
        self.assertRedirects(response, self.contact_url + "?sent=1")
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_application_three_bare_domains_show_error(self):
        data = self.app_data(
            self.get_token(), message="My portfolio: a.live b.live c.live and more.")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please include no more than")
        self.assertFalse(JobApplication.objects.exists())
        self.assertEqual(self.stored_cvs(), [])
