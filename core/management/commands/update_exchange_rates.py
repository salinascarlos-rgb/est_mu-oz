from django.core.management.base import BaseCommand

from core.exchange_rates import update_exchange_rates, base_currency_code


class Command(BaseCommand):
    help = 'Descarga las tasas de cambio que faltan (Frankfurter + TRM oficial para COP).'

    def handle(self, *args, **options):
        saved = update_exchange_rates()
        self.stdout.write(self.style.SUCCESS(
            f'Tasas de cambio actualizadas frente a {base_currency_code()}. Registros nuevos: {saved}.'
        ))
