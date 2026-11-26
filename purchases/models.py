from django.db import models
from django.conf import settings
from suppliers.models import Supplier
from materials.models import Material, Unit
from core.models import Currency
from inventory.models import LocationInventory

class OrderStatus(models.Model):

    name = models.CharField(max_length=200, verbose_name="Nombre")
    symbol = models.CharField(max_length=100, blank=True, verbose_name="Símbolo")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Estado de orden de compra"
        verbose_name_plural = "Estados de orden de compra"

    def __str__(self):
        return self.symbol

class PurchaseOrder(models.Model):
    id_purchase_order = models.CharField(max_length=10, verbose_name="ID orden de compra")
    id_supplier = models.ForeignKey(Supplier, default=1, on_delete=models.PROTECT,verbose_name="Proveedor")
    issue_date = models.DateField(auto_now_add=True)
    estimated_delivery_date = models.DateField(verbose_name="Fecha estimada de entrega")
    status = models.ForeignKey(OrderStatus, default=1, on_delete=models.PROTECT, verbose_name="Estado")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Orden de compra"
        verbose_name_plural = "Órdenes de compra"

    def __str__(self):
        return self.id_purchase_order

class LinesPurchaseOrder(models.Model):
    id_purchase_order_line = models.CharField(max_length=10, verbose_name="ID línea de orden de compra")
    id_purchase_order = models.ForeignKey(PurchaseOrder, default=1, on_delete=models.PROTECT,verbose_name="Orden de compra")
    id_material = models.ForeignKey(Material, default=1, on_delete=models.PROTECT,verbose_name="Material", related_name="id_material_1")
    position = models.IntegerField(default=1,verbose_name="Posición")
    quantity = models.IntegerField(default=0,verbose_name="Cantidad")
    unit_material = models.ForeignKey(Unit, on_delete=models.PROTECT,verbose_name="Unidad")
    price = models.FloatField(verbose_name="Precio")
    currency_supplier = models.ForeignKey(Currency, on_delete=models.PROTECT,verbose_name="Moneda")
    received_quantity = models.IntegerField(verbose_name="Cantidad recibida")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Línea de orden de compra"
        verbose_name_plural = "Líneas de órdenes de compra"

    def __str__(self):
        return self.id_purchase_order_line

class GoodsReceiptStatus(models.Model):

    name = models.CharField(max_length=200, verbose_name="Nombre")
    symbol = models.CharField(max_length=100, blank=True, verbose_name="Símbolo")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Estado de recepción"
        verbose_name_plural = "Estado de recepción"

    def __str__(self):
        return self.symbol

class GoodsReceipt(models.Model):

    id_goods_receipt = models.CharField(max_length=10, verbose_name='ID recepción')
    id_purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, verbose_name="ID orden de compra")
    receipt_date = models.DateField(verbose_name='Fecha de recepción')
    supplier_delivery_note = models.CharField(max_length=50, blank=True, null=True, verbose_name="Fecha estimada de entrega")

    status = models.ForeignKey(GoodsReceiptStatus, default=1, on_delete=models.PROTECT, verbose_name="Estado")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Recepción de mercancía"
        verbose_name_plural = "Recepciones de mercancía"

    def __str__(self):
        return self.id_goods_receipt

class LinesGoodsReceipt(models.Model):

    id_goods_receipt_line = models.CharField(max_length=10, verbose_name="ID línea de recepción")
    id_goods_receipt = models.ForeignKey(GoodsReceipt, default=1, on_delete=models.PROTECT,verbose_name="Recepción de mercancía", related_name='lines')
    id_purchase_order_line = models.ForeignKey(LinesPurchaseOrder, on_delete=models.PROTECT,verbose_name="Línea de orden de compra")
    id_material = models.ForeignKey(Material, default=1, on_delete=models.PROTECT,verbose_name="Material")
    received_quantity = models.IntegerField(verbose_name="Cantidad recibida")
    unit_material = models.ForeignKey(Unit, on_delete=models.PROTECT,verbose_name="Unidad")
    id_location = models.ForeignKey(LocationInventory, on_delete=models.PROTECT,verbose_name="Bodega destino")
    inventory_movement_ref = models.CharField(max_length=10,blank=True,null=True, verbose_name="ID movimiento de inventario")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Línea de recepción"
        verbose_name_plural = "Líneas de recepciones"

    def __str__(self):
        return self.id_goods_receipt_line

class InvoiceStatus(models.Model):

    name = models.CharField(max_length=200, verbose_name="Nombre")
    symbol = models.CharField(max_length=100, blank=True, verbose_name="Símbolo")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Estado de factura"
        verbose_name_plural = "Estado de factura"

    def __str__(self):
        return self.symbol

class PurchaseInvoice(models.Model):

    id_invoice = models.CharField(max_length=10, verbose_name='ID factura de compra')
    id_purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, verbose_name="Orden de compra (ref.)")

    invoice_date = models.DateField(auto_now_add=True, verbose_name='Fecha de factura')
    due_date = models.DateField(verbose_name='Fecha de vencimiento')
    total_amount = models.FloatField(verbose_name='Valor total', default=0.0)
    currency_invoice = models.ForeignKey(Currency, on_delete=models.PROTECT, verbose_name='Moneda')

    status = models.ForeignKey(InvoiceStatus, default=1, on_delete=models.PROTECT, verbose_name="Estado")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Factura de compra"
        verbose_name_plural = "Facturas de compra"

    def __str__(self):
        return self.id_invoice


class LinesPurchaseInvoice(models.Model):

    id_invoice_line = models.CharField(max_length=10, verbose_name="ID línea de factura")
    id_purchase_invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.PROTECT,verbose_name="Factura de compra", related_name='lines')
    id_purchase_order_line = models.ForeignKey(LinesPurchaseOrder, on_delete=models.PROTECT,verbose_name="Línea de orden de compra")
    price = models.FloatField(verbose_name="Precio unitario")
    currency_invoice_line = models.ForeignKey(Currency, on_delete=models.PROTECT,verbose_name="Moneda")
    quantity = models.IntegerField(verbose_name="Cantidad facturada")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Línea de factura de compra"
        verbose_name_plural = "Líneas de facturas de compra"

    def __str__(self):
        return self.id_invoice_line