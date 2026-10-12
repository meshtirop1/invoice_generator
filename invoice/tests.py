"""
Comprehensive test suite for the Invoice application.
Run with: python manage.py test invoice --verbosity=2
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
import datetime

from .models import SellerProfile, Buyer, Invoice, InvoiceItem
from .views import SHEET_MIN_ROWS


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
    inv = Invoice(**defaults)
    inv.fill_seller_from_profile(defaults['seller'])
    inv.save()
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
        # An earlier invoice must not influence this one.
        make_invoice(
            self.seller, self.buyer,
            items=[{'name': '첫번째', 'qty': 1, 'boxes': 1, 'price': 3000}],
        )
        inv = make_invoice(
            self.seller, self.buyer,
            items=[{'name': '감', 'qty': 4, 'boxes': 2, 'price': 500}],  # 4000
            delivery_fee=1000,
            deduction=500,
            payment_received=2000,
        )
        # 4000 + 1000 - 500 - 2000 = 2500, with nothing carried in.
        self.assertEqual(inv.calculate_current_balance(), Decimal('2500'))

    def test_nothing_carries_over_from_the_previous_invoice(self):
        make_invoice(
            self.seller, self.buyer,
            items=[{'name': '사과', 'qty': 10, 'boxes': 1, 'price': 1000}],
        )
        inv2 = Invoice(
            seller=self.seller,
            buyer=self.buyer,
            date=datetime.date(2026, 6, 2),
        )
        inv2.save()
        inv2.refresh_from_db()
        self.assertEqual(inv2.previous_balance, Decimal('0'))
        self.assertEqual(inv2.current_balance, Decimal('0'))

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
        # Saving keeps him on the sheet so he can keep working / send it.
        self.assertRedirects(response, reverse('invoice_edit', kwargs={'pk': inv.pk}))

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

    def test_invoice_print_pads_the_grid(self):
        inv = make_invoice(
            self.seller, self.buyer,
            items=[{'name': '사과', 'qty': 1, 'boxes': 1, 'price': 1000}],
        )
        response = self.client.get(reverse('invoice_print', kwargs={'pk': inv.pk}))
        self.assertEqual(len(response.context['empty_rows']), SHEET_MIN_ROWS - 1)

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

    def test_buyer_balance_is_always_zero(self):
        seller = make_seller()
        buyer = make_buyer()
        make_invoice(
            seller, buyer,
            items=[{'name': '사과', 'qty': 5, 'boxes': 2, 'price': 1000}],
        )
        response = self.client.get(reverse('buyer_balance', kwargs={'pk': buyer.pk}))
        self.assertEqual(response.json()['previous_balance'], 0)

    def test_buyer_balance_404(self):
        response = self.client.get(reverse('buyer_balance', kwargs={'pk': 9999}))
        self.assertEqual(response.status_code, 404)


# ─── Invoices are independent ────────────────────────────────────────────────

class IndependentInvoiceTest(TestCase):
    """Each invoice stands alone: nothing carries between them, in any direction."""

    def setUp(self):
        self.seller = make_seller()
        self.buyer = make_buyer()
        self.i1 = make_invoice(
            self.seller, self.buyer, date=datetime.date(2026, 1, 1),
            items=[{'name': 'A', 'qty': 1, 'boxes': 1, 'price': 1000}],
        )
        self.i2 = make_invoice(
            self.seller, self.buyer, date=datetime.date(2026, 2, 1),
            items=[{'name': 'B', 'qty': 1, 'boxes': 1, 'price': 2000}],
        )
        self.i3 = make_invoice(
            self.seller, self.buyer, date=datetime.date(2026, 3, 1),
            items=[{'name': 'C', 'qty': 1, 'boxes': 1, 'price': 3000}],
        )

    def test_each_invoice_shows_only_its_own_total(self):
        for inv, own in [(self.i1, 1000), (self.i2, 2000), (self.i3, 3000)]:
            inv.refresh_from_db()
            self.assertEqual(inv.previous_balance, Decimal('0'))
            self.assertEqual(inv.current_balance, Decimal(own))

    def test_deleting_one_invoice_leaves_the_others_untouched(self):
        self.i2.delete()
        self.i1.refresh_from_db()
        self.i3.refresh_from_db()
        self.assertEqual(self.i1.current_balance, Decimal('1000'))
        self.assertEqual(self.i3.current_balance, Decimal('3000'))

    def test_deleting_via_the_view_leaves_the_others_untouched(self):
        self.client.post(reverse('invoice_delete', kwargs={'pk': self.i1.pk}))
        self.i2.refresh_from_db()
        self.i3.refresh_from_db()
        self.assertEqual(self.i2.current_balance, Decimal('2000'))
        self.assertEqual(self.i3.current_balance, Decimal('3000'))

    def test_editing_an_early_invoice_does_not_move_later_ones(self):
        self.client.post(reverse('invoice_edit', kwargs={'pk': self.i1.pk}), {
            'buyer': self.buyer.pk,
            'date': '2026-01-01',
            'delivery_fee': '0',
            'deduction': '0',
            'payment_received': '0',
            'seller_name': self.seller.company_name,
            'seller_address': '', 'seller_phone': '',
            'seller_bank_account': '', 'seller_fax': '',
            'product_name[]': ['A'],
            'quantity[]': ['1'],
            'boxes[]': ['1'],
            'unit_price[]': ['9000'],
        })
        self.i1.refresh_from_db()
        self.i3.refresh_from_db()
        self.assertEqual(self.i1.current_balance, Decimal('9000'))
        self.assertEqual(self.i3.previous_balance, Decimal('0'))
        self.assertEqual(self.i3.current_balance, Decimal('3000'))

    def test_changing_an_item_only_moves_its_own_invoice(self):
        item = self.i1.invoiceitem_set.first()
        item.unit_price = 5000
        item.save()
        self.i1.refresh_from_db()
        self.i3.refresh_from_db()
        self.assertEqual(self.i1.current_balance, Decimal('5000'))
        self.assertEqual(self.i3.current_balance, Decimal('3000'))

    def test_payment_reduces_only_that_invoice(self):
        self.i2.payment_received = 500
        self.i2.save()
        self.i2.refresh_from_db()
        self.i3.refresh_from_db()
        self.assertEqual(self.i2.current_balance, Decimal('1500'))
        self.assertEqual(self.i3.current_balance, Decimal('3000'))

    def test_adding_items_after_the_invoice_recalculates(self):
        """The admin writes the Invoice row first and its items second."""
        fresh = Invoice.objects.create(
            seller=self.seller, buyer=make_buyer(name='관리자테스트'),
            date=datetime.date(2026, 4, 1),
        )
        InvoiceItem.objects.create(
            invoice=fresh, product_name='D', quantity=2, boxes=1, unit_price=2500,
        )
        fresh.refresh_from_db()
        self.assertEqual(fresh.current_balance, Decimal('5000'))

    def test_buyer_total_is_the_sum_of_outstanding_invoices(self):
        self.assertEqual(self.buyer.get_current_balance(), Decimal('6000'))
        self.i2.payment_received = 2000      # settle #2 in full
        self.i2.save()
        self.assertEqual(self.buyer.get_current_balance(), Decimal('4000'))

    def test_buyer_total_with_no_invoices_is_zero(self):
        self.assertEqual(make_buyer(name='신규').get_current_balance(), Decimal('0'))


# ─── The editable sheet ───────────────────────────────────────────────────────

class InvoiceSheetTest(TestCase):

    def setUp(self):
        self.seller = make_seller()
        self.buyer = make_buyer()

    def _payload(self, **overrides):
        data = {
            'seller': self.seller.pk,
            'buyer': self.buyer.pk,
            'date': '2026-06-01',
            'delivery_fee': '0',
            'deduction': '0',
            'payment_received': '0',
            'product_name[]': ['사과'],
            'quantity[]': ['2'],
            'boxes[]': ['3'],
            'unit_price[]': ['1000'],
        }
        data.update(overrides)
        return data

    def test_new_sheet_renders(self):
        response = self.client.get(reverse('invoice_new'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'invoice_sheet.html')

    def test_edit_sheet_renders_with_values(self):
        inv = make_invoice(
            self.seller, self.buyer,
            items=[{'name': '고등어', 'qty': 4, 'boxes': 2, 'price': 3000}],
        )
        response = self.client.get(reverse('invoice_edit', kwargs={'pk': inv.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '고등어')

    def test_edit_sheet_404(self):
        response = self.client.get(reverse('invoice_edit', kwargs={'pk': 9999}))
        self.assertEqual(response.status_code, 404)

    def test_edit_replaces_items_rather_than_appending(self):
        inv = make_invoice(
            self.seller, self.buyer,
            items=[{'name': '옛품목', 'qty': 1, 'boxes': 1, 'price': 100}],
        )
        self.client.post(
            reverse('invoice_edit', kwargs={'pk': inv.pk}),
            self._payload(**{'product_name[]': ['새품목'], 'quantity[]': ['1'],
                             'boxes[]': ['1'], 'unit_price[]': ['500']}),
        )
        names = list(inv.invoiceitem_set.values_list('product_name', flat=True))
        self.assertEqual(names, ['새품목'])

    def test_decimal_quantity_is_preserved(self):
        self.client.post(reverse('invoice_new'), self._payload(**{
            'quantity[]': ['2.5'], 'boxes[]': ['2'], 'unit_price[]': ['1000'],
        }))
        item = InvoiceItem.objects.get()
        self.assertEqual(item.quantity, Decimal('2.5'))
        self.assertEqual(item.amount, Decimal('5000'))

    def test_ragged_post_arrays_do_not_crash(self):
        """A short quantity[] list used to raise IndexError and orphan the invoice."""
        response = self.client.post(reverse('invoice_new'), self._payload(**{
            'product_name[]': ['사과', '배', '감'],
            'quantity[]': ['1'],
            'boxes[]': ['1'],
            'unit_price[]': ['1000'],
        }))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(InvoiceItem.objects.count(), 3)

    def test_missing_buyer_saves_nothing(self):
        response = self.client.post(reverse('invoice_new'), self._payload(buyer=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Invoice.objects.count(), 0)

    def test_comma_formatted_money_is_accepted(self):
        self.client.post(reverse('invoice_new'), self._payload(
            payment_received='1,500',
            **{'unit_price[]': ['2,000']},
        ))
        inv = Invoice.objects.get()
        self.assertEqual(inv.payment_received, Decimal('1500'))
        self.assertEqual(inv.invoiceitem_set.get().unit_price, Decimal('2000'))


# ─── Print / share output ─────────────────────────────────────────────────────

class InvoiceOutputTest(TestCase):

    def setUp(self):
        self.seller = make_seller()
        self.buyer = make_buyer()

    def test_print_does_not_drop_items_past_twelve(self):
        items = [{'name': '품목%02d' % i, 'qty': 1, 'boxes': 1, 'price': 100}
                 for i in range(20)]
        inv = make_invoice(self.seller, self.buyer, items=items)
        response = self.client.get(reverse('invoice_print', kwargs={'pk': inv.pk}))
        self.assertEqual(len(response.context['empty_rows']), 0)
        for i in range(20):
            self.assertContains(response, '품목%02d' % i)

    def test_share_page_renders(self):
        inv = make_invoice(
            self.seller, self.buyer,
            items=[{'name': '오징어', 'qty': 2, 'boxes': 1, 'price': 4000}],
        )
        response = self.client.get(reverse('invoice_share', kwargs={'pk': inv.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'invoice_share.html')
        self.assertContains(response, '오징어')
        self.assertContains(response, '홍길동')

    def test_share_page_404(self):
        response = self.client.get(reverse('invoice_share', kwargs={'pk': 9999}))
        self.assertEqual(response.status_code, 404)


# ─── AJAX buyer lookup ───────────────────────────────────────────────────────

class BuyerLookupTest(TestCase):

    def test_balance_is_zero_even_with_prior_invoices(self):
        seller = make_seller()
        buyer = make_buyer()
        make_invoice(
            seller, buyer, date=datetime.date(2026, 1, 1),
            items=[{'name': 'A', 'qty': 1, 'boxes': 1, 'price': 1000}],
        )
        make_invoice(
            seller, buyer, date=datetime.date(2026, 2, 1),
            items=[{'name': 'B', 'qty': 1, 'boxes': 1, 'price': 2000}],
        )
        url = reverse('buyer_balance', kwargs={'pk': buyer.pk})
        self.assertEqual(self.client.get(url).json()['previous_balance'], 0)

    def test_balance_response_carries_buyer_flags(self):
        buyer = make_buyer(has_delivery_fee=True, has_deduction=False)
        response = self.client.get(reverse('buyer_balance', kwargs={'pk': buyer.pk}))
        self.assertTrue(response.json()['has_delivery_fee'])
        self.assertFalse(response.json()['has_deduction'])
