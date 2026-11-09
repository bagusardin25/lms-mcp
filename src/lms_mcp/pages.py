"""Halaman HTML untuk login mode online.

Halaman ini sengaja tanpa JavaScript dan tanpa sumber dari luar, supaya sesuai dengan
Content-Security-Policy server. Semua nilai dari luar di-escape di modul ini.
"""

from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import urlsplit

_REPO_URL = "https://github.com/bagusardin25/lms-mcp"

_STYLE = """\
:root{color-scheme:light dark;--bg:#f2f6f7;--surface:#fff;--text:#14262c;--muted:#4a5f67;--line:#d5dfe2;--brand:#0f4c5c;--brand-strong:#0b3a47;--on-brand:#fff;--link:#0f5d70;--field:#fff;--field-line:#71868e;--soft:#e8f0f2;--error:#8f1d14;--error-bg:#fdf0ef;--error-line:#c0392b}
@media (prefers-color-scheme:dark){:root{--bg:#0e1719;--surface:#16242a;--text:#eaf1f3;--muted:#a9bbc1;--line:#2c3f46;--brand:#7fd3e3;--brand-strong:#a3e2ee;--on-brand:#06242b;--link:#8fd8e8;--field:#0f1b1f;--field-line:#6f8791;--soft:#1f3239;--error:#ffb4ab;--error-bg:#2d1614;--error-line:#e5786d}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:32rem;margin:0 auto;padding:1.25rem}
a{color:var(--link)}
code{font:.875em ui-monospace,Consolas,monospace;overflow-wrap:anywhere}
:focus-visible{outline:3px solid var(--brand);outline-offset:2px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1.5rem}
.brand{display:flex;align-items:center;gap:.625rem;margin-bottom:1.25rem}
.brand img{display:block;border-radius:9px}
.brand strong{font-size:.9375rem}
.badge{margin-left:auto;font-size:.75rem;font-weight:600;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:.125rem .625rem;white-space:nowrap}
h1{font-size:1.5rem;line-height:1.25;margin:0 0 .5rem;overflow-wrap:anywhere}
.lead{margin:0 0 .5rem;overflow-wrap:anywhere}
.quiet{margin:0;font-size:.875rem;color:var(--muted)}
.error{margin:1.25rem 0 0;padding:.625rem .875rem;background:var(--error-bg);color:var(--error);border-left:4px solid var(--error-line);border-radius:6px;font-weight:600}
.steps{list-style:none;margin:1.5rem 0 0;padding:0;counter-reset:step}
.steps>li{position:relative;counter-increment:step;padding:0 0 1.5rem 2.75rem}
.steps>li:last-child{padding-bottom:0}
.steps>li::before{content:counter(step);position:absolute;left:0;top:0;width:2rem;height:2rem;border-radius:50%;background:var(--brand);color:var(--on-brand);font-size:.9375rem;font-weight:700;display:grid;place-items:center}
.steps>li:not(:last-child)::after{content:"";position:absolute;left:calc(1rem - 1px);top:2.25rem;bottom:.25rem;width:2px;background:var(--line)}
.steps h2{font-size:1rem;line-height:2rem;margin:0}
.steps p{margin:0 0 .75rem;color:var(--muted)}
.button{display:inline-flex;align-items:center;justify-content:center;gap:.5rem;min-height:2.75rem;padding:.5rem 1rem;border-radius:10px;font:inherit;font-weight:600;text-decoration:none;cursor:pointer}
.secondary{background:var(--soft);color:var(--text);border:1px solid var(--line)}
.secondary:hover{border-color:var(--field-line)}
.primary{width:100%;margin-top:.75rem;background:var(--brand);color:var(--on-brand);border:0}
.primary:hover{background:var(--brand-strong)}
.hint{padding:.75rem;background:var(--soft);border-radius:10px;font-size:.8125rem}
.hint-link{color:var(--error);font-weight:600;text-decoration:underline}
.hint-menu{display:block;width:max-content;max-width:100%;margin:.5rem 0 0 1.25rem;padding:.375rem .75rem;background:var(--surface);border:1px solid var(--field-line);border-radius:8px;font-weight:600}
label{display:block}
textarea{display:block;width:100%;margin-top:.25rem;min-height:5.5rem;padding:.625rem .75rem;background:var(--field);color:var(--text);border:1px solid var(--field-line);border-radius:10px;font:.875rem/1.4 ui-monospace,Consolas,monospace;resize:vertical}
.more{margin-top:1.5rem;border-bottom:1px solid var(--line)}
details{border-top:1px solid var(--line);padding:.625rem 0}
summary{cursor:pointer;font-weight:600;padding:.25rem 0}
details p{margin:.5rem 0 0;font-size:.9375rem;color:var(--muted)}
.facts{display:grid;grid-template-columns:auto 1fr;gap:.25rem .875rem;margin:1rem 0 0;font-size:.9375rem}
.facts dt{color:var(--muted)}
.facts dd{margin:0;overflow-wrap:anywhere}
.notice{margin:1rem 0 0;padding:.625rem .875rem;background:var(--soft);border-left:4px solid var(--brand);border-radius:6px;font-size:.9375rem}
.check{display:flex;gap:.625rem;align-items:flex-start;margin-top:.875rem;font-weight:400}
.check input{margin-top:.3rem;width:1.125rem;height:1.125rem;flex:none}
.field{margin:1.25rem 0 0}
.after{margin-top:.875rem}
input[type=file]{display:block;width:100%;margin-top:.25rem;padding:.625rem;background:var(--field);color:var(--text);border:1px solid var(--field-line);border-radius:10px;font:inherit}
footer{margin-top:1rem;font-size:.8125rem;color:var(--muted)}
footer p{margin:0 0 .25rem}
@media (max-width:30rem){main{padding:0}.card{border:0;border-radius:0;min-height:100vh;padding:1.25rem}}"""

_EXTERNAL_ICON = (
    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" '
    'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M6 3H3v10h10v-3M9 3h4v4M13 3 7 9"/></svg>'
)


def _document(title: str, body: str, *, brand: str | None = None) -> str:
    return (
        '<!doctype html><html lang="id"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="icon" href="/favicon.ico">'
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><main><div class=\"card\">{_BRAND if brand is None else brand}{body}</div></main></body></html>"
    )


_BRAND = (
    '<div class="brand"><img src="/icon-64.png" width="36" height="36" alt="">'
    '<strong>LMS MCP</strong><span class="badge">Tidak resmi</span></div>'
)
# Halaman konfirmasi lokal tidak punya ikon, karena servernya hanya untuk satu klik.
_CONFIRM_BRAND = (
    '<div class="brand"><strong>LMS MCP</strong><span class="badge">Konfirmasi</span></div>'
)

_FOOTER = (
    "<footer><p>Proyek mahasiswa yang tidak resmi dan tidak berafiliasi dengan "
    "pihak kampus maupun pengelola LMS.</p>"
    "<p>Dibuat oleh Bagus Ardin Prayoga. "
    f'<a href="{_REPO_URL}" target="_blank" rel="noopener noreferrer">Lihat kode sumber</a></p>'
    "</footer>"
)


def message_page(message: str) -> str:
    return _document(
        "LMS MCP",
        f'<h1>Ada yang perlu diulang</h1><p class="lead">{escape(message)}</p>{_FOOTER}',
    )


def login_page(
    *,
    client: str,
    target: str,
    token_page: str,
    request: str,
    redirect_uri: str = "",
    loopback: bool = False,
    writes: bool = False,
    error: str = "",
) -> str:
    title = f"Hubungkan LMS ke {client}"
    client = escape(client)
    target = escape(target)
    error_block = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    redirect_block = ""
    if redirect_uri:
        redirect_block = (
            "<p>Alamat lengkap yang menerima kode login: "
            f"<code>{escape(redirect_uri)}</code></p>"
        )
    loopback_block = ""
    if loopback:
        loopback_block = (
            '<p class="notice">Alamat ini ada di komputermu sendiri. Lanjutkan hanya kalau '
            "kamu yang baru saja menjalankan aplikasi AI di komputer ini.</p>"
        )
    if writes:
        capability = (
            "Server ini mengizinkan pengumpulan tugas. AI hanya bisa membuat tautan. "
            "Kamu sendiri yang memilih file dan menekan tombol."
        )
    else:
        capability = (
            "Tool di server ini hanya membaca data, jadi AI belum bisa mengumpulkan tugas "
            "atau mengirim pesan."
        )
    return _document(
        title,
        f"""<h1>Hubungkan LMS ke {client}</h1>
<p class="lead">{client} akan bisa membaca mata kuliah, deadline, dan materimu. Data yang dibaca dikirim ke <code>{target}</code>.</p>
{redirect_block}
{loopback_block}
<p class="quiet">Kalau bukan kamu yang memulai proses ini, tutup saja halaman ini.</p>
{error_block}
<form method="post" action="login">
<input type="hidden" name="request" value="{escape(request, quote=True)}">
<ol class="steps">
<li><h2>Buka halaman token</h2>
<p>Login ke LMS kalau diminta.</p>
<a class="button secondary" href="{escape(token_page, quote=True)}" target="_blank" rel="noopener noreferrer">Buka di tab baru {_EXTERNAL_ICON}</a></li>
<li><h2>Salin tautannya</h2>
<p>Klik kanan tulisan merah, lalu pilih <strong>Copy link address</strong> (Salin alamat link). Di HP, tekan lama tulisannya.</p>
<div class="hint" aria-hidden="true"><span class="hint-link">Click here if the app does not open automatically.</span><span class="hint-menu">Copy link address</span></div></li>
<li><h2><label for="lms_link">Tempel tautannya di sini</label></h2>
<textarea id="lms_link" name="lms_link" rows="3" required autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="moodlemobile://token=..."></textarea>
<button class="button primary" type="submit">Hubungkan</button></li>
</ol>
</form>
<div class="more">
<details><summary>Ada kendala saat menyalin?</summary>
<p>Jangan diketik ulang atau disalin dari gambar, karena satu huruf yang berubah membuat token ditolak.</p>
<p>Kalau pilihannya tidak ada, tekan F12 di halaman token, buka tab Console, lalu jalankan <code>copy(document.getElementById('launchapp').href)</code>.</p>
<p>Kalau kamu memasang proyek ini sendiri, isi <code>LMS_TOKEN</code> dari file <code>.env</code> juga bisa dipakai.</p></details>
<details><summary>Apakah ini aman?</summary>
<p>Token setara akses penuh ke akun LMS-mu. {capability}</p>
<p>Server tidak punya database, dan token dienkripsi di dalam data login yang dipegang aplikasi AI. Tetap saja, pemilik server secara teknis bisa membacanya saat lewat, jadi tempel hanya kalau kamu percaya padanya.</p>
<p>Untuk memutus akses, reset token di halaman Security keys LMS.</p></details>
</div>
{_FOOTER}""",
    )


def _format_due(value: str | None) -> str:
    if not value:
        return "Tidak ada"
    return value[:16].replace("T", " ") + " WIB"


def _due_line(context: dict[str, Any]) -> str:
    text = context.get("due_text") or _format_due(context.get("due"))
    left = context.get("time_left")
    if left:
        return f"{text} ({left})"
    return text


def _size_text(size: int | None) -> str:
    if not size:
        return "Tidak diketahui"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


_STATUS_TEXT = {
    "belum_dikumpulkan": "belum dikumpulkan",
    "draft": "draft, belum terkirim ke dosen",
    "terkumpul": "sudah terkumpul",
    "dibuka_lagi": "dibuka lagi oleh dosen",
    "tanpa_pengumpulan_online": "tanpa pengumpulan online",
}


def _assignment_facts(context: dict[str, Any]) -> list[tuple[str, str]]:
    status = context.get("submission_status") or ""
    return [
        ("Mata kuliah", context.get("course") or "Tidak diketahui"),
        ("Bagian", context.get("section") or "Tidak muncul di daftar bagian"),
        ("Tugas", context["name"]),
        ("Tenggat", _due_line(context)),
        ("Status kiriman", _STATUS_TEXT.get(status, status or "Tidak diketahui")),
    ]


def _page_link(url: str) -> str:
    parsed = urlsplit(url or "")
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return (
            '<p class="quiet after">Bandingkan dengan '
            f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">'
            "halaman LMS</a> sebelum menekan tombol.</p>"
        )
    return ""


def action_confirm_page(
    *,
    title: str,
    lead: str,
    facts: list[tuple[str, str]],
    notices: list[str],
    checks: list[tuple[str, str]],
    allow_label: str,
    page_url: str = "",
) -> str:
    rows = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in facts
    )
    notes = "".join(f'<p class="notice">{escape(note)}</p>' for note in notices)
    boxes = "".join(
        '<label class="check">'
        f'<input type="checkbox" name="{escape(name, quote=True)}" value="yes" required>'
        f"<span>{escape(label)}</span></label>"
        for name, label in checks
    )
    return _document(
        title,
        f"""<h1>{escape(title)}</h1>
<p class="lead">{escape(lead)}</p>
<dl class="facts">{rows}</dl>
{notes}
{_page_link(page_url)}
<form method="post"><input type="hidden" name="decision" value="cancel">
<button class="button secondary" type="submit">Batalkan</button></form>
<form method="post"><input type="hidden" name="decision" value="allow">
{boxes}
<button class="button primary" type="submit">{escape(allow_label)}</button></form>
<p class="quiet after">AI tidak bisa menekan tombol ini. Kalau detailnya tidak sama dengan halaman LMS, batalkan.</p>""",
        brand=_CONFIRM_BRAND,
    )


def download_confirm_page(place: dict[str, Any], folder: str) -> str:
    notices = [
        "Detail ini diambil dari halaman mata kuliah, bukan dari perkiraan AI.",
    ]
    if place.get("stored_outside_lms"):
        notices.append("File ini tersimpan di luar LMS, jadi unduhan bisa gagal.")
    if place.get("hidden"):
        notices.append("Aktivitas ini sedang disembunyikan di halaman mata kuliah.")
    return action_confirm_page(
        title="Unduh file ini?",
        lead="File baru disimpan ke komputermu setelah kamu menekan tombol.",
        facts=[
            ("Mata kuliah", place["course"]),
            ("Status mata kuliah", place["course_status"]),
            ("Bagian", place["section"]),
            ("Aktivitas", place["activity"]),
            ("File", place["file_name"]),
            ("Ukuran", _size_text(place.get("size_bytes"))),
            ("Diubah", place.get("modified") or "Tidak diketahui"),
            ("Disimpan ke", folder),
        ],
        notices=notices,
        checks=[],
        allow_label="Unduh file ini",
        page_url=place.get("activity_url") or "",
    )


def save_confirm_page(context: dict[str, Any], file_path: str, size: int) -> str:
    rules = context["rules"]
    notices = ["Detail ini diambil dari halaman mata kuliah, bukan dari perkiraan AI."]
    checks: list[tuple[str, str]] = []
    existing = ", ".join(item["name"] for item in context["submitted_files"])
    if existing:
        checks.append(("replace", f"Ganti file yang sudah ada: {existing}"))
    if rules.team_submission:
        notices.append("Ini tugas kelompok, jadi kiriman berlaku untuk seluruh kelompok.")
    if rules.needs_final_submit:
        notices.append("File disimpan sebagai draft dulu dan belum terkirim ke dosen.")
        allow = "Simpan draft"
    else:
        notices.append("Tugas ini tidak punya tahap draft. File yang disetujui langsung terkumpul.")
        checks.append(("confirm_immediate", "Saya mengerti file ini langsung terkumpul."))
        allow = "Kumpulkan tugas"
    return action_confirm_page(
        title="Kumpulkan file ini?",
        lead="Tidak ada yang dikirim ke LMS sebelum kamu menekan tombol.",
        facts=[
            *_assignment_facts(context),
            ("File di komputer", file_path),
            ("Ukuran", _size_text(size)),
        ],
        notices=notices,
        checks=checks,
        allow_label=allow,
        page_url=context["url"],
    )


def submit_confirm_page(context: dict[str, Any]) -> str:
    rules = context["rules"]
    files = ", ".join(item["name"] for item in context["submitted_files"]) or "Tidak ada"
    notices = ["Setelah dikirim, kiriman bisa terkunci dan tidak bisa diubah lagi."]
    checks: list[tuple[str, str]] = []
    if rules.team_submission:
        notices.append("Ini tugas kelompok, jadi kiriman berlaku untuk seluruh kelompok.")
    if context.get("statement"):
        checks.append(("accept_statement", context["statement"]))
    return action_confirm_page(
        title="Kirim final ke dosen?",
        lead="Draft belum terkirim sebelum kamu menekan tombol.",
        facts=[*_assignment_facts(context), ("File yang akan dikirim", files)],
        notices=notices,
        checks=checks,
        allow_label="Kirim final ke dosen",
        page_url=context["url"],
    )


def _file_rules(rules: Any) -> str:
    types = ", ".join(rules.file_types) if rules.file_types else "semua format"
    if rules.max_bytes:
        return f"{types}, maksimal {rules.max_bytes / (1024 * 1024):g} MB"
    return types


def upload_form_page(*, context: dict[str, Any], request: str, error: str = "") -> str:
    rules = context["rules"]
    name = escape(context["name"])
    error_block = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    existing = ", ".join(item["name"] for item in context["submitted_files"])

    replace_block = ""
    if existing:
        replace_block = (
            '<label class="check"><input type="checkbox" name="replace" value="yes" required>'
            f"<span>Ganti file yang sudah ada: {escape(existing)}</span></label>"
        )
    team_block = ""
    if rules.team_submission:
        team_block = (
            '<p class="notice">Ini tugas kelompok, jadi kirimanmu berlaku untuk seluruh kelompok.</p>'
        )

    if rules.needs_final_submit:
        mode_block = (
            '<p class="notice">File disimpan sebagai draft dulu. '
            "Kamu bisa memeriksanya sebelum mengirim ke dosen.</p>"
        )
        button = "Simpan draft"
    else:
        mode_block = (
            '<p class="notice"><strong>Tugas ini tidak punya tahap draft.</strong> '
            "File yang kamu unggah langsung terkumpul.</p>"
            '<label class="check"><input type="checkbox" name="confirm_immediate" value="yes" required>'
            "<span>Saya mengerti file ini langsung terkumpul.</span></label>"
        )
        button = "Kumpulkan tugas"

    course = escape(context.get("course") or "Tidak diketahui")
    section = escape(context.get("section") or "Tidak muncul di daftar bagian")
    return _document(
        f"Unggah tugas: {context['name']}",
        f"""<h1>Unggah tugas</h1>
<dl class="facts"><dt>Mata kuliah</dt><dd>{course}</dd>
<dt>Bagian</dt><dd>{section}</dd>
<dt>Tugas</dt><dd>{name}</dd>
<dt>Tenggat</dt><dd>{escape(_due_line(context))}</dd>
<dt>Format</dt><dd>{escape(_file_rules(rules))}</dd></dl>
{team_block}
{error_block}
<form method="post" action="upload" enctype="multipart/form-data">
<input type="hidden" name="request" value="{escape(request, quote=True)}">
<input type="hidden" name="step" value="save">
<div class="field"><label for="file"><strong>Pilih file tugasmu</strong></label>
<input id="file" type="file" name="file" required></div>
{replace_block}
{mode_block}
<button class="button primary" type="submit">{button}</button>
</form>
<p class="quiet after">Isi tugas tetap tanggung jawabmu. Periksa hasilnya di <a href="{escape(context["url"], quote=True)}" target="_blank" rel="noopener noreferrer">halaman tugas LMS</a>.</p>
{_FOOTER}""",
    )


def upload_result_page(
    *, result: dict[str, Any], final_request: str | None, statement: str
) -> str:
    files = ", ".join(item["name"] for item in result["submitted_files"]) or "-"
    url = escape(result["url"], quote=True)
    note = f'<p class="notice">{escape(result["note"])}</p>' if result.get("note") else ""

    if final_request:
        statement_block = ""
        if statement:
            statement_block = (
                '<label class="check"><input type="checkbox" name="accept_statement" value="yes" required>'
                f"<span>{escape(statement)}</span></label>"
            )
        title = "Draft tersimpan"
        lead = "File sudah tersimpan, tapi <strong>belum terkirim ke dosen</strong>."
        action = f"""<form method="post" action="upload" enctype="multipart/form-data">
<input type="hidden" name="request" value="{escape(final_request, quote=True)}">
<input type="hidden" name="step" value="final">
{statement_block}
<p class="notice">Setelah dikirim, kiriman bisa terkunci dan tidak bisa diubah lagi.</p>
<button class="button primary" type="submit">Kirim final ke dosen</button>
</form>"""
    else:
        title = "Tugas terkumpul"
        lead = "LMS sudah mencatat kirimanmu."
        action = ""

    return _document(
        title,
        f"""<h1>{title}</h1>
<p class="lead">{lead}</p>
<dl class="facts"><dt>Tugas</dt><dd>{escape(result["assignment"])}</dd>
<dt>File</dt><dd>{escape(files)}</dd></dl>
{note}
{action}
<p class="quiet after">Pastikan sekali lagi di <a href="{url}" target="_blank" rel="noopener noreferrer">halaman tugas LMS</a>.</p>
{_FOOTER}""",
    )
