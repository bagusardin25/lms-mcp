# lms-mcp

lms-mcp menghubungkan AI dengan LMS kampus kita. Lewat penghubung ini, kita bisa minta AI melihat mata kuliah, tenggat, dan materi, serta mengambil file, memakai akun kita sendiri.

Kita membuatnya sebagai mahasiswa, terpisah dari kampus dan pengelola LMS. Aturan kuliah tetap tanggung jawab kita.

![Contoh di claude.ai: AI menyebutkan tujuh mata kuliah yang sedang berjalan beserta progresnya](docs/images/contoh-claude.png)

Contoh di claude.ai. Alamat LMS di jawaban AI sengaja ditutup.

## Pilih cara pakai

| Cara | Dipakai di | Yang perlu disiapkan |
|---|---|---|
| [Lewat situs](#pakai-lewat-situs) | claude.ai, ChatGPT, dan Grok | Tidak ada. Servernya sudah jalan, tinggal sambungkan |
| [Di komputer](#pakai-di-komputer) | Claude Code, Codex, Claude Desktop, Cursor, VS Code, Antigravity, atau AI di komputer seperti LM Studio | Memasang proyek ini di komputer kita |

Lewat situs adalah cara yang paling cepat. Kunci masuk kita lewat server yang dijalankan pembuat proyek ini. Kalau dipakai di komputer, kunci masuk tetap di komputer kita.

## Pakai lewat situs

Server untuk teman-teman sudah jalan. Tidak perlu memasang apa pun. Yang dibutuhkan hanya browser, akun LMS, dan akun di claude.ai, ChatGPT, atau Grok.

Alamat server yang ditempel ke aplikasi AI:

```
https://lms-mcp.up.railway.app/mcp
```

Sebelum menyambungkan, baca [PRIVASI.md](PRIVASI.md). Isinya data apa saja yang dibaca dari LMS, apa yang disimpan, siapa yang bisa melihat kunci masuk, dan cara memutus akses.

### 1. Tambahkan alamat server ke aplikasi AI

- **claude.ai:** buka Customize, lalu Connectors. Klik "+ Add", pilih "Add custom connector", isi nama, lalu tempel alamat di atas. Akun gratis hanya boleh punya satu sambungan buatan sendiri. [Panduan resmi claude.ai](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).
- **ChatGPT:** buka [chatgpt.com/plugins](https://chatgpt.com/plugins), klik tombol plus, lalu pilih "Add custom MCP server". Isi nama, pilih Public endpoint, tempel alamat di atas, lalu lanjutkan sampai "Create as a plugin". Tidak semua akun punya menu ini. [Panduan resmi ChatGPT](https://developers.openai.com/plugins/deploy/connect-chatgpt).
- **Grok:** buka [grok.com/connectors](https://grok.com/connectors), klik "New Connector", pilih "Custom", lalu tempel alamat di atas. [Panduan resmi Grok](https://docs.x.ai/grok/connectors).

Menu di ketiga aplikasi itu sering berubah. Kalau tampilannya berbeda, ikuti panduan resminya.

### 2. Tempel kunci masuk di halaman server

Setelah alamat ditambahkan, aplikasi AI membuka halaman server ini di browser. Judulnya "Hubungkan LMS ke", diikuti nama aplikasi AI-nya. Halaman itu menjelaskan siapa yang menjalankan server ini, dan apa yang AI boleh lakukan.

![Halaman yang muncul saat menyambungkan: penjelasan server, lalu tiga langkah menempel kunci masuk](docs/images/login-server.png)

Di halaman itu ada tiga langkah:

1. **Buka halaman token.** Klik "Buka di tab baru". Halaman LMS terbuka di tab lain. Masuk ke LMS kalau diminta.
2. **Salin tautannya.** Di halaman LMS itu, klik kanan tulisan merah "Click here if the app does not open automatically", lalu pilih "Copy link address". Di HP, tekan lama tulisannya. Jangan diklik biasa, karena yang kita butuhkan adalah alamat tautannya.
3. **Tempel tautannya.** Kembali ke tab halaman server, tempel di kotak yang tersedia, lalu klik "Hubungkan".

![Halaman kunci masuk LMS: klik kanan tautan merah, lalu pilih Copy link address](docs/images/salin-kunci.png)

Kalau berhasil, browser kembali ke aplikasi AI, dan lms-mcp tercatat sudah tersambung. Halaman server ini berlaku 10 menit. Kalau terlewat, ulangi dari aplikasi AI.

Tautan yang disalin itu adalah kunci masuk LMS kita. Jangan dibagikan. Jangan ditempel ke chat AI. Penjelasan lengkapnya ada di bagian [Ambil kunci masuk](#ambil-kunci-masuk).

### 3. Nyalakan di chat, lalu coba bertanya

Di claude.ai, sambungan dinyalakan per chat: klik tombol "+" di kotak chat, pilih Connectors, lalu nyalakan lms-mcp. Untuk ChatGPT dan Grok, caranya ada di panduan resmi masing-masing.

Setelah itu tanyakan dengan bahasa biasa. Contohnya:

- "Mata kuliah apa saja yang saya ambil semester ini?"
- "Tugas apa yang tenggatnya minggu ini? Ada yang terlambat?"
- "Tampilkan materi minggu 3 mata kuliah Basis Data."
- "Rangkum isi slide minggu 3 itu."
- "Tugas mana di mata kuliah itu yang belum saya kumpulkan? Apa perintah dosennya?"

Saat AI pertama kali memakai lms-mcp, aplikasi AI biasanya meminta izin dulu. Izinkan supaya AI bisa membaca LMS.

### Kondisi server sekarang

- AI hanya bisa melihat mata kuliah, tenggat, materi, dan tugas beserta nilai dan komentar dosen. Mengumpulkan tugas, mengirim pesan, dan menulis di forum tidak bisa dilakukan dari server ini.
- Tiap orang memakai kunci masuknya sendiri. Server tidak menyimpan daftar akun. Orang lain tidak bisa membuka LMS kita selama mereka tidak memegang kunci masuk kita.
- Server tidur kalau sekitar 5–10 menit tidak ada yang memakai. Permintaan pertama setelah itu kadang gagal. Ulangi saja ke AI.
- Server tidak menyimpan file yang dibaca.
- Orang yang menjalankan server ini bisa melihat kunci masuk saat teman menempelkannya. Server harus memakai kunci itu untuk bertanya ke LMS. Teman yang tidak nyaman sebaiknya memakai cara di komputer.
- Data yang AI baca juga terkirim ke perusahaan AI yang dipakai, misalnya Claude, ChatGPT, atau Grok.
- Tulisan di LMS bisa berisi kalimat yang mencoba menyuruh AI. Baca dulu sebelum menyetujui.

### Kalau ada masalah

| Yang terjadi | Artinya | Yang dilakukan |
|---|---|---|
| Halaman server menulis "Token tidak terbaca" | Tautannya tidak tersalin utuh | Salin ulang lewat "Copy link address". Jangan diketik ulang |
| Halaman server menulis "LMS menolak token ini" | Kunci masuk sudah di-reset, atau masa berlakunya habis | Buka lagi halaman token, lalu salin tautan yang baru |
| Halaman server menulis "Permintaan login ini sudah tidak berlaku" | Halaman dibiarkan lebih dari 10 menit | Ulangi dari aplikasi AI |
| Halaman server menulis "Terlalu banyak percobaan" | Terlalu banyak yang mencoba masuk dalam satu menit | Tunggu satu menit, lalu coba lagi |
| Halaman server menulis "LMS tidak bisa dihubungi" | LMS sedang lambat atau mati | Coba lagi beberapa menit kemudian |
| Jawaban pertama AI gagal, atau AI bilang server tidak bisa dihubungi | Server sedang tidur | Ulangi permintaannya ke AI |
| AI bilang akses ditolak (`invalidtoken` atau `accessexception`) | Masa berlaku kunci masuk habis. Biasanya sekitar 12 minggu | Sambungkan ulang dari aplikasi AI, lalu tempel kunci masuk yang baru |
| AI menjawab tanpa membuka LMS | Sambungan belum dinyalakan di chat itu | Nyalakan lms-mcp di kotak chat |

### Memutus akses

1. Hapus sambungan lms-mcp di aplikasi AI.
2. Reset kunci masuk di LMS: klik foto profil di kanan atas, pilih Preferences, lalu Security keys. Reset kunci untuk aplikasi HP Moodle. Semua kunci lama langsung tidak berlaku, termasuk izin yang tersimpan di aplikasi AI.

Penjelasan lengkapnya ada di [PRIVASI.md](PRIVASI.md#cara-memutus-akses).

## Yang bisa diminta ke AI

Nama di kolom kiri adalah nama yang AI pakai. Kita cukup memintanya dengan bahasa biasa.

| Nama | Kegunaan | Cara |
|---|---|---|
| `get_profile` | Siapa kita, dan apakah akun ini boleh mengunduh atau mengunggah file | Keduanya |
| `list_courses` | Daftar mata kuliah: yang sedang berjalan, yang sudah selesai, dan yang akan datang | Keduanya |
| `get_upcoming_deadlines` | Tenggat beberapa hari ke depan di semua mata kuliah, ditambah tugas yang terlambat dan belum dikumpulkan | Keduanya |
| `get_course_materials` | Isi satu mata kuliah per bagian: kegiatan, file, dan tautan luar | Keduanya |
| `read_file_text` | Membaca tulisan di dalam file, per halaman, supaya AI bisa merangkum atau menjawab pertanyaan | Keduanya |
| `get_file_link` | Membuat tautan supaya file dibuka di browser | Keduanya |
| `list_assignments` | Daftar tugas di satu mata kuliah, lengkap dengan tenggat, status, dan nilai | Keduanya |
| `get_assignment` | Detail satu tugas: perintah dosen, aturan file, yang sudah dikirim, dan komentar dosen | Keduanya |
| `download_file` | Mengunduh file ke komputer kita setelah kita menekan tombol di browser. Paling besar 200 MB | Di komputer |

Setiap jawaban yang ada tanggalnya juga menyertakan jam sekarang, tanggal lengkap dengan nama hari, dan sisa waktunya. AI jadi tidak perlu menebak hari ini. Tebakan seperti itu sering meleset.

Tugas sisa salinan semester lalu dipisahkan. Tenggatnya jauh sebelum mata kuliah dimulai, jadi tidak terlihat seperti tugas yang belum dikumpulkan. Daftar tenggat juga memeriksa tugas dan kuis yang tidak muncul di kalender karena sudah ditandai selesai, serta draf yang sudah diunggah tetapi belum dikirim ke dosen.

Dari awal, AI hanya bisa melihat. Mengumpulkan tugas dimatikan sampai kita menyalakannya sendiri. Tugas gampang terkirim tanpa kita sadari, dan LMS mencatatnya atas nama kita. Mengirim pesan dan menulis di forum belum bisa.

### Mengumpulkan tugas

Fitur ini baru dicoba di LMS tiruan. Mulai dari tugas latihan dulu. Untuk menyalakannya, isi `LMS_ENABLE_WRITE=1` di file pengaturan.

| Cara | Nama | Yang terjadi |
|---|---|---|
| Di komputer | `save_assignment_file`, `submit_assignment` | Halaman terbuka di browser. Kita yang menekan tombol |
| Lewat situs | `create_upload_link` | AI memberi tautan. Kita sendiri yang memilih file dan menekan tombol |

- **AI tidak menekan tombolnya sendiri.** Di komputer, halaman konfirmasi terbuka di browser. Halaman itu menampilkan mata kuliah, bagian, tugas, tenggat, dan file. Tidak ada yang terunggah sebelum kita menekan tombol.
- **Banyak tugas langsung terkumpul begitu file disimpan.** Tugas seperti ini tidak punya tahap simpan dulu. Halaman konfirmasi minta kita mencentang sebelum lanjut.
- **File lama tidak diganti diam-diam.** Kalau tugas sudah berisi file, halaman yang sama minta centang untuk menggantinya.
- **Di komputer, file tugas hanya boleh diambil dari tempat yang aman.** Tempatnya folder Dokumen, Unduhan, dan Desktop. Kita bisa mengubahnya lewat `LMS_UPLOAD_DIRS`. File rahasia seperti `.env`, kunci masuk komputer, dan `credentials.json` ditolak. File yang di dalamnya ada kunci masuk LMS juga ditolak.
- **File yang baru diunduh dari LMS tidak bisa langsung dikumpulkan.** Salin dulu ke folder lain kalau memang itu tugas kita.
- **Lewat situs, tautan unggah berlaku 15 menit dan sekali pakai.** File diteruskan ke LMS. Server tidak menyimpannya.
- **Isi tugas tetap tanggung jawab kita.** Yang diunggah hanya file yang kita pilih.

### Konfirmasi di browser

Mengunduh file, menyimpan file tugas, dan mengirim tugas ke dosen menunggu kita. Di komputer, halaman terbuka di browser dan menunggu paling lama 3 menit. Halaman itu menampilkan mata kuliah, bagian (misalnya Minggu 3), kegiatan, dan berkasnya, sesuai yang tertulis di LMS. Tombolnya hanya bisa kita tekan. Kalau ditolak atau waktunya habis, tidak ada yang diunduh atau dikumpulkan.

Lewat situs, file tidak diunduh ke komputer. Mengumpulkan tugas tetap lewat halaman unggah. Halaman itu juga menampilkan mata kuliah serta bagiannya.

### Batasan membaca file

`read_file_text` bisa membaca PDF, PowerPoint (PPTX), Word (DOCX), teks biasa, Markdown, CSV, dan HTML, sampai 50 MB. File tidak disimpan di server.

- **File di Office 365 tidak bisa dibaca dari sini.** Dosen kadang menaruh materi di Office 365, lalu menautkannya ke LMS. LMS menolak mengirim file seperti itu. File ini ditandai tersimpan di luar LMS. Buka lewat `get_file_link` di browser, lalu unggah sendiri ke AI kalau isinya perlu dibaca.
- **Gambar tidak terbaca.** PDF hasil scan hampir tidak punya tulisan. Gambar dan diagram di slide juga tidak ikut.
- **Beberapa format lama belum bisa,** termasuk Excel, PowerPoint lama (PPT), dan Word lama (DOC).
- **File yang bisa dijalankan tidak diunduh,** termasuk `.exe`, skrip, dan halaman `.html`. Buka lewat `get_file_link` kalau memang perlu.

## Ambil kunci masuk

LMS kita hanya bisa masuk lewat Office 365. Kunci masuknya kita ambil dari halaman yang biasa dipakai aplikasi HP Moodle.

1. Buka halaman kunci masuk LMS, lalu masuk kalau diminta. Lewat situs, halaman server menautkannya di langkah "Buka halaman token". Di komputer, alamatnya ditampilkan oleh `uv run lms-mcp login`.
2. Klik kanan tautan "Click here if the app does not open automatically", lalu pilih "Copy link address". Gambarnya ada di [langkah 2 cara lewat situs](#2-tempel-kunci-masuk-di-halaman-server).

Tautan itu harus sama persis, huruf demi huruf. Jangan diketik ulang. Jangan disalin dari gambar. Kalau ditolak, tekan `F12` di halaman itu, buka tab Console, lalu tempel perintah ini:

```
copy(document.getElementById('launchapp').href)
```

Kunci masuk ini sama saja dengan membuka akun LMS kita. Jangan dibagikan. Jangan ditempel ke chat AI. Jangan ikut di tangkapan layar. Kalau sempat terkirim, reset kunci di LMS: klik foto profil di kanan atas, pilih Preferences, lalu Security keys.

Kunci ini punya masa berlaku yang diatur pengelola LMS. Biasanya sekitar 12 minggu. Kalau sudah habis, AI membalas bahwa akses ditolak (`accessexception` atau `invalidtoken`). Ulangi langkah di atas.

## Pakai di komputer

Dengan cara ini, kunci masuk tidak lewat server orang lain. Yang perlu ada di komputer:

- [git](https://git-scm.com/downloads), untuk mengambil proyek ini.
- [uv](https://docs.astral.sh/uv/getting-started/installation/), untuk memasang dan menjalankannya. Python tidak perlu dipasang sendiri. uv yang menyiapkannya.

Perintah memasang uv, dari panduan resminya. Di Windows, jalankan di PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Di macOS dan Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Setelah itu tutup terminal, lalu buka lagi.

### 1. Ambil dan pasang proyeknya

```bash
git clone https://github.com/bagusardin25/lms-mcp.git
cd lms-mcp
uv sync
```

### 2. Simpan kunci masuk

```bash
uv run lms-mcp login
```

Perintah ini menampilkan alamat halaman kunci masuk LMS, lalu menunggu kita menempel tautannya. Cara menyalin tautannya ada di bagian [Ambil kunci masuk](#ambil-kunci-masuk). Tautan yang ditempel tidak tampil di layar. Tekan Enter setelah menempel.

Kalau berhasil, muncul nama kita. Kunci masuk tersimpan di `~/.lms-mcp/token.txt`, dan dibaca sendiri setiap kali lms-mcp dijalankan. Di Windows, `~` adalah folder pengguna, misalnya `C:\Users\nama`.

File itu sengaja ada di luar folder proyek. AI yang bisa membuka folder proyek bisa membaca isinya. Yang disimpan juga hanya kunci untuk membaca LMS, bukan seluruh tautannya.

Kalau masa berlaku kunci habis, jalankan lagi perintah yang sama.

### 3. Cek sambungan ke LMS

```bash
uv run lms-mcp check
```

Kalau berhasil, muncul nama kita, daftar mata kuliah yang sedang berjalan, dan tenggat terdekat.

### 4. Sambungkan ke aplikasi AI

Di perintah dan contoh di bawah, ganti `/path/ke/lms-mcp` dengan lokasi folder proyek ini. Lokasinya muncul kalau kita menjalankan `pwd` di dalam folder proyek. Di Windows, tulis dengan garis miring biasa, misalnya `C:/Users/nama/lms-mcp`.

| Aplikasi | Tempat mengisinya | Panduan resmi |
|---|---|---|
| Claude Code | Perintah `claude mcp add` di bawah | [Claude Code](https://code.claude.com/docs/en/mcp) |
| Codex | Perintah `codex mcp add` di bawah | [Codex](https://learn.chatgpt.com/docs/extend/mcp) |
| Claude Desktop | Settings, Developer, lalu Edit Config. Nama filenya `claude_desktop_config.json` | [Claude Desktop](https://modelcontextprotocol.io/docs/develop/connect-local-servers) |
| Cursor | File `~/.cursor/mcp.json` | [Cursor](https://cursor.com/docs/mcp) |
| Antigravity | Tombol "…" di panel agen, MCP Servers, Manage MCP Servers, lalu View raw config | [Antigravity](https://antigravity.google/docs/mcp) |
| LM Studio | Tab Program, Install, lalu Edit mcp.json | [LM Studio](https://lmstudio.ai/docs/app/mcp) |
| VS Code | Command Palette, `MCP: Add Server`, lalu pilih Command (stdio) | [VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers) |

**Claude Code**

```bash
claude mcp add --scope user lms-mcp -- uv run --directory /path/ke/lms-mcp lms-mcp serve
```

Dengan `--scope user`, sambungan ini bisa dipakai dari folder mana pun. Tanpa itu, sambungan hanya ada di folder tempat perintahnya dijalankan. Cek hasilnya dengan `claude mcp list`.

**Codex**

```bash
codex mcp add lms-mcp -- uv run --directory /path/ke/lms-mcp lms-mcp serve
```

Cek hasilnya dengan `codex mcp list`.

**Claude Desktop, Cursor, Antigravity, dan LM Studio**

Keempatnya memakai isi yang sama. Tempel di file yang disebut di tabel:

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

Kalau file itu sudah berisi sambungan lain, tambahkan bagian `"lms-mcp"` saja ke dalam `mcpServers` yang sudah ada. Setelah disimpan, tutup aplikasinya sampai benar-benar keluar, lalu buka lagi.

**VS Code**

Setelah memilih Command (stdio), isi perintah ini:

```
uv run --directory /path/ke/lms-mcp lms-mcp serve
```

Kalau lebih suka mengisi file, VS Code memakai `.vscode/mcp.json`. Kuncinya `servers`:

```json
{
  "servers": {
    "lms-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/ke/lms-mcp", "lms-mcp", "serve"]
    }
  }
}
```

Kalau aplikasinya tidak menemukan `uv`, isi `command` dengan lokasi lengkap program `uv`. Lokasinya muncul dengan `where.exe uv` di Windows, atau `which uv` di macOS dan Linux.

Pengaturan lain, seperti folder unduhan, boleh dibiarkan. Daftarnya ada di bagian [Pengaturan di komputer](#pengaturan-di-komputer).

## Hal yang perlu dijaga

- Isi LMS bisa ditulis siapa saja di kelas, termasuk kalimat yang mencoba menyuruh AI. Baca dulu sebelum menyetujui apa yang AI mau lakukan.
- Data LMS yang dibaca AI ikut terkirim ke perusahaan pembuat AI itu. Kalau AI-nya berjalan di komputer kita, data itu tetap di komputer kita.
- Kunci masuk hanya dikirim ke LMS. Tautan unduhan dari situs lain ditolak.
- Semua yang kita lakukan tercatat di LMS atas nama akun kita.
- Unduh, unggah, kirim tugas, dan pembuatan tautan unggah juga dicatat di `~/.lms-mcp/audit.log`. Lokasinya bisa diganti lewat `LMS_AUDIT_LOG`. Catatan itu memuat waktu, apa yang dilakukan, berhasil atau tidak, dan nama mata kuliah atau tugas. Kunci masuk dan isi file tidak ikut.
- Di komputer, sambungkan ke satu AI saja. AI yang bisa membuka folder proyek bisa membaca file pengaturan. Karena itu `lms-mcp login` menyimpan kunci masuk di luar folder proyek. Kalau kunci masuk tetap ditaruh di `.env`, tambahkan `.env` ke `.cursorignore` sendiri.
- Di server yang sudah jalan, orang yang menjalankannya tetap bisa melihat kunci masuk teman. Itu batas dari cara ini, selama server yang bertanya ke LMS.
- Kalau menemukan celah yang bisa membuat kunci masuk orang lain terbaca, jangan tulis di issue publik. Cara melapornya diam-diam ada di [SECURITY.md](SECURITY.md).

## Pengaturan di komputer

Semua pengaturan ini boleh dibiarkan kosong. Kalau ada yang ingin diubah, salin [`.env.example`](.env.example) menjadi `.env` di folder proyek, lalu isi di sana. Di Windows perintahnya `Copy-Item .env.example .env`, di macOS dan Linux `cp .env.example .env`. File `.env` tidak ikut saat proyek ini diunggah ke GitHub.

| Nama | Artinya |
|---|---|
| `LMS_TOKEN` | Boleh dikosongkan. Tautan kunci masuk. Kalau diisi, ini yang dipakai, bukan kunci yang disimpan `lms-mcp login` |
| `LMS_TOKEN_FILE` | Boleh dikosongkan. Lokasi lain untuk file kunci masuk. Kalau kosong, yang dipakai `~/.lms-mcp/token.txt` |
| `LMS_DOWNLOAD_DIR` | Boleh dikosongkan. Folder tujuan unduhan. Kalau kosong, yang dipakai `Downloads/lms-mcp` |
| `LMS_AUDIT_LOG` | Boleh dikosongkan. Lokasi catatan. Kalau kosong, yang dipakai `~/.lms-mcp/audit.log` |
| `LMS_ENABLE_WRITE` | Boleh dikosongkan. Isi `1` untuk menyalakan pengumpulan tugas |
| `LMS_UPLOAD_DIRS` | Boleh dikosongkan. Folder asal file tugas, dipisah koma. Kalau kosong, yang dipakai Dokumen, Unduhan, dan Desktop |
| `LMS_BASE_URL` | Boleh dikosongkan. Alamat LMS. Kalau kosong, yang dipakai alamat LMS kampus kita |

Kalau nama yang sama juga diisi di pengaturan komputer, yang di komputer yang dipakai.

## Ikut mengembangkan

Cara ikut memperbaiki proyek ini ada di [CONTRIBUTING.md](CONTRIBUTING.md).

## Memeriksa proyek

```bash
uv run pytest
```

Perintah yang sama juga berjalan di GitHub setiap ada perubahan yang diunggah.
