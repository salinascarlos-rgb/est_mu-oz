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

    def __str__(self):
        return self.name


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name