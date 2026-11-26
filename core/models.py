from django.db import models

class Status(models.Model):

    name = models.CharField(max_length=50, unique=True, verbose_name='Status Name')
    is_active = models.BooleanField(default=True, verbose_name='Is Active?')

    class Meta:
            verbose_name = "Status"
            verbose_name_plural = "Statuses"
    
    def __str__(self):
        return self.name
    

class Currency(models.Model):
    name = models.CharField(max_length=50, unique=True)
    symbol = models.CharField(max_length=10, unique=True, verbose_name='Symbol')

    def __str__(self):
        return self.symbol


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class ExchangeRate(models.Model):
    """
    Tasa de cambio diaria: cuántas unidades de `currency` equivalen a 1 unidad
    de la moneda base (settings.BASE_CURRENCY, por defecto USD).
    Ejemplo con base USD: COP 3592.03 significa 1 USD = 3.592,03 COP.
    """
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='rates', verbose_name='Currency')
    date = models.DateField(verbose_name='Date')
    rate = models.DecimalField(max_digits=18, decimal_places=6, verbose_name='Rate')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Exchange Rate"
        verbose_name_plural = "Exchange Rates"
        unique_together = ('currency', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.currency.symbol} - {self.date} : {self.rate}"
