"""Platform credential metadata shared by credential and connect views."""

from .models import PlatformCredential

NO_APP_CREDENTIAL_PLATFORMS = {
    PlatformCredential.Platform.BLUESKY,
    PlatformCredential.Platform.MASTODON,
}

PLATFORM_CREDENTIAL_FIELDS = {
    PlatformCredential.Platform.FACEBOOK: [
        ("app_id", "App ID", False),
        ("app_secret", "App Secret", True),
    ],
    PlatformCredential.Platform.INSTAGRAM: [
        ("app_id", "App ID", False),
        ("app_secret", "App Secret", True),
    ],
    PlatformCredential.Platform.THREADS: [
        ("app_id", "App ID", False),
        ("app_secret", "App Secret", True),
    ],
    PlatformCredential.Platform.INSTAGRAM_LOGIN: [
        ("app_id", "Instagram App ID", False),
        ("app_secret", "Instagram App Secret", True),
    ],
    PlatformCredential.Platform.LINKEDIN_PERSONAL: [
        ("client_id", "Client ID", False),
        ("client_secret", "Client Secret", True),
    ],
    PlatformCredential.Platform.LINKEDIN_COMPANY: [
        ("client_id", "Client ID", False),
        ("client_secret", "Client Secret", True),
    ],
    PlatformCredential.Platform.TIKTOK: [
        ("client_key", "Client Key", False),
        ("client_secret", "Client Secret", True),
    ],
    PlatformCredential.Platform.YOUTUBE: [
        ("client_id", "Client ID", False),
        ("client_secret", "Client Secret", True),
    ],
    PlatformCredential.Platform.GOOGLE_BUSINESS: [
        ("client_id", "Client ID", False),
        ("client_secret", "Client Secret", True),
    ],
    PlatformCredential.Platform.PINTEREST: [
        ("app_id", "App ID", False),
        ("app_secret", "App Secret", True),
    ],
}

PLATFORM_NOTES = {
    PlatformCredential.Platform.FACEBOOK: "Facebook, Instagram, and Threads can share the same Meta app credentials.",
    PlatformCredential.Platform.INSTAGRAM: "Facebook, Instagram, and Threads can share the same Meta app credentials.",
    PlatformCredential.Platform.THREADS: "Facebook, Instagram, and Threads can share the same Meta app credentials.",
    PlatformCredential.Platform.LINKEDIN_PERSONAL: (
        "LinkedIn Personal and Company Page can share one Community Management API app."
    ),
    PlatformCredential.Platform.LINKEDIN_COMPANY: (
        "LinkedIn Personal and Company Page can share one Community Management API app."
    ),
    PlatformCredential.Platform.YOUTUBE: "YouTube and Google Business Profile can share one Google OAuth client.",
    PlatformCredential.Platform.GOOGLE_BUSINESS: "YouTube and Google Business Profile can share one Google OAuth client.",
    PlatformCredential.Platform.BLUESKY: "No platform app credentials are required. Clients connect with a Bluesky app password.",
    PlatformCredential.Platform.MASTODON: "No platform app credentials are required. BrightBean registers per Mastodon instance.",
}


def get_credential_fields(platform):
    """Return field metadata for a platform."""
    return PLATFORM_CREDENTIAL_FIELDS.get(platform, [])


def has_required_credentials(platform, credentials):
    """Whether a platform has enough app credentials to start connection flows."""
    if platform in NO_APP_CREDENTIAL_PLATFORMS:
        return True

    fields = get_credential_fields(platform)
    if not fields:
        return False

    return all(credentials.get(name) for name, _label, _secret in fields)


def platform_note(platform):
    """Short note shown in the credential admin UI."""
    return PLATFORM_NOTES.get(platform, "")
