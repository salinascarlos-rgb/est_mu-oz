from django.core.management.base import BaseCommand

from inventory.services import fill_missing_exchange_rates, sync_daily_stock


class Command(BaseCommand):
    help = 'Genera la foto diaria de existencias valorizada en la moneda base.'

    def add_arguments(self, parser):
        parser.add_argument('--full', action='store_true', help='Recalcula toda la historia desde el primer movimiento.')

    def handle(self, *args, **options):
        fixed = fill_missing_exchange_rates()
        rows = sync_daily_stock(full=options['full'] or bool(fixed))
        self.stdout.write(self.style.SUCCESS(
            f'Existencias sincronizadas. Movimientos con tasa corregida: {fixed}. Filas de foto escritas: {rows}.'
        ))
