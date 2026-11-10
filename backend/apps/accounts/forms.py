from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

User = get_user_model()


class StyledMixin:
    """Adds GEIDA input classes and sensible autocomplete hints."""

    def style_fields(self):
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "checkbox")
                continue
            widget.attrs.setdefault("class", "input")
            if self.errors.get(name):
                widget.attrs["aria-invalid"] = "true"


class SignInForm(StyledMixin, AuthenticationForm):
    remember = forms.BooleanField(label="Keep me signed in", required=False, initial=True)

    error_messages = {
        "invalid_login": "That email and password don't match an account. Check them and try again.",
        "inactive": "This account isn't verified yet.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email or username"
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "autofocus": True, "placeholder": "name@isdb.org"})
        self.fields["password"].widget.attrs.update({"autocomplete": "current-password"})
        self.style_fields()


class RegisterForm(StyledMixin, UserCreationForm):
    first_name = forms.CharField(label="First name", max_length=150)
    last_name = forms.CharField(label="Last name", max_length=150)
    email = forms.EmailField(label="Work email")
    accept = forms.BooleanField(label="I agree to use GEIDA data for IsDB project work", required=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.update({"autocomplete": "given-name", "autofocus": True})
        self.fields["last_name"].widget.attrs.update({"autocomplete": "family-name"})
        self.fields["email"].widget.attrs.update({"autocomplete": "email", "placeholder": "name@isdb.org"})
        self.fields["password1"].label = "Password"
        self.fields["password1"].help_text = "At least 8 characters. Avoid common words and numbers only."
        self.fields["password2"].label = "Confirm password"
        self.fields["password2"].help_text = ""
        for f in ("password1", "password2"):
            self.fields[f].widget.attrs.update({"autocomplete": "new-password"})
        self.style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Sign in or reset your password.")
        return email

    def _post_clean(self):
        # Use the email as the username before Django validates the password.
        if self.cleaned_data.get("email"):
            self.instance.username = self.cleaned_data["email"]
        super()._post_clean()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.is_active = False  # activated after email verification
        if commit:
            user.save()
        return user


class VerifyForm(forms.Form):
    code = forms.RegexField(regex=r"^\d{6}$", max_length=6, error_messages={"invalid": "Enter the 6-digit code from the email."})


class ResetRequestForm(StyledMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Work email"
        self.fields["email"].widget.attrs.update({"autocomplete": "email", "autofocus": True, "placeholder": "name@isdb.org"})
        self.style_fields()


class NewPasswordForm(StyledMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "New password"
        self.fields["new_password1"].help_text = "At least 8 characters. Avoid common words and numbers only."
        self.fields["new_password2"].label = "Confirm new password"
        for f in ("new_password1", "new_password2"):
            self.fields[f].widget.attrs.update({"autocomplete": "new-password"})
        self.fields["new_password1"].widget.attrs["autofocus"] = True
        self.style_fields()
