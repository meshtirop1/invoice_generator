from django.db import models
from django.utils import timezone


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

    def __str__(self):
        return f"{self.buyer.name} - {self.date}"

    def calculate_total_amount(self):
        return sum(item.amount for item in self.invoiceitem_set.all())

    def calculate_current_balance(self):
        total = self.calculate_total_amount()
        return total + self.delivery_fee - self.deduction - self.payment_received + self.previous_balance

    def save(self, *args, **kwargs):
        if not self.pk:
            last = self.buyer.get_last_invoice()
            self.previous_balance = last.current_balance if last else 0
            self.current_balance = 0
        super().save(*args, **kwargs)

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