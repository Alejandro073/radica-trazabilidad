from django import forms
from django.utils import timezone

from .models import CausalGlosa, EntidadPagadora, TipoServicio, TipoSoporte


class CuentaForm(forms.Form):
    paciente_documento = forms.CharField(label="Documento del paciente", max_length=20)
    paciente_nombre = forms.CharField(label="Nombre del paciente", max_length=150)
    tipo_servicio = forms.ChoiceField(label="Tipo de servicio", choices=TipoServicio.choices)
    entidad = forms.ModelChoiceField(
        label="Entidad responsable de pago", queryset=EntidadPagadora.objects.none()
    )
    fecha_ingreso = forms.DateField(
        label="Fecha de ingreso", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    valor = forms.DecimalField(label="Valor facturado (COP)", min_value=0, max_digits=14, decimal_places=0, initial=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["entidad"].queryset = EntidadPagadora.objects.filter(activa=True)
        self.fields["fecha_ingreso"].initial = timezone.localdate()

    def clean_fecha_ingreso(self):
        fecha = self.cleaned_data["fecha_ingreso"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de ingreso no puede ser futura.")
        return fecha


class SoporteForm(forms.Form):
    tipo = forms.ModelChoiceField(label="Tipo de soporte", queryset=TipoSoporte.objects.all())
    archivo = forms.FileField(label="Archivo (PDF, PNG o JPG, máx. 10 MB)")


class GlosaForm(forms.Form):
    causal = forms.ChoiceField(label="Causal", choices=CausalGlosa.choices)
    valor_glosado = forms.DecimalField(label="Valor glosado (COP)", min_value=0, max_digits=14, decimal_places=0)
    descripcion = forms.CharField(label="Descripción", max_length=500, required=False)


class RespuestaGlosaForm(forms.Form):
    respuesta = forms.CharField(label="Respuesta", max_length=500, widget=forms.Textarea(attrs={"rows": 2}))
