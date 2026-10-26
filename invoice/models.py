import contextlib
import re
import threading
import unicodedata

from decimal import ROUND_HALF_UP, Decimal

from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone


# ─── Item cells: text that may or may not be a number ────────
#
# 수량 / 박스 / 단가 / 금액 are stored exactly as typed, so a cell can say '10kg', '3박스' or
# '시가' as well as '1,000'. number_in() reads the number out of a cell when it is one.

_NUMBER = re.compile(r'-?\d+(\.\d+)?')
_IGNORED = (',', '₩', '\\', '원', ' ')   # '\\' is how a Korean keyboard types ₩


def number_in(text):
    """The number a cell holds — '1,000', '₩1,000', '1000원', '2.5' — or None for anything
    else ('시가', '10kg', blank)."""
    if text is None:
        return None
    if isinstance(text, (int, Decimal)):
        return Decimal(text)
    value = unicodedata.normalize('NFKC', str(text))   # full-width digits and ￦ → plain
    for mark in _IGNORED:
        value = value.replace(mark, '')
    return Decimal(value) if _NUMBER.fullmatch(value) else None


def whole_won(amount):
    """An amount as plain whole won, e.g. Decimal('99.9') → '100'."""
    return str(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


# ─── Recalculation control ───────────────────────────────────
# The running-balance chain is recomputed automatically whenever an invoice or
# an item changes, so the admin, the shell and the views can never leave a
# buyer's balances stale. Bulk operations wrap themselves in suppress_recalc()
# and call recalculate_balances() once at the end instead of once per row.

_local = threading.local()


@contextlib.contextmanager
def suppress_recalc():
    """Temporarily stop the signal handlers from recomputing the chain."""
    previous = getattr(_local, 'suppressed', False)
    _local.suppressed = True
    try:
        yield
    finally:
        _local.suppressed = previous


def _recalc_enabled():
    return not getattr(_local, 'suppressed', False)


def recalculate_balances(buyer):
    """
    Recompute current balances while preserving each invoice's manual previous balance.

    Still needed because an invoice's own total changes whenever its items do.
    Uses bulk_update, which does not emit signals, so it cannot recurse.
    """
    if buyer is None:
        return 0

    invoices = list(
        Invoice.objects
        .filter(buyer=buyer)
        .order_by('date', 'created_at', 'pk')
        .prefetch_related('invoiceitem_set')
    )

    for invoice in invoices:
        invoice.current_balance = invoice.calculate_current_balance()

    if invoices:
        Invoice.objects.bulk_update(invoices, ['current_balance'])
    return len(invoices)


class SellerProfile(models.Model):
    company_name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    bank_account = models.CharField(max_length=100)
    fax = models.CharField(max_length=50, blank=True, null=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.company_name

    def save(self, *args, **kwargs):
        if self.is_default:
            SellerProfile.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class Buyer(models.Model):
    name = models.CharField(max_length=100)
    has_delivery_fee = models.BooleanField(default=False)
    has_deduction = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_last_invoice(self):
        return self.invoice_set.order_by('-date', '-created_at').first()

    def get_current_balance(self):
        """
        Total still outstanding across this buyer's invoices.

        With independent invoices there is no single running balance, so the
        only meaningful per-buyer figure is the sum of what each invoice still
        has owing.
        """
        return sum(
            (inv.current_balance for inv in self.invoice_set.all()),
            Decimal('0'),
        )


class Invoice(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.PROTECT)
    buyer = models.ForeignKey(Buyer, on_delete=models.PROTECT)
    date = models.DateField(default=timezone.now)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0, blank=True)
    deduction = models.DecimalField(max_digits=12, decimal_places=0, default=0, blank=True)
    payment_received = models.DecimalField(max_digits=12, decimal_places=0, default=0, blank=True)
    previous_balance = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    current_balance = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    # Seller details are snapshotted per invoice: they are typed straight onto
    # the sheet, and a past invoice must keep the details it was issued with
    # even after the seller profile changes.
    seller_name = models.CharField(max_length=100, blank=True, default='')
    seller_address = models.CharField(max_length=255, blank=True, default='')
    seller_phone = models.CharField(max_length=50, blank=True, default='')
    seller_bank_account = models.CharField(max_length=100, blank=True, default='')
    seller_fax = models.CharField(max_length=50, blank=True, default='')

    def __str__(self):
        return f"{self.buyer.name} - {self.date}"

    def fill_seller_from_profile(self, profile):
        """Seed the snapshot fields from a SellerProfile, for a fresh invoice."""
        if profile is None:
            return
        self.seller_name = profile.company_name or ''
        self.seller_address = profile.address or ''
        self.seller_phone = profile.phone or ''
        self.seller_bank_account = profile.bank_account or ''
        self.seller_fax = profile.fax or ''

    def calculate_total_amount(self):
        """The items' amounts that are numbers; an amount written as text ('별도') adds nothing."""
        return sum((item.amount_value for item in self.invoiceitem_set.all()), Decimal('0'))

    def calculate_current_balance(self):
        """What this invoice still has owing, including its manual previous balance."""
        total = self.calculate_total_amount()
        return (
            self.previous_balance + total + self.delivery_fee
            - self.deduction - self.payment_received
        )

    class Meta:
        ordering = ['-date', '-created_at']


class InvoiceItem(models.Model):
    """One line of an invoice. 수량, 박스, 단가 and 금액 are text, kept exactly as typed.

    When quantity, boxes and unit price are all numbers, the amount is their product (in
    whole won), whatever was typed there. Otherwise the amount is whatever was typed — a
    number counts towards the invoice total, text ('별도') does not.
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=100)
    quantity = models.CharField(max_length=50, blank=True, default='')
    boxes = models.CharField(max_length=50, blank=True, default='')
    unit_price = models.CharField(max_length=50, blank=True, default='')
    amount = models.CharField(max_length=50, blank=True, default='')
    order = models.PositiveIntegerField(default=0)

    CELLS = ('quantity', 'boxes', 'unit_price', 'amount')

    def computed_amount(self):
        """quantity × boxes × unit_price when all three are numbers, else None."""
        numbers = [number_in(getattr(self, field)) for field in ('quantity', 'boxes', 'unit_price')]
        if None in numbers:
            return None
        quantity, boxes, unit_price = numbers
        return quantity * boxes * unit_price

    @property
    def amount_value(self):
        """What this line adds to the invoice total."""
        return number_in(self.amount) or Decimal('0')

    def save(self, *args, **kwargs):
        for field in self.CELLS:
            value = getattr(self, field)
            setattr(self, field, '' if value is None else str(value).strip()[:50])
        computed = self.computed_amount()
        if computed is not None:
            self.amount = whole_won(computed)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} ({self.invoice})"

    class Meta:
        ordering = ['order']


# ─── Signals: keep the balance chain correct, always ─────────

@receiver(post_save, sender=Invoice)
def _invoice_saved(sender, instance, **kwargs):
    if _recalc_enabled():
        recalculate_balances(instance.buyer)
        instance.refresh_from_db(fields=['previous_balance', 'current_balance'])


@receiver(post_delete, sender=Invoice)
def _invoice_deleted(sender, instance, **kwargs):
    if _recalc_enabled():
        recalculate_balances(instance.buyer)


@receiver(post_save, sender=InvoiceItem)
@receiver(post_delete, sender=InvoiceItem)
def _item_changed(sender, instance, **kwargs):
    if not _recalc_enabled():
        return
    # During a cascading Invoice delete the parent row may already be gone.
    try:
        buyer = instance.invoice.buyer
    except Invoice.DoesNotExist:
        return
    recalculate_balances(buyer)
