# lmstelkom-mcp

Bagus Ardin Prayoga

Kita buat MCP server ini untuk LMS Telkom University (Moodle). Dengan server ini, kita bisa meminta AI melihat mata kuliah, deadline, dan materi, serta mengambil file LMS memakai akun kita sendiri.

Kita membuatnya sebagai mahasiswa. Kita tidak berafiliasi dengan Telkom University atau CeLOE. Aturan akademik tetap tanggung jawab kita.

## Pilih mode

| Kita memakai | Mode | Perlu deploy? |
|---|---|---|
| Claude Code, Codex, Claude Desktop, Cursor, VS Code, Antigravity, AI lokal seperti LM Studio | Lokal (stdio) | Tidak |
| claude.ai, ChatGPT, dan AI chat web lain yang mendukung custom MCP | Online (HTTP) | Ya |

Untuk akun kita sendiri, kita pakai mode lokal. Token tetap di komputer kita. Mode online hanya untuk AI yang berjalan di web, dan hanya di server yang kita percaya.

## Tool yang tersedia

| Tool | Fungsi | Mode |
|---|---|---|
| `get_profile` | Profil dan izin unduh serta upload file | Keduanya |
| `list_courses` | Mata kuliah berjalan, selesai, atau akan datang | Keduanya |
| `get_upcoming_deadlines` | Aktivitas yang belum selesai dan jatuh tempo dalam sekian hari | Keduanya |
| `get_course_materials` | Isi mata kuliah per bagian: aktivitas, file, dan link luar | Keduanya |
| `read_file_text` | Membaca teks file per halaman, untuk merangkum atau menjawab pertanyaan | Keduanya |
| `get_file_link` | Membuat tautan file untuk dibuka di browser | Keduanya |
| `download_file` | Mengunduh file LMS ke komputer kita, maksimal 200 MB | Lokal |

Semua tool hanya membaca data LMS, jadi kita belum bisa mengumpulkan tugas atau mengirim pesan lewat server ini. Ini sengaja. Mengumpulkan tugas lewat AI mudah terjadi tanpa kita sengaja, dan aksinya tercatat di LMS atas nama akun kita.

### Batasan membaca file

`read_file_text` mendukung PDF, PPTX, DOCX, TXT, MD, CSV, dan HTML sampai 50 MB, tanpa menyimpan file di server.

- **File di Office 365 tidak bisa kita baca.** Dosen bisa menaruh materi di Office 365 lalu menautkannya ke LMS, dan Moodle menolak mengirim file seperti ini lewat token. File ini kita tandai `stored_outside_lms`. Kita buka lewat `get_file_link` di browser, lalu kita unggah filenya ke AI kalau isinya perlu kita baca.
- **Gambar tidak terbaca.** PDF hasil scan hampir tidak menghasilkan teks, dan gambar serta diagram di slide tidak ikut.
- **Format lain belum kita dukung,** termasuk XLSX, PPT, dan DOC versi lama.

## Ambil token

LMS kita hanya bisa login lewat Office365, jadi kita ambil token lewat alur SSO aplikasi mobile Moodle.

1. Kita buka [halaman token](https://lms.telkomuniversity.ac.id/admin/tool/mobile/launch.php?service=moodle_mobile_app&passport=1&urlscheme=moodlemobile&confirmed=1), lalu login kalau diminta.
2. Kita klik kanan tautan "Click here if the app does not open automatically", lalu pilih "Copy link address".

Tautan harus sama persis sampai ke tiap huruf, jadi jangan kita ketik ulang atau kita baca dari gambar. Kalau ditolak, kita tekan `F12` di halaman token, lalu jalankan ini di tab Console untuk menyalinnya:

```
copy(document.getElementById('launchapp').href)
```

Token ini setara akses penuh ke akun LMS kita, jadi jangan kita bagikan atau kita kirim ke chat AI, termasuk lewat screenshot.

Token punya masa berlaku yang diatur admin LMS, dengan default Moodle 12 minggu. Kalau sudah habis, tool membalas error `accessexception` atau `invalidtoken`, lalu kita ulangi langkah di atas.

## Mode lokal

Kita butuh [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/bagusardin25/mcp-lmstelkom.git
cd mcp-lmstelkom
uv sync
```

Kita salin `.env.example` menjadi `.env`, lalu tempel tautan token setelah `LMS_TOKEN=`. File `.env` tidak kita ikutkan di commit. Setelah itu kita uji aksesnya:

```bash
uv run lms-mcp check
```

Kita ganti `/path/ke/mcp-lmstelkom` dengan lokasi folder proyek ini.

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

Kalau `uv` tidak ditemukan oleh aplikasinya, kita isi `command` dengan lokasi lengkap `uv`.

## Mode online

### Deploy

Di repo ini ada `Dockerfile`, jadi kita bisa menjalankannya di hosting apa pun yang mendukung container. `railway.json` sudah kita siapkan untuk Railway.

Kita isi variabel ini di pengaturan hosting:

| Variabel | Keterangan |
|---|---|
| `LMS_PUBLIC_URL` | Alamat publik server, contoh `https://nama-server.up.railway.app` |
| `LMS_SERVER_SECRET` | Kunci enkripsi acak, minimal 32 karakter |
| `LMS_EXTRA_REDIRECT_HOSTS` | Opsional, host klien tambahan yang kita izinkan, dipisah koma |

Kita buat `LMS_SERVER_SECRET` dengan perintah ini, dan jangan pernah kita ubah tanpa alasan, karena kita yang sudah tersambung akan perlu login ulang:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Jangan kita isi `LMS_TOKEN` di hosting, karena mode online tidak memakainya.

### Sambungkan ke AI chat

Alamat connector kita adalah `LMS_PUBLIC_URL` ditambah `/mcp`.

- **claude.ai:** kita buka Settings, Connectors, lalu Add custom connector.
- **ChatGPT:** kita aktifkan Developer Mode, lalu tambahkan connector di pengaturan Apps & Connectors. Ketersediaannya tergantung paket.
- **AI chat lain:** kita tambahkan host callback-nya ke `LMS_EXTRA_REDIRECT_HOSTS`. Hanya claude.ai dan ChatGPT yang kita izinkan secara default.

Saat kita menyambungkan, muncul halaman login server ini. Kita tempel tautan token di sana.

### Cara kerja login

Server ini tidak kita beri database. Token LMS kita enkripsi dan simpan di dalam access token yang dipegang aplikasi AI, dan hanya server yang bisa membukanya. Karena itu tiap akun tetap memakai tokennya sendiri.

Kita yang menjalankan server secara teknis bisa membaca token yang lewat. Karena itu kita tempel token hanya di server yang kita percaya, atau kita pakai mode lokal. Untuk memutus akses sepenuhnya, kita reset token di halaman Security keys LMS.

## Keamanan

- Isi LMS bisa ditulis siapa saja di kelas kita, termasuk teks yang mencoba memberi perintah ke AI. Kita periksa dulu aksi AI sebelum menyetujuinya.
- Data LMS yang kita baca lewat AI ikut terkirim ke penyedia model AI, kecuali kalau kita memakai model lokal.
- Token hanya kita kirim ke LMS, dan URL unduhan ke server lain kita tolak.
- Semua aksi tercatat di log LMS atas nama akun kita.

## Konfigurasi mode lokal

| Variabel | Keterangan |
|---|---|
| `LMS_TOKEN` | Tautan `moodlemobile://token=...` atau token web service |
| `LMS_DOWNLOAD_DIR` | Opsional, default folder `Downloads/lms-telkom` |
| `LMS_BASE_URL` | Opsional, default `https://lms.telkomuniversity.ac.id` |

Variabel environment mengalahkan nilai yang kita tulis di `.env`.

## Tes

```bash
uv run pytest
```

Perintah yang sama juga kita jalankan di GitHub pada setiap push dan pull request.
