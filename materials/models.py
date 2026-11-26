from django.db import models
from django.conf import settings
from core.models import Status

class Unit(models.Model):

    name = models.CharField(max_length=50, unique=True, verbose_name='Nombre de la unidad')
    symbol = models.CharField(max_length=10, unique=True, verbose_name='Símbolo')

    class Meta:
        verbose_name = "Unidad"
        verbose_name_plural = "Unidades"

    def __str__(self):
        return f"{self.name} ({self.symbol})"

class MaterialType(models.Model):

    name = models.CharField(max_length=50, unique=True, verbose_name='Nombre del tipo de material')
    symbol = models.CharField(max_length=10, unique=True, verbose_name='Símbolo')

    class Meta:
            verbose_name = "Tipo de material"
            verbose_name_plural = "Tipos de material"
    
    def __str__(self):
        return f"{self.name} ({self.symbol})"

# Create your models here.
class Material(models.Model):

    id_material = models.CharField(max_length=50, null= True, unique=True,verbose_name="ID material")
    name = models.CharField(max_length=100, verbose_name="Nombre")
    description = models.TextField(max_length=250,blank=True,verbose_name="Descripción")
    unit = models.ForeignKey(Unit, default=1, on_delete=models.PROTECT, verbose_name="Unidad de medida")
    material_type = models.ForeignKey(MaterialType, default=1, on_delete=models.PROTECT, verbose_name="Tipo de material")
    status = models.ForeignKey(Status, default=1, on_delete=models.PROTECT, verbose_name="Estado")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete= models.SET_NULL, null= True)
    
    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materiales"

    def __str__(self):
        return self.id_material