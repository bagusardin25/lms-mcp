# Ikut mengembangkan lms-mcp

Terima kasih kalau kamu ingin membantu. Perbaikan tulisan bisa langsung dikirim sebagai usulan perubahan. Untuk perubahan kode, ceritakan dulu maksudnya di issue, supaya kita sepakat sebelum kamu menghabiskan waktu.

## Bertanya dan melapor

- Pertanyaan, ide, dan laporan kerusakan ditulis di [GitHub Issues](https://github.com/bagusardin25/lms-mcp/issues).
- Jangan tempel kunci masuk LMS, isi `.env`, atau tangkapan layar yang memuat tautan `moodlemobile://token=`. Kalau kunci itu sempat terkirim, reset di halaman Security keys LMS.
- Kalau kamu menemukan celah yang bisa membuat kunci masuk orang lain terbaca, jangan tulis detailnya di issue publik. Kirim lewat pesan pribadi ke pembuat proyek, Bagus Ardin Prayoga.

## Cara mengusulkan perubahan

- Perbaikan README dan penjelasan lain boleh langsung menjadi pull request.
- Perubahan kode, termasuk perbaikan kecil, fitur baru, ketergantungan baru, dan perombakan, dimulai dari issue:
  1. Cari issue yang sudah ada, atau buat issue baru yang menjelaskan masalah dan usulannya.
  2. Tunggu tanggapan dulu. Perubahan yang menyentuh kunci masuk, pengumpulan tugas, atau data LMS perlu dibicarakan sebelum kodenya ditulis.
  3. Setelah disetujui, kerjakan di cabangmu sendiri, lalu buka pull request ke `main`.
- Satu pull request untuk satu perubahan. Judulnya cukup menjelaskan apa yang diperbaiki.
- Di deskripsi, tulis `Closes #123` kalau pull request itu menyelesaikan issue nomor 123.

## Yang perlu dibicarakan dulu

- Ketergantungan baru. Daftar pustaka sengaja dibuat kecil. Pustaka baru perlu alasan di issue sebelum ditambahkan.
- Fitur yang mengubah LMS, seperti mengumpulkan tugas, mengirim pesan, atau menulis di forum. Melihat data boleh. Mengubah data harus tetap lewat tombol yang ditekan manusia.
- Apa pun yang mencatat, menampilkan, atau mengirim kunci masuk LMS.
- Server bersama untuk banyak orang. Batasnya sudah dijelaskan di README: orang yang menjalankan server bisa melihat kunci masuk.

## Menjalankan dari sumber

Perlu [uv](https://docs.astral.sh/uv/) dan Python 3.11 atau lebih baru. Pengembangan biasa memakai Python 3.12.

```bash
git clone https://github.com/bagusardin25/lms-mcp.git
cd lms-mcp
uv sync
uv run pytest
```

Perintah tes yang sama juga berjalan di GitHub pada setiap push dan pull request. Tes memakai LMS tiruan, jadi tidak perlu kunci masuk sungguhan.

Untuk mencoba pada LMS sungguhan, salin `.env.example` menjadi `.env`, lalu isi kunci masuk seperti di README. File `.env` tidak boleh ikut terkirim.

## Di Windows

Windows didukung. Cukup git, Python, dan uv. Perintah `uv sync` dan `uv run pytest` sama seperti di sistem lain.

## Mengirim pull request

- Fork repositori ini, buat cabang di forkmu, lalu buka pull request ke `main`.
- Nama cabang memakai awalan: `feat/…`, `fix/…`, `docs/…`, `refactor/…`, `test/…`.
- Perubahan perilaku baru disertai tes.
- Jangan masukkan kunci masuk, file unduhan, atau catatan dari komputermu.

## Isi proyek

- `src/lms_mcp/server.py` — alat yang dilihat AI, untuk komputer dan untuk situs.
- `src/lms_mcp/service.py` — membaca mata kuliah, materi, dan file.
- `src/lms_mcp/assignments.py` — tugas dan aturan pengumpulannya.
- `src/lms_mcp/moodle.py` — percakapan dengan LMS.
- `src/lms_mcp/oauth.py` dan `src/lms_mcp/pages.py` — masuk lewat situs dan halaman yang dilihat manusia.
- `src/lms_mcp/confirm.py` — halaman konfirmasi di komputer sebelum mengunduh atau mengumpulkan.
- `tests/` — tes. LMS tiruannya ada di `tests/fake_moodle.py`.

## Lisensi

Dengan mengirim kontribusi, kamu setuju kontribusi itu memakai [MIT License](LICENSE), lisensi yang sama dengan proyek ini. Tidak ada perjanjian tambahan.
