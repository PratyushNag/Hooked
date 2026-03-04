from __future__ import annotations

import hashlib
import hmac


def is_valid_signature(secret: str | None, payload: bytes, signature_header: str | None) -> bool:
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    received = signature_header.split("=", 1)[1]
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received, expected)
