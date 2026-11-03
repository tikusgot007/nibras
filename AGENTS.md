# Instruksi untuk Agen Coding

Baca file ini sebelum mengerjakan tugas apa pun di repo ini.

## Aturan Utama

1. **`docs/decisions.md` adalah sumber kebenaran desain.** Ikuti setiap keputusan di dalamnya. Jangan ganti teknologi, PRAGMA, struktur folder, atau pendekatan dengan pilihan lain, meskipun pilihan lain itu lebih umum.
2. **Kerjakan hanya brief yang diberikan** di `docs/briefs/`. Jangan memperluas scope dan jangan menambah fitur yang tidak diminta.
3. **Patuhi bagian "Larangan" di setiap brief.** Larangan bersifat mutlak.
4. **Jika ada konflik atau ambiguitas, berhenti dan tanyakan.** Jangan menebak, dan jangan menyimpang diam-diam.
5. **Jangan mengubah `docs/decisions.md` dan `docs/briefs/`.** Usulan perubahan ditulis di deskripsi pull request.
6. **Laporan hasil uji harus berasal dari eksekusi nyata.** Jangan mengarang angka.

## Konvensi

- Kode, nama file, dan identifier ditulis dalam bahasa Inggris. Dokumentasi dan laporan ditulis dalam Bahasa Indonesia.
- Setiap brief dikerjakan di branch tersendiri (misalnya `fase0/uji01`), lalu dibuka pull request ke `main`.
- Jangan commit secret, API key, file `.env`, database hasil uji, atau file vault. Lihat `.gitignore`.

## Prinsip Desain yang Sering Dilanggar (perhatikan)

- SQLite **tanpa WAL**: gunakan `journal_mode=DELETE` dan `synchronous=FULL`.
- **Semua data di USB.** Jangan menulis ke `%TEMP%`, `%APPDATA%`, atau profil pengguna di PC host.
- **Jangan memakai PyInstaller** dalam mode apa pun. Packaging memakai Python Embeddable Distribution.
- Aplikasi berjalan **tanpa hak admin** dan **tanpa background service**.
