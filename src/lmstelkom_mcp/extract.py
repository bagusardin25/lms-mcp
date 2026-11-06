"""Mengambil teks dari file materi, per halaman.

File berasal dari LMS, jadi diperlakukan sebagai data yang tidak dipercaya.
"""

from __future__ import annotations

import html
import io
import posixpath
import re
import zipfile
from typing import Any, Protocol

from docx import Document as open_docx
from docx.table import Table
from pptx import Presentation as open_pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pypdf import PdfReader

_FORMATS = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".docx": "docx",
    ".txt": "text",
    ".md": "text",
    ".csv": "text",
    ".html": "html",
    ".htm": "html",
}

# Satu pemanggilan tidak boleh memakan terlalu banyak konteks AI.
MAX_TEXT_CHARS = 30_000
# Format tanpa halaman (DOCX, teks, HTML) dipotong per sekian karakter.
CHARS_PER_PAGE = 3_000
# Batas ukuran setelah diekstrak, untuk menahan file zip bomb.
MAX_UNZIPPED_BYTES = 300 * 1024 * 1024
_MIN_CHARS_PER_PAGE = 20


class ExtractError(ValueError):
    pass


class _Document(Protocol):
    total_pages: int

    def page_text(self, number: int) -> str: ...


class _PdfDocument:
    """Halaman dibaca saat dibutuhkan, supaya PDF panjang tidak diproses seluruhnya."""

    def __init__(self, data: bytes) -> None:
        self._reader = PdfReader(io.BytesIO(data))
        if self._reader.is_encrypted and not self._reader.decrypt(""):
            raise ExtractError("PDF ini dilindungi password, jadi isinya tidak bisa dibaca.")
        self.total_pages = len(self._reader.pages)

    def page_text(self, number: int) -> str:
        return self._reader.pages[number - 1].extract_text() or ""


class _ListDocument:
    def __init__(self, pages: list[str]) -> None:
        self._pages = pages
        self.total_pages = len(pages)

    def page_text(self, number: int) -> str:
        return self._pages[number - 1]


def file_format(file_name: str) -> str:
    extension = posixpath.splitext(file_name)[1].lower()
    file_type = _FORMATS.get(extension)
    if file_type is None:
        raise ExtractError(
            f"Format {extension or 'file ini'} belum bisa dibaca. "
            "Yang didukung: PDF, PPTX, DOCX, TXT, MD, CSV, dan HTML."
        )
    return file_type


def read_pages(
    data: bytes, file_type: str, start_page: int, page_count: int
) -> dict[str, Any]:
    # Parser membuka file dari luar dan bisa gagal dengan banyak jenis error.
    try:
        document = _open_document(data, file_type)
        return _collect_pages(document, start_page, page_count)
    except ExtractError:
        raise
    except Exception:
        raise ExtractError("File tidak bisa dibaca, mungkin rusak atau bukan format aslinya.") from None


def _open_document(data: bytes, file_type: str) -> _Document:
    if file_type == "pdf":
        return _PdfDocument(data)
    if file_type == "pptx":
        _check_zip_size(data)
        return _ListDocument(_pptx_pages(data))
    if file_type == "docx":
        _check_zip_size(data)
        return _ListDocument(_split_pages(_docx_text(data)))
    text = data.decode("utf-8", errors="replace")
    if file_type == "html":
        text = _html_text(text)
    return _ListDocument(_split_pages(text))


def _collect_pages(document: _Document, start_page: int, page_count: int) -> dict[str, Any]:
    total = document.total_pages
    if total == 0:
        raise ExtractError("File ini tidak berisi teks.")
    if start_page > total:
        raise ExtractError(f"File ini hanya punya {total} halaman.")

    parts: list[str] = []
    blank_pages: list[int] = []
    chars = 0
    end_page = start_page
    truncated = False
    for number in range(start_page, min(start_page + page_count - 1, total) + 1):
        text = _normalize(document.page_text(number))
        if parts and chars + len(text) > MAX_TEXT_CHARS:
            break
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS]
            truncated = True
        if not text:
            blank_pages.append(number)
        parts.append(f"--- Halaman {number} ---\n{text or '(tidak ada teks)'}")
        chars += len(text)
        end_page = number

    result: dict[str, Any] = {
        "total_pages": total,
        "start_page": start_page,
        "end_page": end_page,
        "next_start_page": end_page + 1 if end_page < total else None,
        "text": "\n\n".join(parts),
    }
    if blank_pages:
        result["pages_without_text"] = blank_pages
    if chars < _MIN_CHARS_PER_PAGE * len(parts):
        result["warning"] = (
            "Halaman ini hampir tidak berisi teks, kemungkinan berupa gambar atau hasil scan."
        )
    if truncated:
        result["warning"] = f"Halaman ini dipotong sampai {MAX_TEXT_CHARS} karakter."
    return result


def _normalize(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _check_zip_size(data: bytes) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > MAX_UNZIPPED_BYTES:
            raise ExtractError("Isi file ini terlalu besar untuk dibaca.")


def _pptx_pages(data: bytes) -> list[str]:
    pages = []
    for slide in open_pptx(io.BytesIO(data)).slides:
        lines = _shape_lines(slide.shapes)
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame
            if notes is not None and notes.text.strip():
                lines.append(f"Catatan pembicara: {notes.text.strip()}")
        pages.append("\n".join(lines))
    return pages


def _shape_lines(shapes: Any) -> list[str]:
    lines: list[str] = []
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            lines.extend(_shape_lines(shape.shapes))
        elif getattr(shape, "has_table", False):
            lines.extend(
                " | ".join(cell.text.strip() for cell in row.cells) for row in shape.table.rows
            )
        elif getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
            lines.append(shape.text_frame.text.strip())
    return lines


def _docx_text(data: bytes) -> str:
    blocks = []
    for block in open_docx(io.BytesIO(data)).iter_inner_content():
        if isinstance(block, Table):
            blocks.extend(
                " | ".join(cell.text.strip() for cell in row.cells) for row in block.rows
            )
        elif block.text.strip():
            blocks.append(block.text.strip())
    return "\n\n".join(blocks)


def _html_text(value: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", value)
    text = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr)\b[^>]*>", "\n", text)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def _split_pages(text: str) -> list[str]:
    """Memotong teks di batas baris supaya kalimat tidak terbelah kalau bisa."""
    text = _normalize(text)
    pages = []
    while len(text) > CHARS_PER_PAGE:
        cut = text.rfind("\n", 0, CHARS_PER_PAGE)
        if cut <= 0:
            cut = CHARS_PER_PAGE
        pages.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        pages.append(text)
    return pages
