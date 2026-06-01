"""
Comprehensive test suite for the Invoice application.
Run with: python manage.py test invoice --verbosity=2
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
import datetime

from .models import SellerProfile, Buyer, Invoice, InvoiceItem


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_seller(**kwargs):
    defaults = dict(
        company_name='테스트 상회',
        address='서울시 중구 1-1',
        phone='02-1234-5678',
        bank_account='국민은행 123-456-789',
        is_default=True,
    )
    defaults.update(kwargs)
    return SellerProfile.objects.create(**defaults)


def make_buyer(**kwargs):
    defaults = dict(name='홍길동', has_delivery_fee=False, has_deduction=False)
    defaults.update(kwargs)
    return Buyer.objects.create(**defaults)


def make_invoice(seller, buyer, items=None, **kwargs):
    defaults = dict(
        seller=seller,
        buyer=buyer,
        date=datetime.date(2026, 6, 1),
        delivery_fee=0,
        deduction=0,
        payment_received=0,
        previous_balance=0,
        current_balance=0,
    )
    defaults.update(kwargs)
    inv = Invoice.objects.create(**defaults)
    for item in (items or []):
        InvoiceItem.objects.create(
            invoice=inv,
            product_name=item['name'],
            quantity=item['qty'],
            boxes=item['boxes'],
            unit_price=item['price'],
            order=item.get('order', 0),
        )
    inv.current_balance = inv.calculate_current_balance()
    inv.save()
    return inv


# ─── Model: SellerProfile ─────────────────────────────────────────────────────

class SellerProfileModelTest(TestCase):

    def test_str(self):
        seller = make_seller()
        self.assertEqual(str(seller), '테스트 상회')

    def test_only_one_default_at_a_time(self):
        s1 = make_seller(company_name='A 상회', is_default=True)
        s2 = make_seller(company_name='B 상회', is_default=True)
        s1.refresh_from_db()
        self.assertFalse(s1.is_default)
        self.assertTrue(s2.is_default)

    def test_non_default_seller(self):
        seller = make_seller(is_default=False)
        self.assertFalse(seller.is_default)


# ─── Model: Buyer ─────────────────────────────────────────────────────────────

class BuyerModelTest(TestCase):

    def test_str(self):
        buyer = make_buyer()
        self.assertEqual(str(buyer), '홍길동')

    def test_get_last_invoice_none(self):
        buyer = make_buyer()
        self.assertIsNone(buyer.get_last_invoice())

    def test_get_current_balance_no_invoices(self):
        buyer = make_buyer()
        self.assertEqual(buyer.get_current_balance(), 0)

    def test_get_current_balance_with_invoice(self):
        seller = make_seller()
        buyer = make_buyer()
        inv = make_invoice(
            seller, buyer,
            items=[{'name': '사과', 'qty': 10, 'boxes': 2, 'price': 5000}],
        )
        self.assertEqual(buyer.get_current_balance(), inv.current_balance)


# ─── Model: InvoiceItem ───────────────────────────────────────────────────────

class InvoiceItemModelTest(TestCase):

    def setUp(self):
        self.seller = make_seller()
        self.buyer = make_buyer()
        self.inv = make_invoice(self.seller, self.buyer)

    def test_amount_auto_calculated(self):
        item = InvoiceItem.objects.create(
            invoice=self.inv,
            product_name='배',
            quantity=Decimal('5'),
            boxes=Decimal('3'),
            unit_price=Decimal('2000'),
        )
        # 5 * 3 * 2000 = 30000
        self.assertEqual(item.amount, Decimal('30000'))

    def test_str(self):
        item = InvoiceItem.objects.create(
            invoice=self.inv,
            product_name='감',
            quantity=1,
            boxes=1,
            unit_price=1000,
        )
        self.assertIn('감', str(item))

    def test_zero_quantity_gives_zero_amount(self):
        item = InvoiceItem.objects.create(
            invoice=self.inv,
            product_name='귤',
            quantity=0,
            boxes=5,
            unit_price=3000,
        )
        self.assertEqual(item.amount, Decimal('0'))


# ─── Model: Invoice ───────────────────────────────────────────────────────────

class InvoiceModelTest(TestCase):

    def setUp(self):
        self.seller = make_seller()
        self.buyer = make_buyer()

    def test_str(self):
        inv = make_invoice(self.seller, self.buyer)
        self.assertIn('홍길동', str(inv))

    def test_calculate_total_amount(self):
        inv = make_invoice(
            self.seller, self.buyer,
            items=[
                {'name': '사과', 'qty': 2, 'boxes': 3, 'price': 1000},  # 6000
                {'name': '배',   'qty': 1, 'boxes': 5, 'price': 2000},  # 10000
            ],
        )
        self.assertEqual(inv.calculate_total_amount(), Decimal('16000'))

    def test_calculate_current_balance(self):
        # Create a prior invoice so previous_balance is carried over automatically
        make_invoice(
            self.seller, self.buyer,
            items=[{'name': '첫번째', 'qty': 1, 'boxes': 1, 'price': 3000}],  # balance = 3000
        )
        inv = make_invoice(
            self.seller, self.buyer,
            items=[{'name': '감', 'qty': 4, 'boxes': 2, 'price': 500}],  # 4000
            delivery_fee=1000,
            deduction=500,
            payment_received=2000,
        )
        # previous_balance auto = 3000; 4000 + 1000 - 500 - 2000 + 3000 = 5500
        self.assertEqual(inv.calculate_current_balance(), Decimal('5500'))

    def test_previous_balance_carries_over(self):
        inv1 = make_invoice(
            self.seller, self.buyer,
            items=[{'name': '사과', 'qty': 10, 'boxes': 1, 'price': 1000}],
        )
        inv2 = Invoice(
            seller=self.seller,
            buyer=self.buyer,
            date=datetime.date(2026, 6, 2),
            delivery_fee=0,
            deduction=0,
            payment_received=0,
            current_balance=0,
        )
        inv2.save()
        self.assertEqual(inv2.previous_balance, inv1.current_balance)

    def test_ordering_newest_first(self):
        inv1 = make_invoice(self.seller, self.buyer, date=datetime.date(2026, 1, 1))
        inv2 = make_invoice(self.seller, self.buyer, date=datetime.date(2026, 6, 1))
        invoices = list(Invoice.objects.all())
        self.assertEqual(invoices[0], inv2)
        self.assertEqual(invoices[1], inv1)


# ─── Views ───────────────────────────────────────────────────────────────────

class DashboardViewTest(TestCase):

    def test_dashboard_200(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_buyers(self):
        make_buyer(name='김영희')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '김영희')


class InvoiceViewTest(TestCase):

    def setUp(self):
        self.seller = make_seller()
        self.buyer = make_buyer()

    def test_invoice_list_200(self):
        response = self.client.get(reverse('invoice_list'))
        self.assertEqual(response.status_code, 200)

    def test_invoice_list_filter_by_buyer(self):
        make_invoice(self.seller, self.buyer)
        url = reverse('invoice_list') + f'?buyer={self.buyer.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '홍길동')

    def test_invoice_new_get(self):
        response = self.client.get(reverse('invoice_new'))
        self.assertEqual(response.status_code, 200)

    def test_invoice_new_post_creates_invoice(self):
        data = {
            'seller': self.seller.pk,
            'buyer': self.buyer.pk,
            'date': '2026-06-01',
            'delivery_fee': '0',
            'deduction': '0',
            'payment_received': '0',
            'product_name[]': ['사과', '배'],
            'quantity[]': ['10', '5'],
            'boxes[]': ['2', '3'],
            'unit_price[]': ['1000', '2000'],
        }
        response = self.client.post(reverse('invoice_new'), data)
        self.assertEqual(Invoice.objects.count(), 1)
        inv = Invoice.objects.first()
        self.assertRedirects(response, reverse('invoice_detail', kwargs={'pk': inv.pk}))

    def test_invoice_new_post_calculates_balance(self):
        data = {
            'seller': self.seller.pk,
            'buyer': self.buyer.pk,
            'date': '2026-06-01',
            'delivery_fee': '500',
            'deduction': '200',
            'payment_received': '1000',
            'product_name[]': ['사과'],
            'quantity[]': ['2'],
            'boxes[]': ['3'],
            'unit_price[]': ['1000'],  # 2*3*1000 = 6000
        }
        self.client.post(reverse('invoice_new'), data)
        inv = Invoice.objects.first()
        # 6000 + 500 - 200 - 1000 + 0 = 5300
        self.assertEqual(inv.current_balance, Decimal('5300'))

    def test_invoice_new_skips_empty_rows(self):
        data = {
            'seller': self.seller.pk,
            'buyer': self.buyer.pk,
            'date': '2026-06-01',
            'delivery_fee': '0',
            'deduction': '0',
            'payment_received': '0',
            'product_name[]': ['사과', ''],
            'quantity[]': ['5', '0'],
            'boxes[]': ['1', '0'],
            'unit_price[]': ['1000', '0'],
        }
        self.client.post(reverse('invoice_new'), data)
        inv = Invoice.objects.first()
        self.assertEqual(inv.invoiceitem_set.count(), 1)

    def test_invoice_detail_200(self):
        inv = make_invoice(self.seller, self.buyer)
        response = self.client.get(reverse('invoice_detail', kwargs={'pk': inv.pk}))
        self.assertEqual(response.status_code, 200)

    def test_invoice_detail_404(self):
        response = self.client.get(reverse('invoice_detail', kwargs={'pk': 9999}))
        self.assertEqual(response.status_code, 404)

    def test_invoice_print_200(self):
        inv = make_invoice(self.seller, self.buyer)
        response = self.client.get(reverse('invoice_print', kwargs={'pk': inv.pk}))
        self.assertEqual(response.status_code, 200)

    def test_invoice_print_pads_to_12_rows(self):
        inv = make_invoice(
            self.seller, self.buyer,
            items=[{'name': '사과', 'qty': 1, 'boxes': 1, 'price': 1000}],
        )
        response = self.client.get(reverse('invoice_print', kwargs={'pk': inv.pk}))
        self.assertEqual(len(response.context['empty_rows']), 11)

    def test_invoice_delete_get(self):
        inv = make_invoice(self.seller, self.buyer)
        response = self.client.get(reverse('invoice_delete', kwargs={'pk': inv.pk}))
        self.assertEqual(response.status_code, 200)

    def test_invoice_delete_post(self):
        inv = make_invoice(self.seller, self.buyer)
        self.client.post(reverse('invoice_delete', kwargs={'pk': inv.pk}))
        self.assertEqual(Invoice.objects.count(), 0)


class BuyerViewTest(TestCase):

    def test_buyer_list_200(self):
        response = self.client.get(reverse('buyer_list'))
        self.assertEqual(response.status_code, 200)

    def test_buyer_new_get(self):
        response = self.client.get(reverse('buyer_new'))
        self.assertEqual(response.status_code, 200)

    def test_buyer_new_post_creates_buyer(self):
        self.client.post(reverse('buyer_new'), {
            'name': '김철수',
            'has_delivery_fee': 'on',
            'has_deduction': '',
            'notes': '메모',
        })
        self.assertTrue(Buyer.objects.filter(name='김철수').exists())

    def test_buyer_new_post_empty_name_fails(self):
        self.client.post(reverse('buyer_new'), {'name': ''})
        self.assertEqual(Buyer.objects.count(), 0)

    def test_buyer_edit_get(self):
        buyer = make_buyer()
        response = self.client.get(reverse('buyer_edit', kwargs={'pk': buyer.pk}))
        self.assertEqual(response.status_code, 200)

    def test_buyer_edit_post_updates_name(self):
        buyer = make_buyer()
        self.client.post(reverse('buyer_edit', kwargs={'pk': buyer.pk}), {
            'name': '수정된이름',
            'has_delivery_fee': '',
            'has_deduction': '',
            'notes': '',
        })
        buyer.refresh_from_db()
        self.assertEqual(buyer.name, '수정된이름')


class SellerViewTest(TestCase):

    def test_settings_view_200(self):
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 200)

    def test_seller_new_get(self):
        response = self.client.get(reverse('seller_new'))
        self.assertEqual(response.status_code, 200)

    def test_seller_new_post_creates_seller(self):
        self.client.post(reverse('seller_new'), {
            'company_name': '새 상회',
            'address': '부산시 1-1',
            'phone': '051-1111-2222',
            'bank_account': '우리은행 111-222',
            'fax': '',
            'is_default': 'on',
        })
        self.assertTrue(SellerProfile.objects.filter(company_name='새 상회').exists())

    def test_seller_edit_post_updates(self):
        seller = make_seller()
        self.client.post(reverse('seller_edit', kwargs={'pk': seller.pk}), {
            'company_name': '수정 상회',
            'address': '서울',
            'phone': '02-9999-0000',
            'bank_account': '신한 999',
            'fax': '',
            'is_default': 'on',
        })
        seller.refresh_from_db()
        self.assertEqual(seller.company_name, '수정 상회')


class AjaxViewTest(TestCase):

    def test_buyer_balance_no_invoices(self):
        buyer = make_buyer()
        response = self.client.get(reverse('buyer_balance', kwargs={'pk': buyer.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['previous_balance'], 0)

    def test_buyer_balance_with_invoice(self):
        seller = make_seller()
        buyer = make_buyer()
        inv = make_invoice(
            seller, buyer,
            items=[{'name': '사과', 'qty': 5, 'boxes': 2, 'price': 1000}],
        )
        response = self.client.get(reverse('buyer_balance', kwargs={'pk': buyer.pk}))
        self.assertEqual(response.json()['previous_balance'], int(inv.current_balance))

    def test_buyer_balance_404(self):
        response = self.client.get(reverse('buyer_balance', kwargs={'pk': 9999}))
        self.assertEqual(response.status_code, 404)
