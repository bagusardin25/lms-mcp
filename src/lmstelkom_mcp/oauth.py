"""Login OAuth untuk mode online, tanpa database.

Server tidak menyimpan token LMS. Token itu disegel (dienkripsi) di dalam access token
dan refresh token yang dipegang klien, dan hanya server ini yang bisa membukanya. Data
klien dan kode otorisasi disegel dengan cara yang sama, jadi server tidak butuh penyimpanan
dan tiap pengguna otomatis memakai akun LMS-nya sendiri.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import secrets
import time
import zlib
from collections import deque
from typing import Any, Callable
from urllib.parse import quote, urlencode, urlsplit

import anyio
import httpx
from cryptography.fernet import Fernet, InvalidToken
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    RegistrationError,
    TokenError as OAuthTokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from .auth import TokenError, token_from_env
from .moodle import MoodleError

SCOPE = "lms"
VALID_SCOPES = [SCOPE, "offline_access"]

ACCESS_TOKEN_SECONDS = 60 * 60
REFRESH_TOKEN_SECONDS = 90 * 24 * 60 * 60
CODE_SECONDS = 5 * 60
LOGIN_REQUEST_SECONDS = 10 * 60

MAX_LOGIN_BODY_BYTES = 16 * 1024
LOGIN_ATTEMPTS_PER_MINUTE = 30

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Tanpa daftar ini, siapa pun bisa mendaftarkan alamat tujuannya sendiri lalu memancing
# korban menempelkan token, dan kode otorisasinya terkirim ke penyerang.
_DEFAULT_REDIRECT_HOSTS = {"claude.ai", "claude.com", "chatgpt.com", "chat.openai.com"}

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    # form-action sengaja tidak diisi: browser menerapkannya juga pada redirect ke klien.
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
    ),
}


class Sealer:
    """Mengenkripsi data. Field kind mencegah satu jenis nilai dipakai sebagai jenis lain."""

    def __init__(self, secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        self._fernet = Fernet(key)

    def seal(self, kind: str, data: dict[str, Any]) -> str:
        payload = json.dumps({"kind": kind, **data}, separators=(",", ":")).encode()
        return self._fernet.encrypt(zlib.compress(payload)).decode()

    def unseal(self, kind: str, value: str) -> dict[str, Any] | None:
        """Mengembalikan None kalau nilainya palsu, salah jenis, atau kedaluwarsa."""
        try:
            payload = json.loads(zlib.decompress(self._fernet.decrypt(value.encode())))
        except (InvalidToken, ValueError, zlib.error):
            return None
        if payload.pop("kind", None) != kind:
            return None
        if "exp" in payload and payload["exp"] <= time.time():
            return None
        return payload


class _RateLimiter:
    def __init__(self, limit: int, seconds: float) -> None:
        self._limit = limit
        self._seconds = seconds
        self._times: deque[float] = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self._times and self._times[0] <= now - self._seconds:
            self._times.popleft()
        if len(self._times) >= self._limit:
            return False
        self._times.append(now)
        return True


class LmsAuthorizationCode(AuthorizationCode):
    lms_token: str
    code_id: str


class LmsRefreshToken(RefreshToken):
    lms_token: str


def _is_allowed_redirect(uri: str, allowed_hosts: set[str]) -> bool:
    parsed = urlsplit(uri)
    if parsed.hostname in _LOOPBACK_HOSTS:
        return parsed.scheme in ("http", "https")
    return parsed.scheme == "https" and parsed.hostname in allowed_hosts


class LmsOAuthProvider:
    def __init__(
        self,
        *,
        sealer: Sealer,
        public_url: str,
        lms_url: str,
        verify_lms_token: Callable[[str], dict[str, Any]],
        extra_redirect_hosts: frozenset[str] = frozenset(),
    ) -> None:
        self._sealer = sealer
        self._public_url = public_url
        self._lms_url = lms_url
        self._verify_lms_token = verify_lms_token
        self._redirect_hosts = _DEFAULT_REDIRECT_HOSTS | extra_redirect_hosts
        self._login_limiter = _RateLimiter(LOGIN_ATTEMPTS_PER_MINUTE, 60)
        # Hanya di memori: setelah restart, kode dan token yang dicabut kembali ke masa
        # berlakunya masing-masing. Untuk memutus akses total, reset token di LMS.
        self._used_codes: dict[str, float] = {}
        self._revoked_tokens: dict[str, float] = {}

    # Pendaftaran klien

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        data = self._sealer.unseal("client", client_id)
        if data is None:
            return None
        return OAuthClientInformationFull.model_validate({**data, "client_id": client_id})

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        for uri in client_info.redirect_uris or []:
            if not _is_allowed_redirect(str(uri), self._redirect_hosts):
                raise RegistrationError(
                    error="invalid_redirect_uri",
                    error_description=f"Alamat redirect tidak diizinkan: {uri}",
                )
        data = client_info.model_dump(mode="json", exclude={"client_id"}, exclude_none=True)
        # Client_id menyimpan seluruh data klien, jadi tidak perlu tabel pendaftaran.
        client_info.client_id = self._sealer.seal("client", data)

    # Halaman login

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        request = self._sealer.seal(
            "login",
            {
                "client_id": client.client_id,
                "client_name": client.client_name,
                "redirect_uri": str(params.redirect_uri),
                "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
                "state": params.state,
                "scopes": params.scopes or [],
                "code_challenge": params.code_challenge,
                "resource": params.resource,
                "exp": int(time.time()) + LOGIN_REQUEST_SECONDS,
            },
        )
        return f"{self._public_url}/login?request={quote(request, safe='')}"

    async def login_page(self, request: Request) -> Response:
        sealed = request.query_params.get("request", "")
        data = self._sealer.unseal("login", sealed)
        if data is None:
            return _expired_response()
        return self._render_login(sealed, data)

    async def login_submit(self, request: Request) -> Response:
        if int(request.headers.get("content-length") or 0) > MAX_LOGIN_BODY_BYTES:
            return _message_response("Data yang dikirim terlalu besar.", 413)

        form = await request.form()
        sealed = str(form.get("request") or "")
        data = self._sealer.unseal("login", sealed)
        if data is None:
            return _expired_response()

        if not self._login_limiter.allow():
            return self._render_login(
                sealed, data, "Terlalu banyak percobaan. Coba lagi sebentar lagi.", 429
            )

        link = str(form.get("lms_link") or "").strip()
        if not link:
            return self._render_login(sealed, data, "Tautan token belum diisi.", 400)

        try:
            lms_token = token_from_env(link)
            info = await anyio.to_thread.run_sync(self._verify_lms_token, lms_token)
        except TokenError:
            return self._render_login(
                sealed, data, "Tautan tidak terbaca. Salin ulang lewat Copy link address.", 400
            )
        except MoodleError:
            return self._render_login(
                sealed, data, "LMS menolak token ini. Ambil tautan yang baru, lalu coba lagi.", 400
            )
        except httpx.HTTPError:
            return self._render_login(sealed, data, "LMS tidak bisa dihubungi. Coba lagi.", 502)

        code = self._sealer.seal(
            "code",
            {
                "code_id": secrets.token_urlsafe(16),
                "client_id": data["client_id"],
                "lms_token": lms_token,
                "subject": str(info.get("userid", "")),
                "redirect_uri": data["redirect_uri"],
                "redirect_uri_provided_explicitly": data["redirect_uri_provided_explicitly"],
                "scopes": data["scopes"],
                "code_challenge": data["code_challenge"],
                "resource": data["resource"],
                "exp": int(time.time()) + CODE_SECONDS,
            },
        )
        return RedirectResponse(
            construct_redirect_uri(data["redirect_uri"], code=code, state=data["state"]),
            status_code=303,
            headers=_SECURITY_HEADERS,
        )

    def _render_login(
        self, sealed: str, data: dict[str, Any], error: str = "", status: int = 200
    ) -> Response:
        token_page = (
            f"{self._lms_url}/admin/tool/mobile/launch.php?"
            + urlencode(
                {
                    "service": "moodle_mobile_app",
                    "passport": "1",
                    "urlscheme": "moodlemobile",
                    "confirmed": "1",
                }
            )
        )
        target = urlsplit(data["redirect_uri"]).hostname or ""
        client_name = data.get("client_name") or "Aplikasi tanpa nama"
        error_block = f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ""
        return HTMLResponse(
            _LOGIN_TEMPLATE.format(
                client=html.escape(client_name),
                target=html.escape(target),
                token_page=html.escape(token_page, quote=True),
                error=error_block,
                request=html.escape(sealed, quote=True),
            ),
            status_code=status,
            headers=_SECURITY_HEADERS,
        )

    # Kode otorisasi

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> LmsAuthorizationCode | None:
        data = self._sealer.unseal("code", authorization_code)
        if data is None or data["client_id"] != client.client_id:
            return None
        self._forget_expired(self._used_codes)
        if data["code_id"] in self._used_codes:
            return None
        return LmsAuthorizationCode(
            code=authorization_code,
            code_id=data["code_id"],
            client_id=data["client_id"],
            lms_token=data["lms_token"],
            subject=data["subject"],
            scopes=data["scopes"],
            expires_at=data["exp"],
            code_challenge=data["code_challenge"],
            redirect_uri=data["redirect_uri"],
            redirect_uri_provided_explicitly=data["redirect_uri_provided_explicitly"],
            resource=data["resource"],
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: LmsAuthorizationCode
    ) -> OAuthToken:
        self._used_codes[authorization_code.code_id] = authorization_code.expires_at
        return self._issue_tokens(
            client_id=authorization_code.client_id,
            scopes=authorization_code.scopes,
            resource=authorization_code.resource,
            subject=authorization_code.subject,
            lms_token=authorization_code.lms_token,
        )

    # Token

    def _issue_tokens(
        self,
        *,
        client_id: str,
        scopes: list[str],
        resource: str | None,
        subject: str | None,
        lms_token: str,
    ) -> OAuthToken:
        # Scope lms selalu ikut, karena semua tool membutuhkannya.
        scopes = sorted({*scopes, SCOPE})
        now = int(time.time())
        common = {
            "client_id": client_id,
            "scopes": scopes,
            "resource": resource,
            "subject": subject,
            "lms_token": lms_token,
        }
        return OAuthToken(
            access_token=self._sealer.seal(
                "access", {**common, "exp": now + ACCESS_TOKEN_SECONDS}
            ),
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_SECONDS,
            scope=" ".join(scopes),
            refresh_token=self._sealer.seal(
                "refresh", {**common, "exp": now + REFRESH_TOKEN_SECONDS}
            ),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        data = self._unseal_token("access", token)
        if data is None:
            return None
        return AccessToken(
            token=token,
            client_id=data["client_id"],
            scopes=data["scopes"],
            expires_at=data["exp"],
            resource=data["resource"],
            subject=data["subject"],
            claims={"lms_token": data["lms_token"]},
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> LmsRefreshToken | None:
        data = self._unseal_token("refresh", refresh_token)
        if data is None or data["client_id"] != client.client_id:
            return None
        return LmsRefreshToken(
            token=refresh_token,
            client_id=data["client_id"],
            scopes=data["scopes"],
            expires_at=data["exp"],
            resource=data["resource"],
            subject=data["subject"],
            lms_token=data["lms_token"],
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: LmsRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        return self._issue_tokens(
            client_id=refresh_token.client_id,
            scopes=scopes or refresh_token.scopes,
            resource=refresh_token.resource,
            subject=refresh_token.subject,
            lms_token=refresh_token.lms_token,
        )

    async def exchange_identity_assertion(self, client: Any, params: Any) -> OAuthToken:
        raise OAuthTokenError(error="unsupported_grant_type")

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self._revoked_tokens[_fingerprint(token.token)] = float(
            token.expires_at or time.time() + REFRESH_TOKEN_SECONDS
        )

    def _unseal_token(self, kind: str, token: str) -> dict[str, Any] | None:
        self._forget_expired(self._revoked_tokens)
        if _fingerprint(token) in self._revoked_tokens:
            return None
        return self._sealer.unseal(kind, token)

    @staticmethod
    def _forget_expired(entries: dict[str, float]) -> None:
        now = time.time()
        for key in [key for key, expires in entries.items() if expires <= now]:
            del entries[key]


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _message_response(message: str, status: int) -> Response:
    return HTMLResponse(
        _MESSAGE_TEMPLATE.format(message=html.escape(message)),
        status_code=status,
        headers=_SECURITY_HEADERS,
    )


def _expired_response() -> Response:
    return _message_response(
        "Permintaan login ini sudah tidak berlaku. Ulangi dari aplikasi AI-mu.", 400
    )


_STYLE = """\
:root{color-scheme:light dark}
body{font:16px/1.5 system-ui,sans-serif;max-width:34rem;margin:2rem auto;padding:0 1rem}
h1{font-size:1.4rem}
textarea{width:100%;box-sizing:border-box;font:14px monospace;padding:.5rem}
button{font:inherit;font-weight:600;padding:.6rem 1.2rem;margin-top:.75rem;cursor:pointer}
.error{border-left:4px solid #c0392b;padding:.25rem .75rem}
.note{font-size:.875rem;opacity:.8}
code{overflow-wrap:anywhere}"""

_MESSAGE_TEMPLATE = (
    '<!doctype html><html lang="id"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    f"<title>LMS Telkom MCP</title><style>{_STYLE.replace('{', '{{').replace('}', '}}')}</style>"
    "</head><body><h1>LMS Telkom MCP</h1><p>{message}</p></body></html>"
)

_LOGIN_TEMPLATE = (
    '<!doctype html><html lang="id"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    f"<title>Hubungkan LMS</title><style>{_STYLE.replace('{', '{{').replace('}', '}}')}</style>"
    """</head><body>
<h1>Hubungkan akun LMS-mu</h1>
<p><strong>{client}</strong> ingin membaca data LMS atas namamu, seperti mata kuliah, deadline, dan materi.
Akses akan dikirim ke <code>{target}</code>. Lanjutkan hanya kalau kamu yang memulai proses ini.</p>
{error}
<ol>
<li>Buka <a href="{token_page}" target="_blank" rel="noopener noreferrer">halaman token LMS</a>, lalu login kalau diminta.</li>
<li>Klik kanan tulisan "Click here if the app does not open automatically", lalu pilih <em>Copy link address</em>.</li>
<li>Tempel hasilnya di kotak ini.</li>
</ol>
<form method="post" action="login">
<input type="hidden" name="request" value="{request}">
<label for="lms_link">Tautan token</label>
<textarea id="lms_link" name="lms_link" rows="4" required autocomplete="off" spellcheck="false" placeholder="moodlemobile://token=..."></textarea>
<button type="submit">Hubungkan</button>
</form>
<p class="note">Ini proyek mahasiswa yang tidak resmi. Token setara akses penuh ke akun LMS-mu, jadi hanya tempel kalau kamu percaya pada pemilik server ini.</p>
</body></html>"""
)
