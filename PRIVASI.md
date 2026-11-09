# Privasi dan keamanan data

Tulisan ini untuk teman-teman yang memakai server lms-mcp yang sudah jalan, di alamat `https://lms-mcp.up.railway.app/mcp`. Di sini tertulis apa yang dibaca dari LMS, apa yang disimpan, siapa yang bisa melihatnya, dan cara memutus akses.

Server ini saya jalankan sebagai proyek mahasiswa. Server ini terpisah dari kampus dan pengelola LMS, dan belum pernah diperiksa orang luar.

Terakhir diperiksa: 9 November 2026.

## Ringkasnya

- **Kunci masuk LMS tidak disimpan.** Server ini tidak punya daftar akun, tidak punya file, dan tidak punya cadangan. Kunci masuk juga tidak ikut tercatat.
- **Password akun kampus tidak pernah lewat server ini.** Yang ditempel hanya tautan kunci masuk dari halaman LMS.
- **AI di server ini hanya bisa melihat.** Mengumpulkan tugas, mengirim pesan, dan menulis di forum dimatikan.
- **Saya tetap bisa melihat kunci masuk kalau mau.** Ini batas dari cara lewat situs, dan penjelasannya ada di bawah. Kalau tidak nyaman, pakai cara di komputer sendiri. Caranya ada di [README](README.md#pakai-di-komputer).
- **Akses bisa diputus kapan saja** dengan reset kunci di halaman Security keys LMS.

## Yang dibaca dari LMS

Server baru membaca LMS saat kita meminta sesuatu ke AI. Semuanya dibaca memakai kunci masuk kita sendiri, jadi server hanya bisa melihat yang memang bisa kita lihat di LMS.

| Yang dibaca | Kapan |
|---|---|
| Nama, nama pengguna, nomor akun LMS, dan izin mengunduh atau mengunggah | Saat menyambungkan, untuk memastikan kunci masuknya benar. Juga saat AI menanyakan siapa kita |
| Daftar mata kuliah, progres, dan tanggal mulai serta selesainya | Saat kita menanyakan mata kuliah |
| Tenggat dari kalender LMS, tugas dan kuis di rentang waktu itu, serta status kirimannya | Saat kita menanyakan tenggat |
| Isi mata kuliah: bagian, kegiatan, nama file, tautan, keterangan, dan tanda selesai | Saat kita menanyakan materi |
| Tugas: perintah dosen, aturan file, status, nama file yang sudah dikirim, nilai, dan komentar dosen | Saat kita menanyakan tugas |
| Isi file materi | Hanya kalau kita minta AI membaca file itu. File dibaca sebentar, diambil tulisannya, lalu dibuang |

## Yang tidak diambil

- Password akun kampus atau Office 365.
- Pesan pribadi, forum, presensi, dan soal kuis. Server ini memang tidak punya kemampuan untuk membacanya.
- Data mahasiswa lain, di luar yang memang bisa kita lihat sendiri di LMS.
- Perubahan apa pun di LMS. Server ini tidak mengumpulkan tugas, tidak mengirim pesan, dan tidak menulis di forum.

## Yang disimpan dan yang tidak

| Data | Di mana | Berapa lama |
|---|---|---|
| Kunci masuk, apa adanya | Hanya diingat sementara di server, supaya tidak perlu dibuka ulang setiap kali AI bertanya. Tidak pernah ditulis ke file | Hilang saat server tidur, yaitu sekitar 5–10 menit tanpa pemakaian, atau saat server dinyalakan ulang |
| Kunci masuk yang sudah dikunci | Di aplikasi AI yang kita sambungkan, sebagai izin untuk memakai server ini | Izinnya berlaku 1 jam. Izin untuk memperpanjangnya berlaku 90 hari |
| Nomor akun LMS | Ikut terkunci di dalam izin yang sama | Sama dengan izinnya |
| Data LMS yang dibaca AI | Tidak disimpan di server. Langsung diteruskan ke aplikasi AI | Mengikuti aturan aplikasi AI itu |
| Catatan kunjungan di Railway | Railway, tempat server ini dipasang | Berisi alamat halaman yang dibuka, tanpa isi tambahan di belakangnya. Juga berisi alamat internet kita, jenis browser, waktu, dan berhasil atau tidaknya. Lama simpannya mengikuti Railway |
| Catatan server | Railway | Hanya tanda server menyala dan peringatan. Tidak berisi kunci masuk atau data LMS |
| Daftar akun, file, dan cadangan | Tidak ada | — |

Alamat internet yang tercatat adalah alamat kita saat membuka halaman masuk di browser. Saat AI yang bertanya, yang tercatat adalah alamat server perusahaan AI itu.

## Bagaimana kunci masuk dijaga

1. Kita menempel tautan kunci masuk di halaman masuk server. Sambungannya terkunci, jadi isinya tidak bisa diintip di tengah jalan.
2. Server bertanya ke LMS siapa pemilik kunci itu, untuk memastikan kuncinya benar.
3. Server langsung mengunci kunci masuk itu dengan kata sandi rahasia server. Hasilnya diberikan ke aplikasi AI sebagai izin. Aplikasi AI menyimpan izin itu, tetapi tidak bisa membukanya.
4. Setiap kali AI butuh data, aplikasi AI menunjukkan izin itu. Server membukanya sebentar, lalu memakai kunci masuk untuk bertanya ke LMS.
5. Kunci masuk dikirim ke LMS di dalam isi permintaan, jadi tidak ikut tertulis di alamat halaman. Server juga hanya mau mengirim kunci masuk ke LMS. Tautan file yang mengarah ke situs lain ditolak.

Untuk yang ingin tahu nama caranya: penguncinya memakai Fernet (AES-128 dan HMAC-SHA256), dengan kunci yang diturunkan dari `LMS_SERVER_SECRET`.

## Siapa yang bisa melihat apa

| Siapa | Yang bisa dilihat |
|---|---|
| Kita sendiri | Semua data LMS kita, seperti biasa |
| Saya, yang menjalankan server | Secara teknis bisa membuka kunci masuk, karena saya memegang kata sandi rahasia server dan bisa mengubah kode server. Janjinya ada di bawah |
| Railway, tempat server ini dipasang | Punya akses ke mesin server, seperti tempat pemasangan server pada umumnya |
| Aplikasi AI, misalnya Claude, ChatGPT, atau Grok | Menyimpan izin yang terkunci, dan tidak bisa membukanya. Menerima data LMS yang dibaca AI saat kita mengobrol, sesuai aturan privasi masing-masing |
| LMS | Mencatat setiap permintaan atas nama akun kita, sama seperti saat kita membuka LMS sendiri. Nama aplikasinya tercatat sebagai `lms-mcp` |

## Janji saya sebagai yang menjalankan server

- Saya tidak membuka, menyalin, atau menyimpan kunci masuk teman-teman.
- Saya tidak memakai kunci masuk teman-teman untuk hal lain, selain menjawab permintaan dari AI yang mereka sambungkan sendiri.
- Saya tidak menambah tempat penyimpanan atau catatan yang berisi kunci masuk atau data LMS, tanpa mengubah tulisan ini lebih dulu.
- Saya tidak menyalakan fitur mengumpulkan tugas di server ini tanpa memberi tahu teman-teman lebih dulu.
- Kalau kata sandi rahasia server atau akun saya diduga bocor, saya memutus semua sambungan dan memberi tahu teman-teman.

Bagus Ardin Prayoga

## Cara memutus akses

1. **Reset kunci masuk di LMS.** Buka Preferences di LMS, lalu Security keys, lalu reset kunci untuk aplikasi HP Moodle. Semua kunci lama langsung tidak berlaku, termasuk yang tersimpan terkunci di aplikasi AI. Setelah itu, aplikasi Moodle di HP mungkin minta masuk ulang.
2. **Hapus sambungan di aplikasi AI.** Misalnya di claude.ai lewat Settings, lalu Connectors.
3. **Saya bisa memutus semua sambungan sekaligus,** dengan menaikkan angka `LMS_TOKEN_GENERATION` lalu menyalakan ulang server.

Kalau kita berhenti memakai server ini tanpa reset kunci, izin yang terkunci di aplikasi AI masih ada sampai 90 hari. Kunci masuknya sendiri juga habis masa berlakunya sesuai aturan pengelola LMS.

## Yang belum bisa dijanjikan

- Selama server ini yang bertanya ke LMS atas nama kita, kita tetap perlu percaya kepada orang yang menjalankannya. Cara yang kuncinya tetap di komputer kita adalah memakai lms-mcp di komputer sendiri.
- Belum ada cara untuk memastikan kode yang jalan di server sama dengan kode di GitHub. Server masih dipasang manual dari komputer saya.
- Proyek ini belum pernah diperiksa orang luar.

## Memeriksa sendiri

Kalau ingin memastikan sendiri, kodenya ada di proyek ini:

- Halaman masuk, cara mengunci kunci masuk, dan masa berlaku izin: [`src/lms_mcp/oauth.py`](src/lms_mcp/oauth.py)
- Cara server bertanya ke LMS dan mengirim kunci masuk: [`src/lms_mcp/moodle.py`](src/lms_mcp/moodle.py)
- Daftar yang bisa dilakukan AI lewat server ini: [`src/lms_mcp/server.py`](src/lms_mcp/server.py)
