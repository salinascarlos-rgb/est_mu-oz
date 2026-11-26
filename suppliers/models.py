from django.db import models
from django.conf import settings
from core.models import Country, Currency

# Create your models here.
class Supplier(models.Model):

    id_supplier = models.CharField(max_length=50, unique=True,verbose_name="ID proveedor")
    legal_name = models.CharField(max_length=150, blank=True, verbose_name="Razón social")
    name = models.CharField(max_length=100, verbose_name="Nombre")
    tax_id = models.CharField(max_length=30, verbose_name="NIT")
    country = models.ForeignKey(Country, on_delete=models.PROTECT, verbose_name="País", null=True, blank=True)
    state_province = models.CharField(max_length=60, verbose_name="Departamento")
    city = models.CharField(max_length=100, verbose_name="Ciudad")
    address = models.CharField(max_length=150, verbose_name="Dirección")
    zip_code = models.IntegerField(verbose_name="Código postal")
    phone = models.IntegerField(verbose_name="Teléfono")
    email = models.EmailField(max_length=150, verbose_name="Correo")
    contact_name = models.CharField(max_length=150, verbose_name="Nombre de contacto")
    contact_role = models.CharField(max_length=150, verbose_name="Cargo del contacto")
    category = models.CharField(max_length=150,verbose_name="Categoría")
    payment_terms = models.CharField(max_length=150,verbose_name="Plazo de pago")
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, verbose_name="Moneda", null=True, blank=True)
    payment_method = models.CharField(max_length=150, verbose_name="Medio de pago")
    bank_account = models.CharField(max_length=150, verbose_name="Cuenta bancaria")

    status = models.CharField(max_length=50, verbose_name="Estado")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete= models.SET_NULL, null= True)
    
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

    def __str__(self):
        return self.name
