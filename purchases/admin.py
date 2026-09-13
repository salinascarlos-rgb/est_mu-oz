from django.contrib import admin
from .models import OrderStatus, GoodsReceiptStatus

@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol')

@admin.register(GoodsReceiptStatus)
class GoodsReceiptStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol')