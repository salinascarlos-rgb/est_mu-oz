from django.db import models
from django.conf import settings

from core.models import Currency
from customers.models import Customer
from materials.models import Material, Unit
from inventory.models import LocationInventory


class SalesOrderStatus(models.Model):

    name = models.CharField(max_length=200, verbose_name="Name")
    symbol = models.CharField(max_length=100, blank=True, verbose_name="Symbol")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Sales Order Status"
        verbose_name_plural = "Sales Order Statuses"

    def __str__(self):
        return self.symbol


class SalesOrder(models.Model):

    id_sales_order = models.CharField(max_length=10, unique=True, verbose_name="ID Sales Order")
    id_customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name="Customer")
    issue_date = models.DateField(auto_now_add=True)
    estimated_delivery_date = models.DateField(verbose_name="Estimated delivery date")
    status = models.ForeignKey(SalesOrderStatus, on_delete=models.PROTECT, verbose_name="Status")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Sales Order"
        verbose_name_plural = "Sales Orders"
        ordering = ['-pk']

    def __str__(self):
        return self.id_sales_order

    @property
    def total_amount(self):
        return sum(line.quantity * line.price for line in self.lines.all())


class LinesSalesOrder(models.Model):

    id_sales_order_line = models.CharField(max_length=10, verbose_name="ID Sales Order Line")
    id_sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, verbose_name="Sales Order", related_name='lines')
    # related_name distinto al de compras ('id_material_1') para que Django no choque
    id_material = models.ForeignKey(Material, on_delete=models.PROTECT, verbose_name="Material", related_name='sales_lines')
    id_location = models.ForeignKey(LocationInventory, on_delete=models.PROTECT, verbose_name="Location")
    quantity = models.IntegerField(default=0, verbose_name="Quantity")
    unit_material = models.ForeignKey(Unit, on_delete=models.PROTECT, verbose_name="Unit")

    price = models.FloatField(verbose_name="Price")
    # Costo promedio en la MISMA moneda del precio, para que el margen tenga sentido
    wac = models.FloatField(verbose_name="WAC (Cost)", default=0.0)
    margin = models.FloatField(verbose_name="Margin (%)", default=0.0)

    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, verbose_name="Currency")

    shipped_quantity = models.IntegerField(default=0, verbose_name="Shipped Quantity")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Line Sales Order"
        verbose_name_plural = "Lines Sales Orders"

    def save(self, *args, **kwargs):
        if self.price and self.price > 0:
            self.margin = round(((self.price - self.wac) / self.price) * 100, 2)
        else:
            self.margin = 0.0
        super().save(*args, **kwargs)

    @property
    def pending_quantity(self):
        return self.quantity - self.shipped_quantity

    @property
    def line_total(self):
        return self.quantity * self.price

    def __str__(self):
        return self.id_sales_order_line
