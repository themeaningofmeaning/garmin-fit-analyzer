"""
Ultra State — GitHub Auto-Updater (Option A: Notification Only)

Strategy: On app startup, fetch the latest release tag from the public GitHub
Releases API. If the remote version is newer than APP_VERSION, show a NiceGUI
toast notification prompting the user to download the update manually.

No files are downloaded or replaced automatically — this keeps the update
mechanism simple, transparent, and safe. Upgrade to a silent installer flow
(Option B) only once the component architecture is cleaner.

See ARCHITECTURE.md > Auto-Update Strategy.
"""

import logging
import re

import requests
from nicegui import ui

# ── Version ────────────────────────────────────────────────────────────────
# Bump this string with every release.  Use strict semver: MAJOR.MINOR.PATCH
APP_VERSION = "1.0.0"

# ── GitHub Repository ───────────────────────────────────────────────────────
# Update these two constants to match your public GitHub repo.
GITHUB_OWNER = "themeaningofmeaning"   # e.g. "meaning"
GITHUB_REPO  = "ultra-state"     # e.g. "ultra-state"

RELEASES_API_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)

log = logging.getLogger(__name__)


# ── Semver helpers ──────────────────────────────────────────────────────────

def _parse_version(version_str: str) -> tuple[int, ...]:
    """
    Parse a version string like 'v1.2.3' or '1.2.3' into a comparable tuple.
    Returns (0, 0, 0) on any parse failure so a bad tag never crashes the app.
    """
    cleaned = version_str.lstrip("v").strip()
    parts = re.findall(r"\d+", cleaned)
    try:
        return tuple(int(p) for p in parts[:3])
    except ValueError:
        return (0, 0, 0)


def _is_newer(remote: str, local: str) -> bool:
    """Return True if the remote version is strictly newer than the local one."""
    return _parse_version(remote) > _parse_version(local)


# ── Core check ─────────────────────────────────────────────────────────────

def check_for_update() -> dict | None:
    """
    Fetch the latest GitHub release and compare to APP_VERSION.

    Returns a dict with release info if an update is available, or None if
    the app is up-to-date or the check fails.

    Return shape:
        {
            'tag_name':    str,   # e.g. 'v1.1.0'
            'html_url':    str,   # Link to release page on GitHub
            'body':        str,   # Release notes (may be empty)
        }
    """
    try:
        response = requests.get(
            RELEASES_API_URL,
            timeout=5,
            headers={"Accept": "application/vnd.github+json"},
        )
        response.raise_for_status()
        data = response.json()

        tag = data.get("tag_name", "")
        if not tag:
            log.debug("updater: no tag_name in response, skipping.")
            return None

        if _is_newer(tag, APP_VERSION):
            return {
                "tag_name": tag,
                "html_url": data.get("html_url", ""),
                "body":     data.get("body", ""),
            }

        log.debug("updater: app is up to date (%s >= %s).", APP_VERSION, tag)
        return None

    except requests.exceptions.ConnectionError:
        log.debug("updater: no internet connection, skipping version check.")
        return None
    except requests.exceptions.Timeout:
        log.debug("updater: version check timed out.")
        return None
    except Exception as exc:
        log.warning("updater: unexpected error during version check: %s", exc)
        return None


# ── NiceGUI integration ─────────────────────────────────────────────────────

async def check_and_notify() -> None:
    """
    Async wrapper suitable for use with ui.timer(once=True).

    Runs the network check in a background thread so it never blocks the
    NiceGUI event loop, then fires a toast notification if an update is found.

    Usage in app.py __init__:
        from updater import check_and_notify
        ui.timer(3.0, check_and_notify, once=True)
    """
    from nicegui import run as nicegui_run

    release = await nicegui_run.io_bound(check_for_update)

    if release:
        tag = release["tag_name"]
        url = release["html_url"]
        log.info("updater: update available — %s", tag)

        ui.notify(
            f"🚀 Ultra State {tag} is available! Visit GitHub to download.",
            type="positive",
            position="top-right",
            timeout=0,          # Stays visible until dismissed
            close_button=True,
            actions=[
                {
                    "label": "Open GitHub",
                    "color": "white",
                    "handler": f"() => window.open('{url}', '_blank')",
                }
            ],
        )
