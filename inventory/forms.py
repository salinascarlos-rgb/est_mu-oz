from django import forms

from materials.models import Material
from accounting.models import CostCenter
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


class InventoryMovementForm(StyledForm):
    """Formulario "New Movement Entry" del video 17."""
    movement_type = forms.ModelChoiceField(queryset=MovementType.objects.none(), label='Tipo de movimiento')
    material = forms.ModelChoiceField(queryset=active_materials(), label='Material')
    location = forms.ModelChoiceField(queryset=active_locations(), label='Bodega')
    quantity = forms.IntegerField(label='Cantidad', min_value=1)
    cost_center = forms.ModelChoiceField(queryset=CostCenter.objects.none(), label='Centro de costo', required=False)
    description = forms.CharField(
        label='Descripción', required=False, max_length=500,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Motivo o detalle del movimiento'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Imports aquí para evitar import circular con services
        from .services import MANUAL_MOVEMENT_TYPES
        self.fields['movement_type'].queryset = MovementType.objects.filter(symbol__in=MANUAL_MOVEMENT_TYPES).order_by('direction', 'symbol')
        self.fields['movement_type'].label_from_instance = lambda mt: f"{mt.symbol} - {mt.name}"
        self.fields['material'].queryset = active_materials()
        self.fields['location'].queryset = active_locations()
        self.fields['cost_center'].queryset = CostCenter.objects.filter(status__is_active=True).order_by('id_cost_center')

    def clean(self):
        from .services import COST_CENTER_REQUIRED
        cleaned = super().clean()
        movement_type = cleaned.get('movement_type')
        if movement_type and movement_type.symbol in COST_CENTER_REQUIRED and not cleaned.get('cost_center'):
            self.add_error('cost_center', 'El centro de costo es obligatorio para uso interno.')
        if movement_type and movement_type.symbol in ('LOSS', 'ADJ_IN', 'ADJ_OUT') and not cleaned.get('description'):
            self.add_error('description', 'Describa el motivo de este movimiento.')
        return cleaned


class TransferForm(StyledForm):
    material = forms.ModelChoiceField(queryset=active_materials(), label='Material')
    origin = forms.ModelChoiceField(queryset=active_locations(), label='Bodega origen')
    destination = forms.ModelChoiceField(queryset=active_locations(), label='Bodega destino')
    quantity = forms.IntegerField(label='Cantidad', min_value=1)
    notes = forms.CharField(label='Notas', max_length=60, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = active_materials()
        self.fields['origin'].queryset = active_locations()
        self.fields['destination'].queryset = active_locations()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('origin') and cleaned.get('origin') == cleaned.get('destination'):
            raise forms.ValidationError('La bodega de origen y la de destino deben ser distintas.')
        return cleaned
