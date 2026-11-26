"""
Tasas de cambio: descarga, guardado y consulta.

Fuentes:
  - Frankfurter (api.frankfurter.dev), igual que en el curso. Usa datos del
    Banco Central Europeo, que NO incluyen el peso colombiano (COP).
  - TRM oficial de Colombia (datos.gov.co, dataset 32sa-8pi3) para el COP.

Convención (igual que el curso): `rate` = unidades de la moneda por 1 unidad
de la moneda base. Con base USD: COP 3592.03 => 1 USD = 3.592,03 COP.
Para pasar un precio a la moneda base: precio / rate.
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

from .models import Currency, ExchangeRate

logger = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.dev/v1"
TRM_URL = "https://www.datos.gov.co/resource/32sa-8pi3.json"
TIMEOUT = 10
# Si no hay ninguna tasa guardada, se descargan los últimos N días
INITIAL_DAYS = 120
FRANKFURTER_CURRENCIES = {
    'AUD', 'BRL', 'CAD', 'CHF', 'CNY', 'CZK', 'DKK', 'EUR', 'GBP', 'HKD', 'HUF', 'IDR', 'ILS', 'INR', 'ISK',
    'JPY', 'KRW', 'MXN', 'MYR', 'NOK', 'NZD', 'PHP', 'PLN', 'RON', 'SEK', 'SGD', 'THB', 'TRY', 'USD', 'ZAR',
}


def base_currency_code():
    return getattr(settings, 'BASE_CURRENCY', 'USD').upper()


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------

def fetch_frankfurter(start, end, base, symbols):
    """Devuelve {fecha: {código: tasa}} para las monedas soportadas por Frankfurter."""
    symbols = sorted(set(symbols) & FRANKFURTER_CURRENCIES - {base})
    if not symbols or base not in FRANKFURTER_CURRENCIES:
        return {}

    url = f"{FRANKFURTER_URL}/{start.isoformat()}..{end.isoformat()}"
    response = requests.get(url, params={'base': base, 'symbols': ','.join(symbols)}, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    rates = data.get('rates', {})
    # Rango: {"2026-01-20": {"EUR": 0.9}}. Un solo día: {"EUR": 0.9} con "date" aparte.
    if rates and not isinstance(next(iter(rates.values())), dict):
        rates = {data.get('date', end.isoformat()): rates}

    result = {}
    for day, day_rates in rates.items():
        parsed_day = date.fromisoformat(day)
        result[parsed_day] = {code: _to_decimal(value) for code, value in day_rates.items()}
    return result


def fetch_trm(start, end):
    """TRM oficial: devuelve {fecha: COP por 1 USD} usando la fecha de inicio de vigencia."""
    params = {
        '$where': f"vigenciadesde between '{start.isoformat()}T00:00:00' and '{end.isoformat()}T23:59:59'",
        '$order': 'vigenciadesde ASC',
        '$limit': 1000,
    }
    response = requests.get(TRM_URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()

    result = {}
    for row in response.json():
        value = _to_decimal(row.get('valor'))
        since = row.get('vigenciadesde')
        if value and since:
            result[datetime.fromisoformat(since[:10]).date()] = value
    return result


def update_exchange_rates(today=None):
    """
    Descarga las tasas que faltan desde la última fecha guardada hasta hoy,
    para las monedas registradas en la tabla Currency. Devuelve cuántas guardó.
    """
    today = today or date.today()
    base = base_currency_code()

    codes = set(Currency.objects.exclude(symbol__iexact=base).values_list('symbol', flat=True))
    codes = {code.upper() for code in codes}
    if not codes:
        return 0

    last = ExchangeRate.objects.order_by('-date').first()
    start = (last.date + timedelta(days=1)) if last else today - timedelta(days=INITIAL_DAYS)
    if start > today:
        return 0

    collected = {}   # {(código, fecha): tasa}

    try:
        for day, day_rates in fetch_frankfurter(start, today, base, codes).items():
            for code, value in day_rates.items():
                if value:
                    collected[(code, day)] = value
    except (requests.RequestException, ValueError) as e:
        logger.warning("Frankfurter: could not download exchange rates: %s", e)

    # El peso colombiano viene de la TRM (COP por USD)
    needs_trm = ('COP' in codes and base == 'USD') or (base == 'COP' and 'USD' in codes)
    if needs_trm:
        try:
            for day, trm in fetch_trm(start, today).items():
                if base == 'USD':
                    collected[('COP', day)] = trm
                else:  # base COP: cuántos USD vale 1 COP
                    collected[('USD', day)] = (Decimal('1') / trm).quantize(Decimal('0.000001'))
        except (requests.RequestException, ValueError) as e:
            logger.warning("TRM: could not download COP exchange rate: %s", e)

    currencies = {c.symbol.upper(): c for c in Currency.objects.all()}
    saved = 0
    for (code, day), value in collected.items():
        currency = currencies.get(code)
        if currency is None:
            continue
        _, created = ExchangeRate.objects.update_or_create(
            currency=currency, date=day, defaults={'rate': value}
        )
        saved += created
    return saved


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------

def get_rate(currency, on_date=None):
    """
    Tasa de `currency` frente a la moneda base en `on_date` (o la última
    anterior, que cubre fines de semana y festivos). La moneda base vale 1.
    Devuelve None si no hay ninguna tasa registrada para esa moneda.
    """
    if currency is None:
        return None
    if currency.symbol.upper() == base_currency_code():
        return Decimal('1')

    on_date = on_date or date.today()
    rates = ExchangeRate.objects.filter(currency=currency)
    rate = rates.filter(date__lte=on_date).order_by('-date').first()
    if rate is None:
        # Fecha anterior a la primera tasa guardada: se usa la más antigua disponible
        rate = rates.order_by('date').first()
    return rate.rate if rate else None


def require_rate(currency, on_date=None):
    """Como get_rate, pero lanza ValueError con instrucciones si no hay tasa."""
    rate = get_rate(currency, on_date)
    if rate is None:
        raise ValueError(
            f"No exchange rate found for {currency.symbol} against {base_currency_code()}. "
            f"Run 'python manage.py update_exchange_rates' or add one in the admin (Core > Exchange Rates)."
        )
    return rate
