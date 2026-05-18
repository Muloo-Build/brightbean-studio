import pytest
from django.urls import reverse

from apps.credentials.forms import PlatformCredentialForm
from apps.credentials.models import PlatformCredential
from apps.credentials.platforms import has_required_credentials


@pytest.mark.django_db
class TestPlatformCredentialHelpers:
    def test_bluesky_and_mastodon_do_not_require_app_credentials(self):
        assert has_required_credentials(PlatformCredential.Platform.BLUESKY, {})
        assert has_required_credentials(PlatformCredential.Platform.MASTODON, {})

    def test_oauth_platforms_require_complete_credentials(self):
        assert not has_required_credentials(PlatformCredential.Platform.FACEBOOK, {"app_id": "id"})
        assert has_required_credentials(
            PlatformCredential.Platform.FACEBOOK,
            {"app_id": "id", "app_secret": "secret"},
        )


@pytest.mark.django_db
class TestCredentialsViews:
    def test_list_requires_authentication(self, client):
        response = client.get(reverse("credentials:list"))

        assert response.status_code == 302
        assert "/accounts/" in response.url

    def test_form_merges_posted_credentials(self):
        form = PlatformCredentialForm(
            PlatformCredential.Platform.FACEBOOK,
            data={
                "is_enabled": "on",
                "app_id": "meta-app",
                "app_secret": "meta-secret",
            },
        )

        assert form.is_valid()
        assert form.merged_credentials() == {"app_id": "meta-app", "app_secret": "meta-secret"}
