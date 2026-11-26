from django.core.management.base import BaseCommand

from core.exchange_rates import update_exchange_rates, base_currency_code


class Command(BaseCommand):
    help = 'Downloads missing exchange rates (Frankfurter + official TRM for COP).'

    def handle(self, *args, **options):
        saved = update_exchange_rates()
        self.stdout.write(self.style.SUCCESS(
            f'Exchange rates updated against {base_currency_code()}. New records: {saved}.'
        ))
