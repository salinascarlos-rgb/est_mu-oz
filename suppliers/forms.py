from django import forms
from .models import Supplier

SELECT_CLASSES = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#233b6e]'

class SupplierForm(forms.ModelForm):

    class Meta:
        model = Supplier
        fields = ['id_supplier', 'legal_name', 'name', 'tax_id', 'country', 'state_province', 'city', 'address', 'zip_code', 'phone', 'email', 'contact_name', 'contact_role',
                  'category', 'payment_terms', 'currency', 'payment_method', 'bank_account', 'status']
        widgets = {
            'country': forms.Select(attrs={'class': SELECT_CLASSES}),
            'currency': forms.Select(attrs={'class': SELECT_CLASSES}),
        }

class CsvUploadForm(forms.Form):
    csv_file=forms.FileField(
        label='Supplier CSV File',
        help_text='The file must contain headers that match the model fields.'
    )