import os
import shutil
import tempfile
from unittest import mock

from django.core import mail
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from .models import (
    ContactMessage,
    JobApplication,
    JobPosting,
    OrderItemOption,
    OrderRequest,
)


class OrderResubmitTests(TestCase):
    """FX-25: a form sent once (Back, then Submit) must not create a second order."""

    def setUp(self):
        OrderItemOption.objects.create(name="Kraft Liner")
        self.order_url = reverse("main:order")

    def get_token(self, client=None):
        response = (client or self.client).get(self.order_url)
        return response.context["form"]["submission_token"].value()

    def order_data(self, token, quantity=500):
        return {
            "submission_token": token,
            "company_name": "Acme Traders Ltd",
            "contact_person": "Jane Doe",
            "phone": "0712345678",
            "email": "jane@example.com",
            "delivery_location": "Thika",
            "notes": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "10",
            "items-0-item_description": "Kraft Liner",
            "items-0-color": "Brown",
            "items-0-color_other": "",
            "items-0-length": "1500",
            "items-0-gsm": "80",
            "items-0-quantity": str(quantity),
        }

    def success_url(self, order):
        return reverse("main:order_success", args=[order.reference])

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


class ApplicationResubmitMixin:
    """FX-32: an application form sent once (Back, then Submit) must not create a
    second application. Subclasses set up self.url and self.job."""

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
