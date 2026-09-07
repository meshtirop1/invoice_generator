from django.contrib import admin
from .models import (
    SellerProfile, Buyer, Invoice, InvoiceItem, recalculate_chain,
)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 3


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['buyer', 'seller_name', 'date', 'previous_balance', 'current_balance', 'created_at']
    list_filter = ['buyer', 'seller', 'date']
    readonly_fields = ['previous_balance', 'current_balance']
    inlines = [InvoiceItemInline]

    def save_related(self, request, form, formsets, change):
        # Inline items are written after the Invoice row, so the balances have
        # to be recomputed once the items actually exist.
        super().save_related(request, form, formsets, change)
        recalculate_chain(form.instance.buyer)


@admin.register(Buyer)
class BuyerAdmin(admin.ModelAdmin):
    list_display = ['name', 'has_delivery_fee', 'has_deduction', 'created_at']


@admin.register(SellerProfile)
class SellerAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'phone', 'bank_account', 'is_default']


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'invoice', 'quantity', 'unit_price', 'amount']