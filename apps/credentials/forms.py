from django import forms

from .platforms import get_credential_fields, has_required_credentials


class PlatformCredentialForm(forms.Form):
    """Dynamic form for one platform's app credentials."""

    is_enabled = forms.BooleanField(
        required=False,
        label="Enable platform",
    )

    def __init__(self, platform, *args, existing_credentials=None, **kwargs):
        self.platform = platform
        self.existing_credentials = existing_credentials or {}
        super().__init__(*args, **kwargs)

        for name, label, is_secret in get_credential_fields(platform):
            existing_value = self.existing_credentials.get(name, "")
            widget = forms.PasswordInput if is_secret else forms.TextInput
            attrs = {
                "class": (
                    "w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm "
                    "text-stone-900 outline-none focus:border-orange-300 focus:ring-2 focus:ring-orange-100"
                ),
                "placeholder": "Leave blank to keep existing value" if existing_value else "",
            }
            if not is_secret and existing_value:
                attrs["value"] = existing_value

            self.fields[name] = forms.CharField(
                label=label,
                required=False,
                widget=widget(attrs=attrs),
            )

        self.fields["is_enabled"].widget.attrs.update(
            {
                "class": "h-4 w-4 rounded border-stone-300 text-orange-600 focus:ring-orange-500",
            }
        )

    def clean(self):
        cleaned = super().clean()
        merged = self.merged_credentials(cleaned)

        if cleaned.get("is_enabled") and not has_required_credentials(self.platform, merged):
            raise forms.ValidationError("Add the required credentials before enabling this platform.")

        return cleaned

    def merged_credentials(self, cleaned_data=None):
        """Merge posted values over existing credentials, preserving blanks."""
        cleaned_data = cleaned_data or self.cleaned_data
        credentials = dict(self.existing_credentials)

        for name, _label, _is_secret in get_credential_fields(self.platform):
            value = (cleaned_data.get(name) or "").strip()
            if value:
                credentials[name] = value

        return credentials
