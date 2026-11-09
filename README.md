# lms-mcp

Bagus Ardin Prayoga

lms-mcp menghubungkan AI dengan LMS kampus kita. Lewat penghubung ini, kita bisa minta AI melihat mata kuliah, tenggat, dan materi, serta mengambil file, memakai akun kita sendiri.

Kita membuatnya sebagai mahasiswa, terpisah dari kampus dan pengelola LMS. Aturan kuliah tetap tanggung jawab kita.

## Pilih cara pakai

| Dipakai di | Cara | Perlu dipasang di internet? |
|---|---|---|
| Claude Code, Codex, Claude Desktop, Cursor, VS Code, Antigravity, atau AI di komputer seperti LM Studio | Di komputer kita | Tidak |
| claude.ai, ChatGPT, dan chat AI di situs web | Lewat situs | Ya |

Untuk akun kita sendiri, pakai cara di komputer. Kunci masuk tetap di komputer kita. Cara lewat situs hanya untuk AI yang dibuka di browser, dan hanya di server yang kita percaya.

## Yang bisa diminta ke AI

Nama di kolom kiri adalah nama yang AI pakai. Kita cukup memintanya dengan bahasa biasa.

| Nama | Kegunaan | Cara |
|---|---|---|
| `get_profile` | Siapa kita, dan apakah akun ini boleh mengunduh atau mengunggah file | Keduanya |
| `list_courses` | Daftar mata kuliah: yang sedang berjalan, yang sudah selesai, dan yang akan datang | Keduanya |
| `get_upcoming_deadlines` | Tenggat beberapa hari ke depan di semua mata kuliah, plus tugas yang terlambat dan belum dikumpulkan | Keduanya |
| `get_course_materials` | Isi satu mata kuliah per bagian: kegiatan, file, dan tautan luar | Keduanya |
| `read_file_text` | Membaca tulisan di dalam file, per halaman, supaya AI bisa merangkum atau menjawab pertanyaan | Keduanya |
| `get_file_link` | Membuat tautan supaya file dibuka di browser | Keduanya |
| `list_assignments` | Daftar tugas di satu mata kuliah, lengkap dengan tenggat, status, dan nilai | Keduanya |
| `get_assignment` | Detail satu tugas: perintah dosen, aturan file, yang sudah dikirim, dan komentar dosen | Keduanya |
| `download_file` | Mengunduh file ke komputer kita setelah kita menekan tombol di browser. Paling besar 200 MB | Di komputer |

Setiap jawaban yang ada tanggalnya juga menyertakan jam sekarang, tanggal lengkap dengan nama hari, dan sisa waktunya. AI jadi tidak perlu menebak hari ini atau menghitung sendiri, karena tebakan itu sering meleset. Tugas sisa salinan semester lalu, yang tenggatnya jauh sebelum mata kuliah dimulai, dipisahkan supaya tidak terlihat seperti tugas yang belum dikumpulkan. Daftar tenggat juga memeriksa tugas dan kuis yang tidak muncul di kalender karena sudah ditandai selesai, serta draf yang sudah diunggah tetapi belum dikirim ke dosen.

Secara bawaan, AI hanya boleh melihat. Mengumpulkan tugas dimatikan sampai kita menyalakannya sendiri, karena tugas gampang terkirim tanpa kita sadari, dan LMS mencatatnya atas nama kita. Mengirim pesan dan menulis di forum belum bisa.

### Mengumpulkan tugas

Fitur ini baru dicoba di LMS tiruan. Coba dulu di tugas latihan, bukan tugas yang dinilai. Untuk menyalakannya, isi `LMS_ENABLE_WRITE=1` di file pengaturan.

| Cara | Nama | Yang terjadi |
|---|---|---|
| Di komputer | `save_assignment_file`, `submit_assignment` | Halaman terbuka di browser. Kita yang menekan tombol |
| Lewat situs | `create_upload_link` | AI memberi tautan. Kita sendiri yang memilih file dan menekan tombol |

- **AI tidak menekan tombolnya sendiri.** Di komputer, halaman konfirmasi terbuka di browser. Halaman itu menampilkan mata kuliah, bagian, tugas, tenggat, dan file. Tidak ada yang terunggah sebelum kita menekan tombol.
- **Banyak tugas langsung terkumpul begitu file disimpan.** Tugas seperti ini tidak punya tahap simpan dulu. Halaman konfirmasi minta kita mencentang sebelum lanjut.
- **File lama tidak diganti diam-diam.** Kalau tugas sudah berisi file, halaman yang sama minta centang untuk menggantinya.
- **Di komputer, file tugas hanya boleh diambil dari tempat yang aman.** Tempatnya folder Dokumen, Unduhan, dan Desktop, kecuali kita mengubah `LMS_UPLOAD_DIRS`. File rahasia seperti `.env`, kunci masuk komputer, dan `credentials.json` ditolak. File yang di dalamnya ada kunci masuk LMS juga ditolak.
- **File yang baru diunduh dari LMS tidak bisa langsung dikumpulkan.** Salin dulu ke folder lain kalau memang itu tugas kita.
- **Lewat situs, tautan unggah berlaku 15 menit dan sekali pakai.** File diteruskan ke LMS dan tidak disimpan di server.
- **Isi tugas tetap tanggung jawab kita.** Yang diunggah hanya file yang kita pilih.

### Konfirmasi di browser

Mengunduh file, menyimpan file tugas, dan mengirim tugas ke dosen tidak langsung dijalankan AI. Di komputer, halaman terbuka di browser dan menunggu paling lama 3 menit. Halaman itu menampilkan mata kuliah, bagian (misalnya Minggu 3), kegiatan, dan berkasnya, sesuai yang tertulis di LMS. Tombolnya hanya bisa kita tekan. Kalau ditolak atau waktunya habis, tidak ada yang diunduh atau dikumpulkan.

Lewat situs, file tidak diunduh ke komputer. Mengumpulkan tugas tetap lewat halaman unggah, dan halaman itu juga menampilkan mata kuliah serta bagiannya.

### Batasan membaca file

`read_file_text` bisa membaca PDF, PowerPoint (PPTX), Word (DOCX), teks biasa, Markdown, CSV, dan HTML, sampai 50 MB. File tidak disimpan di server.

- **File di Office 365 tidak bisa dibaca dari sini.** Dosen kadang menaruh materi di Office 365 lalu menautkannya ke LMS. LMS menolak mengirim file seperti itu. File ini ditandai tersimpan di luar LMS. Buka lewat `get_file_link` di browser, lalu unggah sendiri ke AI kalau isinya perlu dibaca.
- **Gambar tidak terbaca.** PDF hasil scan hampir tidak punya tulisan. Gambar dan diagram di slide tidak ikut.
- **Beberapa format lama belum bisa,** termasuk Excel, PowerPoint lama (PPT), dan Word lama (DOC).
- **File yang bisa dijalankan tidak diunduh,** termasuk `.exe`, skrip, dan halaman `.html`. Buka lewat `get_file_link` kalau memang perlu.

## Ambil kunci masuk

LMS kita hanya bisa masuk lewat Office 365, jadi kunci masuknya kita ambil dari halaman yang biasa dipakai aplikasi HP Moodle.

1. Buka halaman kunci masuk LMS, lalu masuk kalau diminta. Di komputer, alamatnya muncul setelah menjalankan `uv run lms-mcp token` (lihat [Pakai di komputer](#pakai-di-komputer)). Lewat situs, halaman masuk server sudah menautkannya.
2. Klik kanan tautan "Click here if the app does not open automatically", lalu pilih "Copy link address".

Tautan itu harus sama persis, huruf demi huruf. Jangan diketik ulang dan jangan disalin dari gambar. Kalau ditolak, tekan `F12` di halaman itu, buka tab Console, lalu tempel perintah ini:

```
copy(document.getElementById('launchapp').href)
```

Kunci masuk ini sama saja dengan membuka akun LMS kita. Jangan dibagikan, jangan ditempel ke chat AI, dan jangan ikut di tangkapan layar.

Kunci ini punya masa berlaku yang diatur pengelola LMS. Bawaannya sekitar 12 minggu. Kalau sudah habis, AI membalas bahwa akses ditolak (`accessexception` atau `invalidtoken`). Ulangi langkah di atas.

## Pakai di komputer

Kita butuh [uv](https://docs.astral.sh/uv/), program untuk memasang proyek ini.

```bash
git clone https://github.com/bagusardin25/lms-mcp.git
cd lms-mcp
uv sync
```

Salin `.env.example` menjadi `.env`. Alamat halaman kunci masuk muncul dengan perintah di bawah. Simpan tautannya di luar folder proyek, misalnya di `~/.lms-mcp/token`, lalu isi lokasinya di `LMS_TOKEN_FILE`. Kalau `LMS_TOKEN` juga diisi, yang itu yang dipakai. Jangan tempel tautan itu ke chat AI, dan jangan bagikan chat yang sempat memuatnya. Kalau chat itu sudah terkirim, reset kunci di halaman Security keys LMS.

```bash
uv run lms-mcp token
```

File `.env` tidak ikut saat proyek ini diunggah ke GitHub. Setelah kunci masuk terisi, cek apakah LMS bisa dibuka:

```bash
uv run lms-mcp check
```

Ganti `/path/ke/lms-mcp` dengan lokasi folder proyek ini di komputer kita.

**Claude Code**

```bash
claude mcp add lms-mcp -- uv run --directory /path/ke/lms-mcp lms-mcp serve
```

**Codex**

```bash
codex mcp add lms-mcp -- uv run --directory /path/ke/lms-mcp lms-mcp serve
```

**Claude Desktop, Cursor, Antigravity, LM Studio, dan aplikasi lain yang memakai format `mcpServers`**

```json
{
  "mcpServers": {
    "lms-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/ke/lms-mcp", "lms-mcp", "serve"]
    }
  }
}
```

VS Code memakai format yang mirip di `mcp.json`, tetapi kuncinya `servers`.

Kalau aplikasinya tidak menemukan `uv`, isi `command` dengan lokasi lengkap program `uv` di komputer kita.

## Pakai lewat situs

### Pasang di internet

Di proyek ini sudah ada berkas untuk memasangnya di layanan seperti Railway. Server tidur sendiri setelah sekitar 5–10 menit tidak dipakai, jadi biayanya hampir nol saat menganggur. Saat ada yang memakai lagi, permintaan pertama butuh beberapa detik, dan sesekali gagal. Ulangi saja permintaan itu ke AI.

Isi pengaturan ini di layanan hosting:

| Nama | Artinya |
|---|---|
| `LMS_PUBLIC_URL` | Alamat server yang bisa dibuka orang, contoh `https://nama-server.up.railway.app` |
| `LMS_SERVER_SECRET` | Kata sandi rahasia server, minimal 32 huruf. Jangan diubah sembarangan, karena semua yang sudah tersambung harus masuk lagi |
| `LMS_EXTRA_REDIRECT_HOSTS` | Opsional. Alamat situs AI lain yang boleh disambungkan, dipisah koma. claude.ai dan ChatGPT sudah diizinkan |
| `LMS_ENABLE_WRITE` | Opsional. Isi `1` untuk menyalakan halaman unggah tugas |
| `LMS_TOKEN_GENERATION` | Opsional, mulai dari `0`. Naikkan angkanya lalu nyalakan ulang server untuk memutus semua yang sudah masuk |

Kata sandi rahasia server bisa dibuat dengan perintah ini:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Jangan isi `LMS_TOKEN` di hosting. Cara lewat situs tidak memakainya.

### Sambungkan ke chat AI

Alamat yang ditempel ke AI adalah `LMS_PUBLIC_URL` ditambah `/mcp`.

- **claude.ai:** buka Settings, Connectors, lalu Add custom connector.
- **ChatGPT:** nyalakan Developer Mode, lalu tambahkan di pengaturan Apps & Connectors. Tidak semua paket memilikinya.
- **Chat AI lain:** tambahkan alamat situsnya ke `LMS_EXTRA_REDIRECT_HOSTS`.

Saat menyambungkan, muncul halaman masuk. Tempel tautan kunci masuk di sana.

### Cara masuknya

Server ini tidak menyimpan daftar akun. Kunci masuk LMS dikunci dan disimpan di dalam izin yang dipegang aplikasi AI. Hanya server ini yang bisa membukanya, jadi tiap orang tetap memakai kunci masuknya sendiri.

Orang yang menjalankan server ini bisa melihat kunci masuk saat kita menempelkannya. Tempel hanya di server yang kita percaya, atau pakai cara di komputer. Untuk memutus akses sepenuhnya, reset kunci di halaman Security keys LMS.

Kalau server dimatikan lalu dinyalakan lagi, pemutusan yang baru saja dilakukan bisa hilang. Jalankan satu server saja. Untuk memutus semua yang masih tersambung di aplikasi AI, naikkan `LMS_TOKEN_GENERATION` lalu nyalakan ulang. Halaman masuk menampilkan alamat lengkap yang menerima izin, dan memperingatkan kalau alamat itu ada di komputer kita. Kalau pengumpulan tugas menyala, halaman itu juga mengatakannya.

## Hal yang perlu dijaga

- Isi LMS bisa ditulis siapa saja di kelas, termasuk kalimat yang mencoba menyuruh AI. Baca dulu sebelum menyetujui apa yang AI mau lakukan.
- Data LMS yang dibaca AI ikut terkirim ke perusahaan pembuat AI itu, kecuali AI-nya berjalan di komputer kita.
- Kunci masuk hanya dikirim ke LMS. Tautan unduhan dari situs lain ditolak.
- Semua yang kita lakukan tercatat di LMS atas nama akun kita.
- Unduh, unggah, kirim tugas, dan pembuatan tautan unggah juga dicatat di `~/.lms-mcp/audit.log`. Lokasinya bisa diganti lewat `LMS_AUDIT_LOG`. Catatan itu hanya memuat waktu, apa yang dilakukan, berhasil atau tidak, dan nama mata kuliah atau tugas. Kunci masuk dan isi file tidak ikut.
- Cukup sambungkan ke satu AI di komputer kita. AI yang bisa membuka folder proyek bisa membaca file pengaturan, jadi simpan kunci masuk lewat `LMS_TOKEN_FILE` di luar folder proyek, dan tambahkan `.env` ke `.cursorignore` sendiri.
- Orang yang memegang `LMS_SERVER_SECRET` tetap bisa membuka kunci masuk yang lewat di server. Kalau servernya lebih dari satu, pemutusan login tidak selalu sampai ke semuanya. Naikkan `LMS_TOKEN_GENERATION` untuk memutus semua sekaligus.

## Pengaturan di komputer

| Nama | Artinya |
|---|---|
| `LMS_TOKEN` | Tautan kunci masuk. Kalau diisi, ini yang dipakai |
| `LMS_TOKEN_FILE` | Opsional. Lokasi file kunci masuk di luar folder proyek, dipakai kalau `LMS_TOKEN` kosong |
| `LMS_DOWNLOAD_DIR` | Opsional. Folder tujuan unduhan. Bawaannya `Downloads/lms-mcp` |
| `LMS_AUDIT_LOG` | Opsional. Lokasi catatan. Bawaannya `~/.lms-mcp/audit.log` |
| `LMS_ENABLE_WRITE` | Opsional. Isi `1` untuk menyalakan pengumpulan tugas |
| `LMS_UPLOAD_DIRS` | Opsional. Folder asal file tugas, dipisah koma. Bawaannya Dokumen, Unduhan, dan Desktop |
| `LMS_BASE_URL` | Opsional. Alamat LMS. Kalau kosong, yang dipakai alamat LMS kampus kita |

Kalau nama yang sama juga diisi di pengaturan komputer, yang di komputer yang dipakai.

## Memeriksa proyek

```bash
uv run pytest
```

Perintah yang sama juga jalan di GitHub setiap ada perubahan yang diunggah.
