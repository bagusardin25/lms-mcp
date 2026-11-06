# lmstelkom-mcp

Bagus Ardin Prayoga

MCP server untuk LMS Telkom University (Moodle). AI bisa melihat mata kuliah, deadline, dan materi, serta mengambil file LMS memakai akunmu sendiri.

Ini proyek mahasiswa yang **tidak resmi** dan tidak berafiliasi dengan Telkom University atau CeLOE. Aturan akademik tetap tanggung jawab masing-masing pengguna.

## Pilih mode

| Kamu memakai | Mode | Perlu deploy? |
|---|---|---|
| Claude Code, Codex, Claude Desktop, Cursor, VS Code, Antigravity, AI lokal seperti LM Studio | Lokal (stdio) | Tidak |
| claude.ai, ChatGPT, dan AI chat web lain yang mendukung custom MCP | Online (HTTP) | Ya |

Untuk akunmu sendiri, pakai mode lokal. Token tetap di komputermu. Mode online hanya untuk AI yang berjalan di web, dan hanya di server yang kamu percaya.

## Tool yang tersedia

| Tool | Fungsi | Mode |
|---|---|---|
| `get_profile` | Profil dan izin unduh serta upload file | Keduanya |
| `list_courses` | Mata kuliah berjalan, selesai, atau akan datang | Keduanya |
| `get_upcoming_deadlines` | Aktivitas yang belum selesai dan jatuh tempo dalam sekian hari | Keduanya |
| `get_course_materials` | Isi mata kuliah per bagian: aktivitas, file, dan link luar | Keduanya |
| `read_file_text` | Membaca teks file per halaman, untuk merangkum atau menjawab pertanyaan | Keduanya |
| `get_file_link` | Membuat tautan file untuk dibuka di browser | Keduanya |
| `download_file` | Mengunduh file LMS ke komputermu, maksimal 200 MB | Lokal |

Semua tool hanya membaca data LMS, jadi belum ada yang bisa mengumpulkan tugas atau mengirim pesan. Ini sengaja. Mengumpulkan tugas lewat AI mudah terjadi tanpa sengaja, dan aksinya tercatat di LMS atas nama akunmu.

### Batasan membaca file

`read_file_text` mendukung PDF, PPTX, DOCX, TXT, MD, CSV, dan HTML sampai 50 MB, tanpa menyimpan file di server.

- **File di Office 365 tidak bisa dibaca.** Dosen bisa menaruh materi di Office 365 lalu menautkannya ke LMS, dan Moodle menolak mengirim file seperti ini lewat token. File ini ditandai `stored_outside_lms`. Buka lewat `get_file_link` di browser, lalu unggah filenya ke AI kalau isinya perlu dibaca.
- **Gambar tidak terbaca.** PDF hasil scan hampir tidak menghasilkan teks, dan gambar serta diagram di slide tidak ikut.
- **Format lain belum didukung,** termasuk XLSX, PPT, dan DOC versi lama.

## Ambil token

LMS hanya bisa login lewat Office365, jadi token diambil lewat alur SSO aplikasi mobile Moodle.

1. Buka [halaman token](https://lms.telkomuniversity.ac.id/admin/tool/mobile/launch.php?service=moodle_mobile_app&passport=1&urlscheme=moodlemobile&confirmed=1), lalu login kalau diminta.
2. Klik kanan tautan "Click here if the app does not open automatically", lalu pilih "Copy link address".

Tautan harus sama persis sampai ke tiap huruf, jadi jangan diketik ulang atau dibaca dari gambar. Kalau ditolak, tekan `F12` di halaman token, lalu jalankan ini di tab Console untuk menyalinnya:

```
copy(document.getElementById('launchapp').href)
```

Token ini setara akses penuh ke akun LMS, jadi jangan dibagikan atau dikirim ke chat AI, termasuk lewat screenshot.

Token punya masa berlaku yang diatur admin LMS, dengan default Moodle 12 minggu. Kalau sudah habis, tool akan membalas error `accessexception` atau `invalidtoken`, lalu ulangi langkah di atas.

## Mode lokal

Butuh [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/bagusardin25/mcp-lmstelkom.git
cd mcp-lmstelkom
uv sync
```

Salin `.env.example` menjadi `.env`, lalu tempel tautan token setelah `LMS_TOKEN=`. File `.env` tidak ikut di-commit. Setelah itu uji aksesnya:

```bash
uv run lms-mcp check
```

Ganti `/path/ke/mcp-lmstelkom` dengan lokasi folder proyek ini.

**Claude Code**

```bash
claude mcp add lms-telkom -- uv run --directory /path/ke/mcp-lmstelkom lms-mcp serve
```

**Codex**

```bash
codex mcp add lms-telkom -- uv run --directory /path/ke/mcp-lmstelkom lms-mcp serve
```

**Claude Desktop, Cursor, Antigravity, LM Studio, dan client lain yang memakai format `mcpServers`**

```json
{
  "mcpServers": {
    "lms-telkom": {
      "command": "uv",
      "args": ["run", "--directory", "/path/ke/mcp-lmstelkom", "lms-mcp", "serve"]
    }
  }
}
```

VS Code memakai format yang mirip di `mcp.json`, tapi kuncinya `servers`, bukan `mcpServers`.

Kalau `uv` tidak ditemukan oleh aplikasinya, isi `command` dengan lokasi lengkap `uv`.

## Mode online

### Deploy

Repo ini berisi `Dockerfile`, jadi bisa dijalankan di hosting apa pun yang mendukung container. `railway.json` sudah disiapkan untuk Railway.

Isi variabel ini di pengaturan hosting:

| Variabel | Keterangan |
|---|---|
| `LMS_PUBLIC_URL` | Alamat publik server, contoh `https://nama-server.up.railway.app` |
| `LMS_SERVER_SECRET` | Kunci enkripsi acak, minimal 32 karakter |
| `LMS_EXTRA_REDIRECT_HOSTS` | Opsional, host klien tambahan yang diizinkan, dipisah koma |

Buat `LMS_SERVER_SECRET` dengan perintah ini, dan jangan pernah mengubahnya tanpa alasan, karena semua pengguna akan perlu login ulang:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Jangan isi `LMS_TOKEN` di hosting, karena mode online tidak memakainya.

### Sambungkan ke AI chat

Alamat connector-nya adalah `LMS_PUBLIC_URL` ditambah `/mcp`.

- **claude.ai:** Settings, Connectors, lalu Add custom connector.
- **ChatGPT:** aktifkan Developer Mode, lalu tambahkan connector di pengaturan Apps & Connectors. Ketersediaannya tergantung paket.
- **AI chat lain:** tambahkan host callback-nya ke `LMS_EXTRA_REDIRECT_HOSTS`. Hanya claude.ai dan ChatGPT yang diizinkan secara default.

Saat menyambungkan, akan muncul halaman login server ini. Tempel tautan token di sana.

### Cara kerja login

Server tidak punya database. Token LMS dienkripsi dan disimpan di dalam access token yang dipegang aplikasi AI, dan hanya server yang bisa membukanya. Karena itu, tiap orang otomatis memakai akunnya sendiri.

Tetap saja, pemilik server secara teknis bisa membaca token yang lewat. Tempel token hanya di server milik orang yang kamu percaya, atau pakai mode lokal. Untuk memutus akses sepenuhnya, reset token di halaman Security keys LMS.

## Keamanan

- Isi LMS bisa ditulis siapa saja di kelasmu, termasuk teks yang mencoba memberi perintah ke AI. Periksa dulu aksi AI sebelum menyetujuinya.
- Data LMS yang dibaca AI ikut terkirim ke penyedia model AI, kecuali kalau memakai model lokal.
- Token hanya dikirim ke LMS, dan URL unduhan ke server lain ditolak.
- Semua aksi tercatat di log LMS atas nama akunmu.

## Konfigurasi mode lokal

| Variabel | Keterangan |
|---|---|
| `LMS_TOKEN` | Tautan `moodlemobile://token=...` atau token web service |
| `LMS_DOWNLOAD_DIR` | Opsional, default folder `Downloads/lms-telkom` |
| `LMS_BASE_URL` | Opsional, default `https://lms.telkomuniversity.ac.id` |

Variabel environment mengalahkan nilai di `.env`.

## Tes

```bash
uv run pytest
```

Perintah yang sama juga berjalan di GitHub pada setiap push dan pull request.
