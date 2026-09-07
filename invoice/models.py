import contextlib
import threading

from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone


# ─── Recalculation control ───────────────────────────────────
# The running-balance chain is recomputed automatically whenever an invoice or
# an item changes, so the admin, the shell and the views can never leave a
# buyer's balances stale. Bulk operations wrap themselves in suppress_recalc()
# and call recalculate_chain() once at the end instead of once per row.

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


def recalculate_chain(buyer):
    """
    Recompute previous_balance / current_balance for every invoice of a buyer,
    walking them oldest-first so each invoice carries the running total forward.

    Safe to call at any time; it is the single source of truth for balances.
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

    running = 0
    for invoice in invoices:
        invoice.previous_balance = running
        invoice.current_balance = invoice.calculate_current_balance()
        running = invoice.current_balance

    if invoices:
        Invoice.objects.bulk_update(
            invoices, ['previous_balance', 'current_balance']
        )
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
        last = self.get_last_invoice()
        return last.current_balance if last else 0


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
        return sum(item.amount for item in self.invoiceitem_set.all())

    def calculate_current_balance(self):
        total = self.calculate_total_amount()
        return total + self.delivery_fee - self.deduction - self.payment_received + self.previous_balance

    class Meta:
        ordering = ['-date', '-created_at']


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=100)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    boxes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    order = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        # amount = quantity × boxes × unit_price
        self.amount = self.quantity * self.boxes * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} ({self.invoice})"

    class Meta:
        ordering = ['order']


# ─── Signals: keep the balance chain correct, always ─────────

@receiver(post_save, sender=Invoice)
def _invoice_saved(sender, instance, **kwargs):
    if _recalc_enabled():
        recalculate_chain(instance.buyer)
        instance.refresh_from_db(fields=['previous_balance', 'current_balance'])


@receiver(post_delete, sender=Invoice)
def _invoice_deleted(sender, instance, **kwargs):
    if _recalc_enabled():
        recalculate_chain(instance.buyer)


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
    recalculate_chain(buyer)
