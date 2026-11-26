from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from .exchange_rates import update_exchange_rates, get_rate, require_rate
from .models import Currency, ExchangeRate


def fake_response(payload):
    response = mock.Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@override_settings(BASE_CURRENCY='USD')
class ExchangeRateTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.usd = Currency.objects.create(name='Dólar', symbol='USD')
        cls.cop = Currency.objects.create(name='Peso Colombiano', symbol='COP')
        cls.eur = Currency.objects.create(name='Euro', symbol='EUR')

    def fake_get(self, url, params=None, timeout=None):
        if 'frankfurter' in url:
            return fake_response({
                'base': 'USD',
                'rates': {'2026-11-24': {'EUR': 0.95}, '2026-11-25': {'EUR': 0.96}},
            })
        if 'datos.gov.co' in url:
            return fake_response([
                {'valor': '3505.92', 'vigenciadesde': '2026-11-24T00:00:00.000'},
                {'valor': '3592.03', 'vigenciadesde': '2026-11-25T00:00:00.000'},
            ])
        raise AssertionError(url)

    def test_downloads_frankfurter_and_trm_for_cop(self):
        with mock.patch('core.exchange_rates.requests.get', side_effect=self.fake_get) as get:
            saved = update_exchange_rates(today=date(2026, 11, 25))
        self.assertEqual(saved, 4)
        # Frankfurter no recibe COP: se pide aparte a la TRM
        frankfurter_call = next(c for c in get.call_args_list if 'frankfurter' in c.args[0])
        self.assertEqual(frankfurter_call.kwargs['params']['symbols'], 'EUR')
        self.assertEqual(get_rate(self.cop, date(2026, 11, 25)), Decimal('3592.03'))
        self.assertEqual(get_rate(self.eur, date(2026, 11, 24)), Decimal('0.95'))

    def test_weekend_uses_previous_rate_and_base_is_one(self):
        ExchangeRate.objects.create(currency=self.cop, date=date(2026, 11, 21), rate=Decimal('3461.92'))
        self.assertEqual(get_rate(self.cop, date(2026, 11, 23)), Decimal('3461.92'))
        self.assertEqual(get_rate(self.usd), Decimal('1'))

    def test_second_run_only_downloads_missing_days(self):
        ExchangeRate.objects.create(currency=self.cop, date=date(2026, 11, 25), rate=Decimal('3592.03'))
        with mock.patch('core.exchange_rates.requests.get') as get:
            self.assertEqual(update_exchange_rates(today=date(2026, 11, 25)), 0)
        get.assert_not_called()

    def test_network_error_does_not_crash(self):
        import requests
        with mock.patch('core.exchange_rates.requests.get', side_effect=requests.ConnectionError('offline')):
            self.assertEqual(update_exchange_rates(today=date(2026, 11, 25)), 0)

    def test_require_rate_explains_what_to_do(self):
        with self.assertRaisesMessage(ValueError, 'update_exchange_rates'):
            require_rate(self.eur)
