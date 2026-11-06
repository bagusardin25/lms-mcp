"""Membaca token web service Moodle dari nilai LMS_TOKEN.

Halaman launch.php Moodle menampilkan tautan moodlemobile://token=<base64>, dengan
isi base64 berupa signature:::token:::privatetoken. Private token sengaja dibuang
karena hanya dipakai untuk auto-login ke halaman web.
"""

from __future__ import annotations

import base64
import binascii
import re
from urllib.parse import unquote

_TOKEN_PATTERN = re.compile(r"token=([A-Za-z0-9+/=%_-]+)")


class TokenError(Exception):
    """Pesannya tidak pernah memuat nilai LMS_TOKEN."""


def token_from_env(value: str) -> str:
    """LMS_TOKEN boleh berisi token langsung atau tautan moodlemobile://token=...

    Signature tidak diperiksa karena passport-nya tidak diketahui di sini.
    Keabsahan token tetap diuji oleh LMS saat dipakai.
    """
    if "token=" not in value:
        return value.strip()

    match = _TOKEN_PATTERN.search(value)
    if not match:
        raise TokenError("Isi LMS_TOKEN tidak terbaca. Pastikan tautan tersalin utuh.")

    encoded = unquote(match.group(1)).rstrip("=").replace("-", "+").replace("_", "/")
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(padded, validate=True).decode("ascii")
    except (binascii.Error, UnicodeDecodeError):
        raise TokenError(
            "Isi LMS_TOKEN tidak terbaca. Pastikan tautan tersalin utuh."
        ) from None

    parts = decoded.split(":::")
    if len(parts) < 2 or not parts[1]:
        raise TokenError("Format LMS_TOKEN tidak dikenali. Pastikan tautan tersalin utuh.")
    return parts[1]
