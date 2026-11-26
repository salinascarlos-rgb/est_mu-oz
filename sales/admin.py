from django.contrib import admin
from .models import SalesOrderStatus, SalesOrder, LinesSalesOrder


@admin.register(SalesOrderStatus)
class SalesOrderStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol')


class LinesSalesOrderInline(admin.TabularInline):
    model = LinesSalesOrder
    extra = 0


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('id_sales_order', 'id_customer', 'issue_date', 'estimated_delivery_date', 'status', 'created_by')
    list_filter = ('status',)
    inlines = [LinesSalesOrderInline]


@admin.register(LinesSalesOrder)
class LinesSalesOrderAdmin(admin.ModelAdmin):
    list_display = ('id_sales_order_line', 'id_sales_order', 'id_material', 'id_location', 'quantity',
                    'price', 'wac', 'margin', 'currency', 'shipped_quantity')
