from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Group

from .listados import FiltroForm

User = get_user_model()

ROLES = [('Administrador', 'Administrador'), ('Cajero', 'Cajero')]


class UsuarioForm(forms.ModelForm):
    rol = forms.ChoiceField(label='Rol', choices=ROLES)
    password1 = forms.CharField(
        label='Contraseña', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label='Repite la contraseña', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        labels = {
            'username': 'Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo electrónico',
            'is_active': 'Activo (puede iniciar sesión)',
        }
        help_texts = {'username': 'Con este nombre inicia sesión. Sin espacios.', 'is_active': ''}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Al editar, la contraseña se cambia desde su propia pantalla.
            del self.fields['password1']
            del self.fields['password2']
            grupo = self.instance.groups.filter(name__in=dict(ROLES)).first()
            if grupo:
                self.fields['rol'].initial = grupo.name

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return p2

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get('password2')
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error('password2', error)

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if 'password1' in self.fields:
            usuario.set_password(self.cleaned_data['password1'])
        usuario.is_staff = True
        if commit:
            usuario.save()
            otros = Group.objects.filter(name__in=dict(ROLES)).exclude(name=self.cleaned_data['rol'])
            usuario.groups.remove(*otros)
            usuario.groups.add(Group.objects.get_or_create(name=self.cleaned_data['rol'])[0])
        return usuario


class CambiarContrasenaForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Nueva contraseña'
        self.fields['new_password2'].label = 'Repite la nueva contraseña'


class UsuarioFilterForm(FiltroForm):
    q = forms.CharField(
        required=False, label='Buscar',
        widget=forms.TextInput(attrs={'placeholder': 'Usuario, nombre o correo'}),
    )
    rol = forms.ChoiceField(required=False, label='Rol', choices=[('', 'Todos')] + ROLES)
    estado = forms.ChoiceField(
        required=False, label='Estado',
        choices=[('', 'Todos'), ('activos', 'Activos'), ('inactivos', 'Inactivos')],
    )


class CorteCajaForm(FiltroForm):
    fecha = forms.DateField(
        label='Fecha', input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'data-fecha': '', 'autocomplete': 'off'}),
    )
    cajero = forms.ModelChoiceField(
        queryset=User.objects.filter(ventas__isnull=False).distinct().order_by('username'),
        required=False, label='Cajero', empty_label='Todos los cajeros',
    )
