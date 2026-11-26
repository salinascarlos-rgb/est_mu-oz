from django.core.management.base import BaseCommand

from inventory.services import fill_missing_exchange_rates, sync_daily_stock


class Command(BaseCommand):
    help = 'Builds the daily Stock snapshots valued in the base currency.'

    def add_arguments(self, parser):
        parser.add_argument('--full', action='store_true', help='Rebuild the whole history from the first movement.')

    def handle(self, *args, **options):
        fixed = fill_missing_exchange_rates()
        rows = sync_daily_stock(full=options['full'] or bool(fixed))
        self.stdout.write(self.style.SUCCESS(
            f'Stock synced. Movements with corrected exchange rate: {fixed}. Snapshot rows written: {rows}.'
        ))
