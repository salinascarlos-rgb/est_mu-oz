from django.db import models
from django.conf import settings

from core.models import Currency
from customers.models import Customer
from materials.models import Material, Unit
from inventory.models import LocationInventory


class SalesOrderStatus(models.Model):

    name = models.CharField(max_length=200, verbose_name="Nombre")
    symbol = models.CharField(max_length=100, blank=True, verbose_name="Símbolo")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Estado de orden de venta"
        verbose_name_plural = "Estados de orden de venta"

    def __str__(self):
        return self.symbol


class SalesOrder(models.Model):

    id_sales_order = models.CharField(max_length=10, unique=True, verbose_name="ID orden de venta")
    id_customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name="Cliente")
    issue_date = models.DateField(auto_now_add=True)
    estimated_delivery_date = models.DateField(verbose_name="Fecha estimada de entrega")
    status = models.ForeignKey(SalesOrderStatus, on_delete=models.PROTECT, verbose_name="Estado")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Orden de venta"
        verbose_name_plural = "Órdenes de venta"
        ordering = ['-pk']

    def __str__(self):
        return self.id_sales_order

    @property
    def total_amount(self):
        return sum(line.quantity * line.price for line in self.lines.all())


class LinesSalesOrder(models.Model):

    id_sales_order_line = models.CharField(max_length=10, verbose_name="ID línea de orden de venta")
    id_sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, verbose_name="Orden de venta", related_name='lines')
    # related_name distinto al de compras ('id_material_1') para que Django no choque
    id_material = models.ForeignKey(Material, on_delete=models.PROTECT, verbose_name="Material", related_name='sales_lines')
    id_location = models.ForeignKey(LocationInventory, on_delete=models.PROTECT, verbose_name="Bodega")
    quantity = models.IntegerField(default=0, verbose_name="Cantidad")
    unit_material = models.ForeignKey(Unit, on_delete=models.PROTECT, verbose_name="Unidad")

    price = models.FloatField(verbose_name="Precio")
    # Costo promedio en la MISMA moneda del precio, para que el margen tenga sentido
    wac = models.FloatField(verbose_name="Costo promedio", default=0.0)
    margin = models.FloatField(verbose_name="Margen (%)", default=0.0)

    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, verbose_name="Moneda")

    shipped_quantity = models.IntegerField(default=0, verbose_name="Cantidad despachada")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Línea de orden de venta"
        verbose_name_plural = "Líneas de órdenes de venta"

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
