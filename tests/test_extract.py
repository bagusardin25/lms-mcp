import io
import zipfile

import pytest
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from pypdf import PdfWriter

from lms_mcp import extract
from lms_mcp.extract import ExtractError, file_format, read_pages


def make_pdf(*pages):
    """PDF kecil dengan teks asli. Halaman berisi None menjadi halaman tanpa teks."""
    objects = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font = 3 + 2 * len(pages)
    for index, text in enumerate(pages):
        content = 4 + 2 * index
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode()
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode() if text else b""
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return output.getvalue()


def make_pptx():
    presentation = Presentation()
    first = presentation.slides.add_slide(presentation.slide_layouts[1])
    first.shapes.title.text = "Judul Slide Satu"
    first.placeholders[1].text = "Isi poin pertama"
    first.notes_slide.notes_text_frame.text = "Jelaskan pelan-pelan"

    second = presentation.slides.add_slide(presentation.slide_layouts[6])
    table = second.shapes.add_table(1, 2, Inches(1), Inches(1), Inches(4), Inches(1)).table
    table.cell(0, 0).text = "Kolom A"
    table.cell(0, 1).text = "Kolom B"

    presentation.slides.add_slide(presentation.slide_layouts[6])

    output = io.BytesIO()
    presentation.save(output)
    return output.getvalue()


def make_docx(*paragraphs, table=None):
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    if table:
        cells = document.add_table(rows=1, cols=2).rows[0].cells
        cells[0].text, cells[1].text = table
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.mark.parametrize(
    "name, expected",
    [
        ("materi.pdf", "pdf"),
        ("MATERI.PDF", "pdf"),
        ("slide.pptx", "pptx"),
        ("tugas.docx", "docx"),
        ("catatan.txt", "text"),
        ("catatan.md", "text"),
        ("data.csv", "text"),
        ("index.html", "html"),
    ],
)
def test_file_format_recognizes_supported_files(name, expected):
    assert file_format(name) == expected


@pytest.mark.parametrize("name", ["lama.ppt", "lama.doc", "video.mp4", "tanpa-ekstensi"])
def test_file_format_rejects_unsupported_files(name):
    with pytest.raises(ExtractError) as error:
        file_format(name)
    assert "PDF" in str(error.value)


def test_pdf_reads_requested_pages_only():
    data = make_pdf("Halaman satu", "Halaman dua", "Halaman tiga")

    result = read_pages(data, "pdf", start_page=2, page_count=1)

    assert result["total_pages"] == 3
    assert result["start_page"] == 2
    assert result["end_page"] == 2
    assert result["next_start_page"] == 3
    assert "Halaman dua" in result["text"]
    assert "Halaman satu" not in result["text"]
    assert "--- Halaman 2 ---" in result["text"]


def test_last_page_has_no_next_page():
    result = read_pages(make_pdf("Satu", "Dua"), "pdf", start_page=1, page_count=10)

    assert result["end_page"] == 2
    assert result["next_start_page"] is None


def test_start_page_past_the_end_is_rejected():
    with pytest.raises(ExtractError) as error:
        read_pages(make_pdf("Satu"), "pdf", start_page=5, page_count=1)
    assert "1 halaman" in str(error.value)


def test_pdf_without_text_warns_about_scan():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)

    result = read_pages(output.getvalue(), "pdf", start_page=1, page_count=2)

    assert result["pages_without_text"] == [1, 2]
    assert "scan" in result["warning"]


def test_pdf_with_some_blank_pages_lists_them_without_warning():
    data = make_pdf("Isi halaman pertama yang cukup panjang untuk dibaca", None)

    result = read_pages(data, "pdf", start_page=1, page_count=2)

    assert result["pages_without_text"] == [2]
    assert "warning" not in result


def test_encrypted_pdf_explains_the_problem():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("rahasia")
    output = io.BytesIO()
    writer.write(output)

    with pytest.raises(ExtractError) as error:
        read_pages(output.getvalue(), "pdf", start_page=1, page_count=1)
    assert "password" in str(error.value)


@pytest.mark.parametrize("file_type", ["pdf", "pptx", "docx"])
def test_broken_file_gives_readable_error(file_type):
    with pytest.raises(ExtractError) as error:
        read_pages(b"bukan file asli", file_type, start_page=1, page_count=1)
    assert "tidak bisa dibaca" in str(error.value)


def test_pptx_reads_text_tables_and_notes():
    result = read_pages(make_pptx(), "pptx", start_page=1, page_count=3)

    assert result["total_pages"] == 3
    assert "Judul Slide Satu" in result["text"]
    assert "Isi poin pertama" in result["text"]
    assert "Catatan pembicara: Jelaskan pelan-pelan" in result["text"]
    assert "Kolom A | Kolom B" in result["text"]
    assert result["pages_without_text"] == [3]


def test_docx_keeps_document_order():
    data = make_docx("Paragraf pertama", table=("Sel A", "Sel B"))

    text = read_pages(data, "docx", start_page=1, page_count=1)["text"]

    assert text.index("Paragraf pertama") < text.index("Sel A | Sel B")


def test_long_docx_is_split_into_pages():
    paragraphs = [f"Paragraf {i} " + "kata " * 100 for i in range(40)]

    result = read_pages(make_docx(*paragraphs), "docx", start_page=1, page_count=1)

    assert result["total_pages"] > 1
    assert result["next_start_page"] == 2
    assert "Paragraf 0" in result["text"]
    assert "Paragraf 39" not in result["text"]


def test_text_file_with_invalid_bytes_still_reads():
    result = read_pages("héllo".encode("latin-1"), "text", start_page=1, page_count=1)
    assert "llo" in result["text"]


def test_html_removes_tags_and_scripts():
    data = b"<h1>Judul &amp; Sub</h1><script>jahat()</script><p>Isi</p><p>Lanjut</p>"

    text = read_pages(data, "html", start_page=1, page_count=1)["text"]

    assert "Judul & Sub" in text
    assert "jahat" not in text
    assert "<p>" not in text
    assert "Isi" in text


def test_empty_file_is_reported():
    with pytest.raises(ExtractError) as error:
        read_pages(b"   ", "text", start_page=1, page_count=1)
    assert "tidak berisi teks" in str(error.value)


def test_output_stops_before_exceeding_limit(monkeypatch):
    monkeypatch.setattr(extract, "MAX_TEXT_CHARS", 5000)
    monkeypatch.setattr(extract, "CHARS_PER_PAGE", 3000)
    data = "\n".join("baris " * 20 for _ in range(100)).encode()

    result = read_pages(data, "text", start_page=1, page_count=50)

    assert result["end_page"] == 1
    assert result["next_start_page"] == 2


def test_single_huge_page_is_truncated(monkeypatch):
    monkeypatch.setattr(extract, "MAX_TEXT_CHARS", 100)
    monkeypatch.setattr(extract, "CHARS_PER_PAGE", 1000)

    result = read_pages(b"x" * 500, "text", start_page=1, page_count=1)

    assert "dipotong" in result["warning"]
    assert len(result["text"]) < 200


def test_zip_bomb_is_rejected_before_parsing(monkeypatch):
    monkeypatch.setattr(extract, "MAX_UNZIPPED_BYTES", 1000)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * 5000)

    with pytest.raises(ExtractError) as error:
        read_pages(output.getvalue(), "docx", start_page=1, page_count=1)
    assert "terlalu besar" in str(error.value)
