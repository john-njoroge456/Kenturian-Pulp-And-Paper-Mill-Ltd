from unittest import mock

from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from .models import OrderItemOption, OrderRequest


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
