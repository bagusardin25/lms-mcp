"""Client REST untuk web service Moodle."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

_FILE_PATH = "/webservice/pluginfile.php/"
_PUBLIC_FILE_PATH = "/pluginfile.php/"
_MAX_JSON_ERROR_BYTES = 64 * 1024

_RENEW_TOKEN = "Perbarui LMS_TOKEN di file .env, atau sambungkan ulang connector di aplikasi AI."
_ERROR_HINTS = {
    "invalidtoken": _RENEW_TOKEN,
    # Moodle memakai kode ini juga untuk token kedaluwarsa, dan alasan persisnya
    # hanya ada di info debug. Setelah itu tokennya dihapus, jadi panggilan
    # berikutnya membalas invalidtoken.
    "accessexception": f"Kemungkinan token sudah kedaluwarsa. {_RENEW_TOKEN}",
    # File dari repository seperti Office 365 dilayani lewat redirect, yang ditolak
    # Moodle kalau diminta lewat web service.
    "redirecterrordetected": (
        "File ini tersimpan di luar LMS, misalnya di Office 365, jadi tidak bisa diambil "
        "lewat token. Buka lewat get_file_link di browser, lalu unggah filenya ke AI "
        "kalau isinya perlu dibaca."
    ),
}


class MoodleError(Exception):
    def __init__(self, errorcode: str, message: str) -> None:
        hint = _ERROR_HINTS.get(errorcode)
        if hint:
            message = f"{message}. {hint}"
        super().__init__(f"{errorcode}: {message}")
        self.errorcode = errorcode


class MoodleClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._token = token
        self._http = httpx.Client(
            base_url=base_url,
            timeout=30,
            headers={"User-Agent": "lmstelkom-mcp/0.1"},
            transport=transport,
        )

    def call(self, function: str, **params: Any) -> Any:
        # Token dikirim di body POST supaya tidak muncul di URL atau log.
        response = self._http.post(
            "/webservice/rest/server.php",
            data={
                "wstoken": self._token,
                "wsfunction": function,
                "moodlewsrestformat": "json",
                **params,
            },
        )
        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            raise MoodleError(
                "invalidresponse", "Respons LMS bukan JSON, mungkin sedang maintenance."
            ) from None

        _raise_for_moodle_error(payload)
        return payload

    def file_path(self, url: str) -> str:
        """Memastikan URL menunjuk ke file di LMS ini sebelum token dikirim.

        URL bisa berasal dari konten LMS atau dari AI, jadi host lain harus ditolak
        supaya token tidak terkirim ke server orang lain.
        """
        parsed = urlsplit(url)
        base = urlsplit(self._base_url)
        if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
            raise MoodleError("invalidfileurl", "URL file harus berasal dari LMS ini.")

        path = parsed.path
        if path.startswith(_PUBLIC_FILE_PATH):
            path = _FILE_PATH + path.removeprefix(_PUBLIC_FILE_PATH)
        if not path.startswith(_FILE_PATH) or ".." in path.split("/"):
            raise MoodleError("invalidfileurl", "URL ini bukan URL file LMS.")
        return path

    def browser_file_url(self, url: str) -> str:
        """URL file untuk dibuka di browser dengan sesi login LMS, tanpa token."""
        relative = self.file_path(url).removeprefix(_FILE_PATH)
        return f"{self._base_url}{_PUBLIC_FILE_PATH}{relative}"

    @contextmanager
    def _open_file(
        self, url: str, max_bytes: int
    ) -> Iterator[tuple[str | None, Iterator[bytes]]]:
        path = self.file_path(url)
        with self._http.stream(
            "POST",
            path,
            params={"forcedownload": 1},
            data={"token": self._token},
            timeout=httpx.Timeout(30, read=120),
        ) as response:
            if response.status_code != 200:
                raise MoodleError(
                    "downloadfailed", f"LMS membalas HTTP {response.status_code}."
                )
            yield response.headers.get("content-type"), _limit_size(
                response.iter_bytes(), max_bytes
            )

    def download(self, url: str, destination: Path, max_bytes: int) -> str | None:
        """Mengunduh file ke destination dan mengembalikan tipe kontennya."""
        partial = destination.with_name(destination.name + ".part")
        try:
            with self._open_file(url, max_bytes) as (content_type, chunks):
                with partial.open("wb") as output:
                    for chunk in chunks:
                        output.write(chunk)

            if partial.stat().st_size <= _MAX_JSON_ERROR_BYTES:
                _raise_for_error_body(partial.read_bytes(), content_type)
            partial.replace(destination)
            return content_type
        finally:
            partial.unlink(missing_ok=True)

    def read_bytes(self, url: str, max_bytes: int) -> bytes:
        """Mengambil isi file ke memori, tanpa menyimpannya ke disk."""
        with self._open_file(url, max_bytes) as (content_type, chunks):
            data = b"".join(chunks)
        if len(data) <= _MAX_JSON_ERROR_BYTES:
            _raise_for_error_body(data, content_type)
        return data


def _limit_size(chunks: Iterator[bytes], max_bytes: int) -> Iterator[bytes]:
    total = 0
    for chunk in chunks:
        total += len(chunk)
        if total > max_bytes:
            raise MoodleError(
                "filetoolarge", f"File melebihi batas {max_bytes // (1024 * 1024)} MB."
            )
        yield chunk


def _raise_for_moodle_error(payload: Any) -> None:
    # Moodle melaporkan error dengan status HTTP 200.
    if isinstance(payload, dict) and ("exception" in payload or "errorcode" in payload):
        raise MoodleError(
            payload.get("errorcode", "unknown"),
            payload.get("message") or payload.get("error") or "",
        )


def _raise_for_error_body(body: bytes, content_type: str | None) -> None:
    # Saat gagal, pluginfile bisa membalas JSON error dengan status HTTP 200.
    if not (content_type or "").startswith("application/json"):
        return
    try:
        payload = json.loads(body)
    except ValueError:
        return
    _raise_for_moodle_error(payload)
