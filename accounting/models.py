from django.db import models
from django.conf import settings
from core.models import Currency, Country, Status

class AccountNature(models.Model):
    id_account_nature = models.CharField(verbose_name="ID naturaleza", max_length=10, primary_key=True)
    name = models.CharField(verbose_name="Nombre", max_length=50)
    symbol = models.CharField(verbose_name="Símbolo", max_length=10)
    effect_on_balance = models.TextField(verbose_name="Efecto en el saldo")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Naturaleza de la cuenta"
        verbose_name_plural = "Naturalezas de cuenta"

    def __str__(self):
        return self.name

class AccountGroup(models.Model):
    id_account_group = models.CharField(verbose_name="ID grupo de cuentas", max_length=10, primary_key=True)
    name = models.CharField(verbose_name="Nombre", max_length=100)
    code_prefix = models.CharField(verbose_name="Prefijo de código", max_length=10)
    description = models.TextField(verbose_name="Descripción")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Grupo de cuentas"
        verbose_name_plural = "Grupos de cuentas"

    def __str__(self):
        return self.name

class AccountType(models.Model):
    id_account_type = models.CharField(verbose_name="ID tipo de cuenta", max_length=10, primary_key=True)
    name = models.CharField(verbose_name="Nombre", max_length=50)
    description = models.TextField(verbose_name="Descripción",blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Tipo de cuenta"
        verbose_name_plural = "Tipos de cuenta"

    def __str__(self):
        return self.name

class AccountAccount(models.Model):
    id_account = models.CharField(verbose_name="ID cuenta", max_length=10, primary_key=True)
    name = models.CharField(verbose_name="Nombre", max_length=100)
    code = models.CharField(verbose_name="Código", max_length=20)
    description = models.TextField(verbose_name="Descripción",blank=True)
    account_type = models.ForeignKey(AccountType, verbose_name="Tipo de cuenta", on_delete=models.PROTECT)
    account_group = models.ForeignKey(AccountGroup, verbose_name="Grupo de cuentas", on_delete=models.PROTECT)
    nature = models.ForeignKey(AccountNature, verbose_name="Naturaleza de la cuenta", on_delete=models.PROTECT)
    currency_id = models.ForeignKey(Currency, verbose_name="ID moneda", on_delete=models.PROTECT)
    country_id = models.ForeignKey(Country, verbose_name="ID país", on_delete=models.PROTECT)
    is_control_account = models.BooleanField(verbose_name="¿Cuenta de control?", default=False)
    parent_account = models.ForeignKey('self',verbose_name="Cuenta padre", on_delete=models.SET_NULL, null=True, blank= True)

    status = models.ForeignKey(Status,default=1,on_delete=models.PROTECT,verbose_name="Estado")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Cuenta contable"
        verbose_name_plural = "Cuentas contables"

    def __str__(self):
        return f"{self.code} - {self.name}"

class Journal(models.Model):

    id_journal = models.CharField(verbose_name='ID asiento', max_length= 10, primary_key=True)
    group_journal = models.CharField(verbose_name='ID grupo de asiento', max_length=10)
    reference = models.CharField(verbose_name='Referencia',max_length=100)
    id_account = models.ForeignKey(AccountAccount, verbose_name = 'ID cuenta', on_delete=models.PROTECT)
    credit = models.FloatField(verbose_name='Crédito',default=0.0)
    debit = models.FloatField(verbose_name='Débito', default=0.0)
    currency = models.ForeignKey(Currency, verbose_name= 'Moneda', on_delete=models.PROTECT)

    cost_center = models.ForeignKey('CostCenter', verbose_name='Centro de costo', on_delete=models.PROTECT, null=True, blank=True)
    description = models.TextField(verbose_name='Descripción', blank=True)

    status = models.ForeignKey(Status,default=1,on_delete=models.PROTECT,verbose_name="Estado")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name="Asiento contable"
        verbose_name_plural = "Asientos contables"

    def __str__(self):
        return self.id_journal


class CostCenter(models.Model):
    id_cost_center = models.CharField(verbose_name="ID centro de costo", max_length=10, primary_key=True)
    name = models.CharField(verbose_name="Nombre", max_length=100)
    description = models.TextField(verbose_name="Descripción", blank=True)

    status = models.ForeignKey(Status, default=1, on_delete=models.PROTECT, verbose_name="Estado")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Centro de costo"
        verbose_name_plural = "Centros de costo"

    def __str__(self):
        return f"{self.id_cost_center} - {self.name}"

