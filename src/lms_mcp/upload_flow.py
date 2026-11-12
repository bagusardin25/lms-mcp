"""Halaman upload untuk mode online.

AI chat di web tidak bisa mengambil file dari komputer pengguna, dan AI tidak boleh
mengumpulkan tugas sendiri. Karena itu AI hanya bisa membuat tautan, sedangkan pengguna yang
memilih file dan menekan tombol. File diteruskan ke LMS tanpa disimpan.
"""

from __future__ import annotations

import secrets
import time
from typing import Any, Callable
from urllib.parse import quote

import anyio
import httpx
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

from .assignments import MAX_UPLOAD_BYTES, AssignmentError, AssignmentOperations
from .moodle import MoodleError
from .oauth import SECURITY_HEADERS, RateLimiter, Sealer, visitor_key
from .pages import message_page, upload_form_page, upload_result_page

UPLOAD_LINK_SECONDS = 15 * 60
UPLOAD_ATTEMPTS_PER_MINUTE = 20
_FORM_OVERHEAD_BYTES = 64 * 1024


class UploadFlow:
    def __init__(
        self,
        *,
        sealer: Sealer,
        public_url: str,
        operations_for: Callable[[str], AssignmentOperations],
        generation: int = 0,
    ) -> None:
        self._sealer = sealer
        self._public_url = public_url
        self._operations_for = operations_for
        self._generation = generation
        self._limiter = RateLimiter(UPLOAD_ATTEMPTS_PER_MINUTE, 60)
        # Hanya di memori: setelah restart, tautan kembali berlaku sampai masa berlakunya habis.
        self._used: dict[str, float] = {}

    def _seal(self, kind: str, lms_token: str, course_id: int, assignment_id: int) -> str:
        return self._sealer.seal(
            kind,
            {
                "id": secrets.token_urlsafe(12),
                "lms_token": lms_token,
                "course_id": course_id,
                "assignment_id": assignment_id,
                "gen": self._generation,
                "exp": int(time.time()) + UPLOAD_LINK_SECONDS,
            },
        )

    def _open(self, kind: str, sealed: str) -> dict[str, Any] | None:
        data = self._sealer.unseal(kind, sealed)
        now = time.time()
        for key in [key for key, expires in self._used.items() if expires <= now]:
            del self._used[key]
        if data is None or int(data.get("gen", 0)) != self._generation or data["id"] in self._used:
            return None
        return data

    def create_link(self, lms_token: str, course_id: int, assignment_id: int) -> dict[str, Any]:
        """Membuat tautan untuk AI. Tugas dicek dulu supaya pengguna tidak membuka tautan buntu."""
        context = self._operations_for(lms_token).upload_context(course_id, assignment_id)
        sealed = self._seal("upload", lms_token, course_id, assignment_id)
        return {
            "assignment": context["name"],
            "upload_url": f"{self._public_url}/upload?request={quote(sealed, safe='')}",
            "expires_in_minutes": UPLOAD_LINK_SECONDS // 60,
            "note": (
                "Berikan tautan ini kepada pengguna. Pengguna sendiri yang memilih file dan "
                "menekan tombol. Tautan ini hanya untuk satu kali upload."
            ),
        }

    async def page(self, request: Request) -> Response:
        sealed = request.query_params.get("request", "")
        data = self._open("upload", sealed)
        if data is None:
            return _expired()
        try:
            context = await self._load_context(data)
        except (AssignmentError, MoodleError) as error:
            return _html(message_page(_user_message(error)), 400)
        except httpx.HTTPError:
            return _html(message_page("LMS tidak bisa dihubungi. Coba lagi sebentar lagi."), 502)
        return _html(upload_form_page(context=context, request=sealed))

    async def _load_context(self, data: dict[str, Any]) -> dict[str, Any]:
        operations = self._operations_for(data["lms_token"])
        return await anyio.to_thread.run_sync(
            operations.upload_context, data["course_id"], data["assignment_id"]
        )

    async def submit(self, request: Request) -> Response:
        # Tanpa panjang yang jelas, ukuran kiriman tidak bisa dibatasi sebelum dibaca.
        length = request.headers.get("content-length")
        if length is None:
            return _html(message_page("Ukuran kiriman tidak diketahui. Coba lagi."), 411)
        if int(length) > MAX_UPLOAD_BYTES + _FORM_OVERHEAD_BYTES:
            limit = MAX_UPLOAD_BYTES // (1024 * 1024)
            return _html(message_page(f"File terlalu besar. Batasnya {limit} MB."), 413)

        form = await request.form(max_files=1, max_fields=8)
        try:
            if form.get("step") == "final":
                return await self._submit_final(form)
            return await self._save(form, visitor_key(request))
        finally:
            await form.close()

    async def _save(self, form: Any, visitor: str) -> Response:
        sealed = str(form.get("request") or "")
        data = self._open("upload", sealed)
        if data is None:
            return _expired()
        if not self._limiter.allow(visitor):
            return await self._form_with_error(data, sealed, "Terlalu banyak percobaan. Coba lagi sebentar lagi.", 429)

        upload = form.get("file")
        if not isinstance(upload, UploadFile) or not upload.filename:
            return await self._form_with_error(data, sealed, "Pilih file dulu.", 400)
        content = await upload.read()

        operations = self._operations_for(data["lms_token"])

        def save() -> dict[str, Any]:
            return operations.save_file(
                data["course_id"],
                data["assignment_id"],
                upload.filename,
                content,
                replace_existing=form.get("replace") == "yes",
                allow_immediate=form.get("confirm_immediate") == "yes",
            )

        try:
            result = await anyio.to_thread.run_sync(save)
        except (AssignmentError, MoodleError) as error:
            return await self._form_with_error(data, sealed, _user_message(error), 400)
        except httpx.HTTPError:
            return await self._form_with_error(data, sealed, "LMS tidak bisa dihubungi. Coba lagi.", 502)

        self._used[data["id"]] = float(data["exp"])
        return await self._saved_response(data, result)

    async def _saved_response(self, data: dict[str, Any], result: dict[str, Any]) -> Response:
        final_request = None
        statement = ""
        if result["submission_status"] == "draft":
            context = await self._load_context(data)
            statement = context["rules"].statement if context["rules"].requires_statement else ""
            final_request = self._seal(
                "final", data["lms_token"], data["course_id"], data["assignment_id"]
            )
        return _html(
            upload_result_page(result=result, final_request=final_request, statement=statement)
        )

    async def _submit_final(self, form: Any) -> Response:
        data = self._open("final", str(form.get("request") or ""))
        if data is None:
            return _expired()
        operations = self._operations_for(data["lms_token"])

        def submit() -> dict[str, Any]:
            return operations.submit_final(
                data["course_id"],
                data["assignment_id"],
                statement_accepted=form.get("accept_statement") == "yes",
            )

        try:
            result = await anyio.to_thread.run_sync(submit)
        except (AssignmentError, MoodleError) as error:
            return _html(message_page(_user_message(error)), 400)
        except httpx.HTTPError:
            return _html(message_page("LMS tidak bisa dihubungi. Coba lagi."), 502)

        self._used[data["id"]] = float(data["exp"])
        return _html(upload_result_page(result=result, final_request=None, statement=""))

    async def _form_with_error(
        self, data: dict[str, Any], sealed: str, error: str, status: int
    ) -> Response:
        try:
            context = await self._load_context(data)
        except (AssignmentError, MoodleError, httpx.HTTPError):
            return _html(message_page(error), status)
        return _html(upload_form_page(context=context, request=sealed, error=error), status)


def _user_message(error: Exception) -> str:
    # Pesan MoodleError diawali kode error yang tidak berarti bagi pengguna.
    return str(error).split(": ", 1)[-1] if isinstance(error, MoodleError) else str(error)


def _html(body: str, status: int = 200) -> Response:
    return HTMLResponse(body, status_code=status, headers=SECURITY_HEADERS)


def _expired() -> Response:
    return _html(
        message_page("Tautan upload ini sudah tidak berlaku. Minta tautan baru ke AI-mu."), 400
    )
