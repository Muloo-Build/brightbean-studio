from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.members.decorators import require_org_role
from apps.members.models import OrgMembership

from .forms import PlatformCredentialForm
from .models import PlatformCredential
from .platforms import get_credential_fields, has_required_credentials, platform_note


def _require_org(request):
    if not request.org:
        raise PermissionDenied("Organization required.")
    return request.org


@login_required
@require_org_role(OrgMembership.OrgRole.ADMIN)
def credentials_list(request):
    org = _require_org(request)
    saved_credentials = {
        cred.platform: cred
        for cred in PlatformCredential.objects.for_org(org.id).order_by("platform")
    }
    env_credentials = getattr(settings, "PLATFORM_CREDENTIALS_FROM_ENV", {})

    platform_cards = []
    for value, label in PlatformCredential.Platform.choices:
        saved = saved_credentials.get(value)
        env_configured = has_required_credentials(value, env_credentials.get(value, {}))
        saved_configured = bool(saved and saved.is_configured)
        is_configured = saved_configured or env_configured

        if saved_configured:
            source = "Saved"
        elif env_configured:
            source = "Environment"
        else:
            source = "Not configured"

        platform_cards.append(
            {
                "value": value,
                "label": label,
                "saved": saved,
                "is_configured": is_configured,
                "source": source,
                "fields": get_credential_fields(value),
                "note": platform_note(value),
            }
        )

    return render(
        request,
        "credentials/list.html",
        {
            "platform_cards": platform_cards,
            "settings_active": "credentials",
        },
    )


@login_required
@require_org_role(OrgMembership.OrgRole.ADMIN)
@require_http_methods(["GET", "POST"])
def credential_edit(request, platform):
    org = _require_org(request)
    platform_labels = dict(PlatformCredential.Platform.choices)
    if platform not in platform_labels:
        raise PermissionDenied("Unknown platform.")

    credential = PlatformCredential.objects.for_org(org.id).filter(platform=platform).first()
    existing_credentials = credential.credentials if credential else {}
    env_configured = has_required_credentials(
        platform,
        getattr(settings, "PLATFORM_CREDENTIALS_FROM_ENV", {}).get(platform, {}),
    )

    if request.method == "POST":
        form = PlatformCredentialForm(platform, request.POST, existing_credentials=existing_credentials)
        if form.is_valid():
            is_enabled = form.cleaned_data.get("is_enabled", False)
            merged_credentials = form.merged_credentials()

            if credential is None:
                credential = PlatformCredential(organization=org, platform=platform)

            credential.credentials = merged_credentials
            credential.is_configured = is_enabled and has_required_credentials(platform, merged_credentials)
            credential.test_result = PlatformCredential.TestResult.UNTESTED
            credential.save()

            if credential.is_configured:
                messages.success(request, f"{platform_labels[platform]} credentials saved.")
            else:
                messages.success(request, f"{platform_labels[platform]} disabled for saved credentials.")
            return redirect("credentials:list")
    else:
        form = PlatformCredentialForm(
            platform,
            existing_credentials=existing_credentials,
            initial={"is_enabled": bool(credential and credential.is_configured) or env_configured},
        )

    return render(
        request,
        "credentials/edit.html",
        {
            "form": form,
            "platform": platform,
            "platform_label": platform_labels[platform],
            "fields": get_credential_fields(platform),
            "note": platform_note(platform),
            "env_configured": env_configured,
            "has_saved_credentials": bool(credential),
            "settings_active": "credentials",
        },
    )


@login_required
@require_org_role(OrgMembership.OrgRole.ADMIN)
@require_http_methods(["POST"])
def credential_disable(request, platform):
    org = _require_org(request)
    platform_labels = dict(PlatformCredential.Platform.choices)
    credential = get_object_or_404(PlatformCredential.objects.for_org(org.id), platform=platform)
    credential.is_configured = False
    credential.save(update_fields=["is_configured", "updated_at"])
    messages.success(request, f"{platform_labels.get(platform, platform)} disabled.")
    return redirect("credentials:list")
