"""Membaca token web service Moodle dari nilai LMS_TOKEN atau dari kotak login.

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
_ENV_LINE_PREFIX = re.compile(r"^(?:export\s+)?LMS_TOKEN\s*=\s*", re.IGNORECASE)
# Token web service Moodle selalu berupa md5, yaitu 32 karakter hex.
_WS_TOKEN = re.compile(r"[0-9a-fA-F]{32}")


class TokenError(Exception):
    """Pesannya tidak pernah memuat nilai LMS_TOKEN."""


def token_from_env(value: str) -> str:
    """Menerima token, tautan moodlemobile://token=..., atau baris utuh dari file .env.

    Signature tidak diperiksa karena passport-nya tidak diketahui di sini.
    Keabsahan token tetap diuji oleh LMS saat dipakai.
    """
    value = _ENV_LINE_PREFIX.sub("", value.strip()).strip("'\" \t\r\n")

    if "token=" in value:
        value = _token_from_link(value)
    if not _WS_TOKEN.fullmatch(value):
        raise TokenError("Isi token tidak terbaca. Pastikan tersalin utuh, tanpa diketik ulang.")
    return value


def _token_from_link(link: str) -> str:
    match = _TOKEN_PATTERN.search(link)
    if not match:
        raise TokenError("Isi token tidak terbaca. Pastikan tersalin utuh, tanpa diketik ulang.")

    encoded = unquote(match.group(1)).rstrip("=").replace("-", "+").replace("_", "/")
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(padded, validate=True).decode("ascii")
    except (binascii.Error, UnicodeDecodeError):
        raise TokenError(
            "Isi token tidak terbaca. Pastikan tersalin utuh, tanpa diketik ulang."
        ) from None

    parts = decoded.split(":::")
    if len(parts) < 2 or not parts[1]:
        raise TokenError("Isi token tidak terbaca. Pastikan tersalin utuh, tanpa diketik ulang.")
    return parts[1]
