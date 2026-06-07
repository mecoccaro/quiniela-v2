from django import forms

from .models import User


class RegistrationForm(forms.ModelForm):
    invite_code = forms.CharField(
        max_length=5,
        required=False,
        label="Código de invitación (opcional)",
    )
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["email", "nickname", "first_name", "last_name"]
        labels = {
            "email": "Email",
            "nickname": "Apodo",
            "first_name": "Nombre",
            "last_name": "Apellido",
        }

    def clean_invite_code(self) -> str:
        code = self.cleaned_data.get("invite_code", "").strip().upper()
        if code:
            from apps.pools.models import Pool
            if not Pool.objects.filter(invite_code=code).exists():
                raise forms.ValidationError("Código de invitación no válido.")
        return code

    def clean_password2(self) -> str:
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return p2  # type: ignore[return-value]

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class PasswordRecoveryForm(forms.Form):
    email = forms.EmailField(label="Email")
    nickname = forms.CharField(max_length=50, label="Apodo")


class SetNewPasswordForm(forms.Form):
    password1 = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)

    def clean_password2(self) -> str:
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return p2  # type: ignore[return-value]
