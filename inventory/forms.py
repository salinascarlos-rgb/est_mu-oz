from django import forms

from materials.models import Material
from .models import LocationInventory, MovementType

INPUT_CLASS = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#233b6e]'


def active_locations():
    return LocationInventory.objects.filter(status__is_active=True).order_by('code')


def active_materials():
    return Material.objects.filter(status__is_active=True).order_by('id_material')


class StyledForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', INPUT_CLASS)


class AdjustmentForm(StyledForm):
    material = forms.ModelChoiceField(queryset=active_materials(), label='Material')
    location = forms.ModelChoiceField(queryset=active_locations(), label='Location')
    direction = forms.TypedChoiceField(
        label='Type',
        choices=[
            (MovementType.DIRECTION_IN, 'Entry (+) — add stock'),
            (MovementType.DIRECTION_OUT, 'Exit (-) — remove stock'),
        ],
        coerce=int,
    )
    quantity = forms.IntegerField(label='Quantity', min_value=1)
    reason = forms.CharField(
        label='Reason', max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Physical count, damaged bags, loss...'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Se recalculan en cada uso para ver bodegas/materiales recién creados
        self.fields['material'].queryset = active_materials()
        self.fields['location'].queryset = active_locations()


class TransferForm(StyledForm):
    material = forms.ModelChoiceField(queryset=active_materials(), label='Material')
    origin = forms.ModelChoiceField(queryset=active_locations(), label='From location')
    destination = forms.ModelChoiceField(queryset=active_locations(), label='To location')
    quantity = forms.IntegerField(label='Quantity', min_value=1)
    notes = forms.CharField(label='Notes', max_length=60, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = active_materials()
        self.fields['origin'].queryset = active_locations()
        self.fields['destination'].queryset = active_locations()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('origin') and cleaned.get('origin') == cleaned.get('destination'):
            raise forms.ValidationError('Origin and destination must be different.')
        return cleaned
