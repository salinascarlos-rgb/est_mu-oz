from datetime import date
from decimal import Decimal

from django.db import models
from django.conf import settings
from core.models import Status, Currency
from accounting.models import CostCenter
from materials.models import Material,Unit

class MovementType(models.Model):

    DIRECTION_IN = 1
    DIRECTION_OUT = -1
    DIRECTION_CHOICES = [
        (DIRECTION_IN, 'Entrada (+)'),
        (DIRECTION_OUT, 'Salida (-)'),
    ]

    name = models.CharField(verbose_name="Nombre",max_length=50)
    symbol = models.CharField(verbose_name="Símbolo",max_length=10)
    # +1 suma al inventario, -1 resta. Las cantidades se guardan siempre positivas.
    direction = models.IntegerField(verbose_name="Dirección", choices=DIRECTION_CHOICES, default=DIRECTION_IN)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Tipo de movimiento"
        verbose_name_plural = "Tipos de movimiento"

    def __str__(self):
        return f"{self.symbol} - {self.name}"

class LocationInventory(models.Model):

    id_location = models.CharField(verbose_name="ID bodega", max_length=10, primary_key=True)
    name = models.CharField(verbose_name="Nombre", max_length=100)
    code = models.CharField(verbose_name="Código", max_length=20)
    main_location = models.BooleanField(verbose_name="Bodega principal", default=False)
    location = models.TextField(verbose_name="Dirección", blank=True)

    status = models.ForeignKey(Status,default=1,on_delete=models.PROTECT,verbose_name="Estado")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Bodega"
        verbose_name_plural = "Bodegas"

    def __str__(self):
        return f"{self.code} - {self.name}"

class InventoryMovements(models.Model):

    id_inventory_movement = models.CharField(verbose_name="ID movimiento de inventario", max_length=10, primary_key=True)
    id_location = models.ForeignKey(LocationInventory, on_delete=models.PROTECT, verbose_name="ID bodega")
    id_material = models.ForeignKey(Material, on_delete=models.PROTECT, verbose_name="ID material")
    quantity = models.IntegerField(verbose_name="Cantidad")
    unit_type = models.ForeignKey(Unit, on_delete=models.PROTECT, verbose_name="Unidad")

    price = models.FloatField(verbose_name='Precio',default=0.0)
    currency = models.ForeignKey(Currency,on_delete=models.PROTECT,verbose_name='Moneda')
    # Unidades de `currency` por 1 unidad de la moneda base (settings.BASE_CURRENCY)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal('1.0'), verbose_name='Tasa de cambio')

    movement_type = models.ForeignKey(MovementType, on_delete=models.PROTECT, verbose_name="Tipo de movimiento")
    reference = models.CharField(verbose_name="Referencia", max_length=100, blank=True, default='')
    cost_center = models.ForeignKey(CostCenter, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Centro de costo")
    description = models.TextField(verbose_name="Descripción", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Movimiento de inventario"
        verbose_name_plural = "Movimientos de inventario"

    def __str__(self):
        return f"{self.id_material} - {self.quantity} - {self.unit_type}"


class Stock(models.Model):
    """
    Foto diaria del inventario por bodega y material, valorizada en la moneda
    base (USD por defecto). La llena inventory.services.sync_daily_stock().
    """
    id_location = models.ForeignKey(LocationInventory, on_delete=models.CASCADE, verbose_name="Bodega")
    id_material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Material")
    date = models.DateField(verbose_name='Fecha', default=date.today)
    quantity = models.IntegerField(verbose_name="Cantidad", default=0)
    unit_type = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Unidad")
    # Cantidad comprometida en órdenes de venta abiertas (video 18)
    reserved_quantity = models.IntegerField(verbose_name="Cantidad reservada", default=0)

    avg_price_usd = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal('0'), verbose_name="Precio promedio (moneda base)")
    total_value_usd = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal('0'), verbose_name="Valor total (moneda base)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Existencia diaria"
        verbose_name_plural = "Existencias diarias"
        unique_together = ('date', 'id_location', 'id_material')
        ordering = ['-date', 'id_location', 'id_material']

    def save(self, *args, **kwargs):
        self.total_value_usd = (Decimal(str(self.quantity)) * Decimal(str(self.avg_price_usd))).quantize(Decimal('0.0001'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} - {self.id_location} - {self.id_material}: {self.quantity}"
