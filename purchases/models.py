from django.db import models
from django.conf import settings
from suppliers.models import Supplier
from materials.models import Material, Unit
from core.models import Currency
from inventory.models import LocationInventory

class OrderStatus(models.Model):

    name = models.CharField(max_length=200, verbose_name="Name")
    symbol = models.CharField(max_length=100, blank=True, verbose_name="Symbol")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Order Status"
        verbose_name_plural = "Order Statuses"

    def __str__(self):
        return self.symbol

class PurchaseOrder(models.Model):
    id_purchase_order = models.CharField(max_length=10, verbose_name="ID Purchase Order")
    id_supplier = models.ForeignKey(Supplier, default=1, on_delete=models.PROTECT,verbose_name="Supplier")
    issue_date = models.DateField(auto_now_add=True)
    estimated_delivery_date = models.DateField(verbose_name="Estimated delivery date")
    status = models.ForeignKey(OrderStatus, default=1, on_delete=models.PROTECT, verbose_name="Status")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Purchase Order"
        verbose_name_plural = "Purchase Orders"

    def __str__(self):
        return self.id_purchase_order

class LinesPurchaseOrder(models.Model):
    id_purchase_order_line = models.CharField(max_length=10, verbose_name="ID Purchase Order Line")
    id_puechase_order = models.ForeignKey(PurchaseOrder, default=1, on_delete=models.PROTECT,verbose_name="Purchase Order")
    id_material = models.ForeignKey(Material, default=1, on_delete=models.PROTECT,verbose_name="Material", related_name="id_material_1")
    position = models.IntegerField(default=1,verbose_name="Position")
    quantity = models.IntegerField(default=0,verbose_name="Quantity")
    unit_material = models.ForeignKey(Unit, on_delete=models.PROTECT,verbose_name="Unit")
    price = models.FloatField(verbose_name="Price")
    currency_supplier = models.ForeignKey(Currency, on_delete=models.PROTECT,verbose_name="Currency")
    received_quantity = models.IntegerField(verbose_name="Received Quantity")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Line Purchase Order"
        verbose_name_plural = "Lines Purchase Orders"

    def __str__(self):
        return self.id_purchase_order_line

class GoodsReceiptStatus(models.Model):

    name = models.CharField(max_length=200, verbose_name="Name")
    symbol = models.CharField(max_length=100, blank=True, verbose_name="Symbol")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Goods Receipt Status"
        verbose_name_plural = "Goods Receipt Status"

    def __str__(self):
        return self.symbol

class GoodsReceipt(models.Model):

    id_goods_receipt = models.CharField(max_length=10, verbose_name='ID Goods Receipt')
    id_purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, verbose_name="ID Purchase Order")
    receipt_date = models.DateField(verbose_name='Receipt Date')
    supplier_delivery_note = models.CharField(max_length=50, blank=True, null=True, verbose_name="Estimated delivery date")

    status = models.ForeignKey(GoodsReceiptStatus, default=1, on_delete=models.PROTECT, verbose_name="Status")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Goods Receipt"
        verbose_name_plural = "Goods Receipts"

    def __str__(self):
        return self.id_goods_receipt

class LinesGoodsReceipt(models.Model):

    id_goods_receipt_line = models.CharField(max_length=10, verbose_name="ID Goods Receipt Line")
    id_goods_recipt = models.ForeignKey(GoodsReceipt, default=1, on_delete=models.PROTECT,verbose_name="Goods Receipt", related_name='lines')
    id_purchase_order_line = models.ForeignKey(LinesPurchaseOrder, on_delete=models.PROTECT,verbose_name="Purchase Order Line")
    id_material = models.ForeignKey(Material, default=1, on_delete=models.PROTECT,verbose_name="Material")
    received_quantity = models.IntegerField(verbose_name="Received Quantity")
    unit_material = models.ForeignKey(Unit, on_delete=models.PROTECT,verbose_name="Unit")
    id_location = models.ForeignKey(LocationInventory, on_delete=models.PROTECT,verbose_name="Destination Location")
    inventory_movement_ref = models.CharField(max_length=10,blank=True,null=True, verbose_name="Inventory Movement ID")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Line Goods Receipt"
        verbose_name_plural = "Lines Goods Receipts"

    def __str__(self):
        return self.id_goods_receipt_line