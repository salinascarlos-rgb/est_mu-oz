import json
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from users.models import User, Role, UserRole
from core.models import Currency, Country
from suppliers.models import Supplier
from materials.models import Material, Unit
from inventory.models import LocationInventory, InventoryMovements
from accounting.models import Journal
from .models import PurchaseOrder, GoodsReceipt, PurchaseInvoice


class PurchaseFlowTests(TestCase):
    """Flujo completo: crear OC -> recepción parcial -> recepción total -> factura."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_data', verbosity=0)

        cls.user = User.objects.create_user(username='admin', password='pass12345')
        UserRole.objects.create(user_id=cls.user, role=Role.objects.get(role_name='Administrator'))

        cls.viewer = User.objects.create_user(username='viewer', password='pass12345')
        viewer_role = Role.objects.create(role_name='Viewer', purchases=1)
        UserRole.objects.create(user_id=cls.viewer, role=viewer_role)

        cop = Currency.objects.get(symbol='COP')
        cls.supplier = Supplier.objects.create(
            id_supplier='P001', name='Proveedor', tax_id='900', country=Country.objects.first(),
            state_province='Valle', city='Yumbo', address='Calle 1', zip_code=760001, phone=3000000,
            email='p@x.com', contact_name='Ana', contact_role='Ventas', category='MP',
            payment_terms='30', currency=cop, payment_method='Transfer', bank_account='123', status='Active',
        )
        cls.material = Material.objects.create(id_material='M001', name='Estuco', unit=Unit.objects.get(symbol='UND'))
        cls.location = LocationInventory.objects.create(id_location='L1', name='Bodega', code='B1')

    def setUp(self):
        self.client.force_login(self.user)

    def post_json(self, url_name, payload):
        return self.client.post(reverse(url_name), json.dumps(payload), content_type='application/json')

    def create_po(self, quantity=10, price=1000):
        return self.post_json('purchases:create_purchase_order', {
            'id_supplier': 'P001', 'estimated_delivery_date': '2026-12-31',
            'lines': [{'id_material': 'M001', 'unit_material': 'UND', 'currency_supplier': 'COP',
                       'quantity': quantity, 'price': price}],
        })

    def test_full_flow(self):
        r = self.create_po()
        self.assertEqual(r.status_code, 201, r.content)
        po = PurchaseOrder.objects.get()
        self.assertEqual(po.status.symbol, 'CONFIRMED')
        line = po.linespurchaseorder_set.get()

        r = self.post_json('purchases:post_goods_receipt', {
            'po_pk': po.pk, 'receipt_date': '2026-11-25',
            'lines': [{'line_pk': line.pk, 'received_quantity': 4, 'location_pk': self.location.pk}],
        })
        self.assertEqual(r.status_code, 200, r.content)
        po.refresh_from_db()
        self.assertEqual(po.status.symbol, 'PARTIAL_RECEIVED')

        r = self.post_json('purchases:post_goods_receipt', {
            'po_pk': po.pk, 'receipt_date': '2026-11-26',
            'lines': [{'line_pk': line.pk, 'received_quantity': 6, 'location_pk': self.location.pk}],
        })
        self.assertEqual(r.status_code, 200, r.content)
        po.refresh_from_db()
        self.assertEqual(po.status.symbol, 'RECEIVED')
        self.assertEqual(InventoryMovements.objects.count(), 2)

        r = self.post_json('purchases:post_purchase_invoice', {
            'po_pk': po.pk, 'due_date': '2026-12-31',
            'lines': [{'line_pk': line.pk, 'quantity_to_invoice': 10}],
        })
        self.assertEqual(r.status_code, 200, r.content)
        po.refresh_from_db()
        self.assertEqual(po.status.symbol, 'CLOSED')
        invoice = PurchaseInvoice.objects.get()
        self.assertEqual(invoice.total_amount, 10000)
        journals = Journal.objects.filter(group_journal=str(int(invoice.id_invoice)))
        self.assertEqual(sum(j.debit for j in journals), sum(j.credit for j in journals))

    def test_over_reception_rolls_back(self):
        self.create_po(quantity=5)
        po = PurchaseOrder.objects.get()
        line = po.linespurchaseorder_set.get()
        r = self.post_json('purchases:post_goods_receipt', {
            'po_pk': po.pk, 'receipt_date': '2026-11-25',
            'lines': [{'line_pk': line.pk, 'received_quantity': 9, 'location_pk': self.location.pk}],
        })
        self.assertEqual(r.status_code, 400)
        # No deben quedar recepciones ni movimientos a medias
        self.assertEqual(GoodsReceipt.objects.count(), 0)
        self.assertEqual(InventoryMovements.objects.count(), 0)

    def test_po_ids_keep_increasing_after_ten(self):
        for _ in range(11):
            self.assertEqual(self.create_po().status_code, 201)
        ids = sorted(int(x) for x in PurchaseOrder.objects.values_list('id_purchase_order', flat=True))
        self.assertEqual(ids, list(range(1, 12)))

    def test_invalid_material_does_not_leave_half_order(self):
        r = self.post_json('purchases:create_purchase_order', {
            'id_supplier': 'P001', 'estimated_delivery_date': '2026-12-31',
            'lines': [{'id_material': 'NOPE', 'unit_material': 'UND', 'currency_supplier': 'COP',
                       'quantity': 1, 'price': 1}],
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_view_only_user_cannot_create(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.create_po().status_code, 403)
        self.assertEqual(self.client.get(reverse('purchases:purchase_order_list')).status_code, 200)

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        r = self.client.get(reverse('dashboard'))
        self.assertRedirects(r, f"{reverse('login')}?next={reverse('dashboard')}")
