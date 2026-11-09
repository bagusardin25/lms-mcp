"""Konfirmasi di browser komputer pengguna.

Parameter tool bisa diisi AI sendiri, jadi unduh dan unggah tidak jalan sebelum
pengguna menekan tombol. Halaman ini hanya menerima sambungan dari komputer yang sama,
dan alamatnya tidak dikembalikan ke AI.
"""

from __future__ import annotations

import secrets
import threading
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.parse import parse_qs

from .oauth import SECURITY_HEADERS

CONFIRM_TIMEOUT_SECONDS = 180
_MAX_BODY_BYTES = 8 * 1024


@dataclass
class Confirmation:
    choice: str
    values: dict[str, str] = field(default_factory=dict)


def refusal(choice: str, undone: str) -> str:
    reasons = {
        "cancel": "Kamu membatalkan di halaman konfirmasi.",
        "timeout": "Waktu konfirmasi habis sebelum ada yang menekan tombol.",
        "unopened": "Halaman konfirmasi tidak bisa dibuka di browser.",
    }
    reason = reasons.get(choice, "Konfirmasi tidak selesai.")
    return f"{reason} {undone}"


def ask_user(
    page: str,
    *,
    timeout: float = CONFIRM_TIMEOUT_SECONDS,
    open_browser: Callable[[str], object] | None = None,
) -> Confirmation:
    """Menampilkan page dan menunggu tombol. choice bernilai allow, cancel, timeout, atau unopened."""
    token = secrets.token_urlsafe(32)
    state = Confirmation("timeout")
    decided = threading.Event()
    serving = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] != f"/{token}":
                self._send(404, b"")
                return
            self._send(200, page.encode())

        def do_POST(self) -> None:
            if self.path.split("?", 1)[0] != f"/{token}":
                self._send(404, b"")
                return
            if decided.is_set():
                self._send(409, _text("Konfirmasi ini sudah selesai. Tab ini boleh ditutup."))
                return
            length = int(self.headers.get("content-length") or 0)
            if length > _MAX_BODY_BYTES:
                self._send(413, _text("Data konfirmasi terlalu besar."))
                return
            form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            decision = (form.get("decision") or ["cancel"])[0]
            if decision not in {"allow", "cancel"}:
                decision = "cancel"
            state.choice = decision
            state.values = {key: item[0] for key, item in form.items() if item}
            self._send(200, _text("Sudah dicatat. Tab ini boleh ditutup."))
            decided.set()

        def log_message(self, format: str, *args: object) -> None:
            # Path berisi token sekali pakai. Jangan ikut tercetak di log yang bisa dibaca AI.
            return

        def _send(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

    class _Server(HTTPServer):
        def serve_forever(self, poll_interval: float = 0.05) -> None:
            serving.set()
            super().serve_forever(poll_interval)

    server = _Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, name="lms-mcp-confirm", daemon=True)
    thread.start()
    serving.wait()
    url = f"http://127.0.0.1:{server.server_address[1]}/{token}"
    try:
        opened = _open(url, open_browser)
        if not opened and not decided.is_set():
            state.choice = "unopened"
        elif not decided.wait(timeout) and not decided.is_set():
            state.choice = "timeout"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
    return state


def _open(url: str, open_browser: Callable[[str], object] | None) -> bool:
    try:
        if open_browser is None:
            return bool(webbrowser.open(url, new=2))
        open_browser(url)
    except Exception:
        return False
    return True


def _text(message: str) -> bytes:
    from html import escape

    return (
        "<!doctype html><meta charset=utf-8><title>LMS MCP</title>"
        f"<p>{escape(message)}</p>"
    ).encode()
