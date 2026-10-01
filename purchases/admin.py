from django.contrib import admin
from .models import OrderStatus, GoodsReceiptStatus, InvoiceStatus, PurchaseInvoice, LinesPurchaseInvoice

@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol')

@admin.register(GoodsReceiptStatus)
class GoodsReceiptStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol')

@admin.register(InvoiceStatus)
class InvoiceStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol')

@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ('id_invoice', 'id_purchase_order', 'invoice_date', 'due_date', 'total_amount', 'currency_invoice', 'status', 'created_at', 'updated_at', 'created_by')

@admin.register(LinesPurchaseInvoice)
class LinePurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ('id_purchase_invoice', 'id_purchase_order_line', 'price', 'currency_invoice_line', 'quantity', 'created_at', 'updated_at', 'created_by')