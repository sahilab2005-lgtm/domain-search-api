import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse

_LOCK = threading.RLock()
_DEFAULT_CONFIG_PATH = str(Path(__file__).resolve().parent / "config.json")
CONFIG_PATH = os.getenv("DOMAIN_CONFIG_PATH", _DEFAULT_CONFIG_PATH)

_DEFAULT_CONFIG = {
    "allowed_domains": [],
    "blocked_domains": [],
}


def _normalize(domain: str) -> str:
    d = domain.strip().lower()
    if d.startswith("www."):
        d = d[4:]
    return d


def _read_raw() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return dict(_DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠ Could not read {CONFIG_PATH} ({e}) — using empty domain config.")
        return dict(_DEFAULT_CONFIG)

    if not isinstance(data, dict):
        print(f"⚠ {CONFIG_PATH} did not contain a JSON object — using empty domain config.")
        return dict(_DEFAULT_CONFIG)

    allowed = data.get("allowed_domains", [])
    blocked = data.get("blocked_domains", [])
    if not isinstance(allowed, list):
        allowed = []
    if not isinstance(blocked, list):
        blocked = []

    return {
        "allowed_domains": sorted({_normalize(d) for d in allowed if _normalize(d)}),
        "blocked_domains": sorted({_normalize(d) for d in blocked if _normalize(d)}),
    }


def _write_raw(data: dict) -> None:
    tmp_path = f"{CONFIG_PATH}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp_path, CONFIG_PATH)  # atomic on POSIX and Windows


def _ensure_file_exists() -> None:
    if not os.path.exists(CONFIG_PATH):
        _write_raw(dict(_DEFAULT_CONFIG))
        print(f"✔ Created {CONFIG_PATH} with an empty allowlist/blocklist.")


_ensure_file_exists()


# ── reads ──────────────────────────────────────────────────────────────────

def get_allowed_domains() -> list[str]:
    with _LOCK:
        return _read_raw()["allowed_domains"]


def get_blocked_domains() -> list[str]:
    with _LOCK:
        return _read_raw()["blocked_domains"]


def get_config() -> dict:
    with _LOCK:
        return _read_raw()


def is_blocked(url_or_domain: str) -> bool:
    """True if the given URL's (or bare domain's) host matches, or is a
    subdomain of, any entry in blocked_domains."""
    host = url_or_domain
    if "://" in url_or_domain:
        try:
            host = urlparse(url_or_domain).netloc.split(":")[0]
        except Exception:
            host = url_or_domain
    host = _normalize(host)

    for b in get_blocked_domains():
        if host == b or host.endswith("." + b):
            return True
    return False


# ── writes ─────────────────────────────────────────────────────────────────

def add_allowed_domain(domain: str) -> None:
    d = _normalize(domain)
    if not d:
        return
    with _LOCK:
        data = _read_raw()
        if d not in data["allowed_domains"]:
            data["allowed_domains"].append(d)
            data["allowed_domains"].sort()
            _write_raw(data)


def remove_allowed_domain(domain: str) -> bool:
    d = _normalize(domain)
    with _LOCK:
        data = _read_raw()
        if d in data["allowed_domains"]:
            data["allowed_domains"].remove(d)
            _write_raw(data)
            return True
        return False


def add_blocked_domain(domain: str) -> None:
    d = _normalize(domain)
    if not d:
        return
    with _LOCK:
        data = _read_raw()
        if d not in data["blocked_domains"]:
            data["blocked_domains"].append(d)
            data["blocked_domains"].sort()
            _write_raw(data)


def remove_blocked_domain(domain: str) -> bool:
    d = _normalize(domain)
    with _LOCK:
        data = _read_raw()
        if d in data["blocked_domains"]:
            data["blocked_domains"].remove(d)
            _write_raw(data)
            return True
        return False
