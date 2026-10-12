"""Administração dos campi cadastrados por professores."""
from django import forms
from django.contrib import admin
from django.utils import timezone

from .models import Instituicao


class InstituicaoAdminForm(forms.ModelForm):
    latitude = forms.FloatField(required=False, min_value=-90, max_value=90)
    longitude = forms.FloatField(required=False, min_value=-180, max_value=180)
    radius_meters = forms.IntegerField(label='Raio permitido (metros)', min_value=1, max_value=10000)

    class Meta:
        model = Instituicao
        fields = '__all__'

    def clean(self):
        data = super().clean()
        if (data.get('latitude') is None) != (data.get('longitude') is None):
            raise forms.ValidationError('Informe latitude e longitude juntas, ou deixe ambas vazias para manter a localização pendente.')
        return data


@admin.register(Instituicao)
class InstituicaoAdmin(admin.ModelAdmin):
    form = InstituicaoAdminForm
    list_display = ('nome', 'cidade', 'estado', 'localizacao_confirmada', 'ativa')
    list_filter = ('ativa', 'estado')
    search_fields = ('nome', 'cidade')
    readonly_fields = ('geocodificada_em', 'geocoding_source', 'created_at')

    @admin.display(boolean=True, description='Localização confirmada')
    def localizacao_confirmada(self, obj):
        return obj.latitude is not None and obj.longitude is not None

    def save_model(self, request, obj, form, change):
        if not change or {'latitude', 'longitude'} & set(form.changed_data):
            confirmed = self.localizacao_confirmada(obj)
            obj.geocodificada_em = timezone.now() if confirmed else None
            obj.geocoding_source = 'confirmacao_manual_admin' if confirmed else ''
        super().save_model(request, obj, form, change)
