# Melapor celah keamanan

lms-mcp memegang kunci masuk LMS, jadi satu celah saja bisa membuat akun orang lain terbuka. Kalau kamu menemukan celah, laporkan diam-diam dulu. Jangan tulis detailnya di issue publik.

## Cara melapor

1. Buka [halaman laporan rahasia](https://github.com/bagusardin25/lms-mcp/security/advisories/new) di GitHub. Laporan di sana hanya bisa dibaca kamu dan pembuat proyek.
2. Ceritakan apa yang terjadi, langkah untuk mengulanginya, dan akibatnya.
3. Jangan sertakan kunci masuk sungguhan, isi `.env`, atau tangkapan layar yang memuat tautan `moodlemobile://token=`. Pakai contoh palsu saja.

Kalau tidak punya akun GitHub, kirim lewat pesan pribadi ke pembuat proyek, Bagus Ardin Prayoga.

## Yang termasuk celah keamanan

- Kunci masuk bisa terbaca orang lain, ikut tercatat, atau terkirim ke tempat selain LMS.
- Server bisa dipakai dengan kunci masuk orang lain, atau tanpa masuk sama sekali.
- Izin yang tersimpan di aplikasi AI bisa dibuka tanpa kata sandi rahasia server.
- Halaman masuk server bisa mengirim izin ke situs selain aplikasi AI yang diizinkan.
- AI bisa mengunduh file, mengunggah file, atau mengumpulkan tugas tanpa kita menekan tombol.

## Yang bukan celah keamanan

- Orang yang menjalankan server bisa melihat kunci masuk. Ini batas cara lewat situs, dan sudah dijelaskan di [PRIVASI.md](PRIVASI.md).
- AI salah menjawab, misalnya salah membaca tenggat. Itu laporan kerusakan biasa, jadi tulis saja di [issue](https://github.com/bagusardin25/lms-mcp/issues).
- Kunci masuk bocor karena kita sendiri menempelnya ke chat atau tangkapan layar. Segera reset kunci itu, caranya ada di bawah.

## Setelah melapor

- Laporan dibaca oleh pembuat proyek, dan balasan pertama diusahakan dalam beberapa hari.
- Perbaikannya dikerjakan diam-diam dulu. Detail celahnya baru diumumkan setelah perbaikan terpasang di server.
- Kalau celah itu sempat dipakai untuk membaca kunci masuk orang lain, semua sambungan ke server diputus dan pemakainya diberi tahu, sesuai janji di [PRIVASI.md](PRIVASI.md).

## Versi yang dijaga

Yang dijaga hanya versi terbaru di cabang `main` dan server yang sudah jalan di `https://lms-mcp.up.railway.app/mcp`.

## Kalau kunci masuk kita sendiri bocor

Buka Preferences di LMS, lalu Security keys, lalu reset kunci untuk aplikasi HP Moodle. Semua kunci lama langsung tidak berlaku, termasuk yang tersimpan terkunci di aplikasi AI.
