"""Shared URL checks for browser automation."""
from urllib.parse import urlparse

VIEW_PROFILE_URL = "https://www.dentalcare.com/en-us/user-account/view-profile"


def is_view_profile_url(url: str) -> bool:
    if not url:
        return False
    try:
        path = (urlparse(url).path or "").rstrip("/")
        return path.endswith("/user-account/view-profile")
    except Exception:
        return "view-profile" in url
