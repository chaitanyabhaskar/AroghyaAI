"""TLS trust configuration for outbound HTTPS calls.

Corporate networks often run a TLS-inspecting proxy (Zscaler, Netskope, and
friends) that re-signs HTTPS with a private root CA. That root lives in the OS
trust store, which browsers use, but Python validates against the bundled
certifi list and fails with CERTIFICATE_VERIFY_FAILED.

``truststore`` points Python at the native OS trust store instead, so the
corporate root is picked up with no manual certificate export. On a plain cloud
host this changes nothing useful - the OS store trusts the same public CAs.
"""

from __future__ import annotations

import os
import ssl
from functools import lru_cache
from typing import Any

# GenAI Generated code - Start


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@lru_cache(maxsize=1)
def ssl_verify() -> Any:
    """Value for httpx's ``verify=`` argument.

    Returns, in order of preference:
      * a path/bundle from ``CA_BUNDLE`` or ``SSL_CERT_FILE`` if either is set
      * an SSLContext backed by the OS trust store (default)
      * ``True`` - plain certifi - if the OS store is unavailable or disabled

    Verification is never disabled.
    """
    bundle = (os.getenv("CA_BUNDLE") or os.getenv("SSL_CERT_FILE") or "").strip()
    if bundle and os.path.exists(bundle):
        return bundle

    if not _flag("SSL_USE_SYSTEM_CERTS", True):
        return True

    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        # truststore missing or unsupported platform - fall back to certifi.
        return True


def describe() -> str:
    """Short human-readable description, for logs and /healthz."""
    verify = ssl_verify()
    if isinstance(verify, str):
        return f"ca-bundle:{verify}"
    if isinstance(verify, ssl.SSLContext):
        return "os-trust-store"
    return "certifi"
# GenAI Generated code - End
