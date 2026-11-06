# Uji Penerimaan — v0.1 Tahap 1 (Chat Dasar dari USB)

> Diisi oleh operator dengan hasil nyata saat pengujian di flashdisk NTFS.
> Butir yang gagal ditulis apa adanya. Template ini dibuat saat implementasi;
> hasil di bawah ini BELUM diisi.

## Status verifikasi otomatis (perbaikan review PR #9)

Diverifikasi di PC pengembang Windows 11 (Python 3.14, dependency dari
`requirements.lock` dengan hash), bukan di flashdisk:

| Hal | Status |
|---|---|
| `pytest`: 48 test lulus, diulang 3 kali tanpa kegagalan | **Sudah** |
| Alur chat lewat `AgentCore` sungguhan (thread + loop asli) ke server tiruan lokal | **Sudah** |
| Lock instance tunggal: dua proses OS terpisah, yang kedua ditolak (Windows) | **Sudah** |
| Kompilasi `Nibras.exe` dengan mingw-w64 | **Belum** (mingw-w64 belum terpasang di PC ini) |
| `build_bundle.ps1` dan pemasangan ke folder uji di drive internal NTFS | **Belum** |
| Menjalankan `Nibras.exe` dari folder uji: jendela, setup pertama, log startup | **Belum** |
| Jejak di `%TEMP%` dan `%LOCALAPPDATA%` saat aplikasi berjalan | **Belum** |
| Seluruh checklist 1–8 di bawah (butuh flashdisk dan operator) | **Belum** |

## Checklist operator

- Tanggal pengujian:
- PC pengujian (Windows, CPU/RAM):
- Flashdisk (merek, USB 2.0/3.x, NTFS):

## 1. Setup pertama
- [ ] Passphrase dibuat (diketik 2x), peringatan "tidak ada pemulihan" tampil
- [ ] base_url, model, API key terisi; jendela chat terbuka
- Hasil:

## 2. Chat panjang (kode + tabel)
- [ ] Jawaban panjang tampil utuh (kode + tabel ter-render)
- [ ] UI tetap responsif selama streaming
- [ ] Tombol Batalkan menghentikan streaming; Esc juga menghentikan
- Hasil:

## 3. Tutup & buka lagi
- [ ] Ditutup via tombol "Tutup & Aman Dilepas"
- [ ] Dibuka lagi: riwayat percakapan masih ada
- Hasil:

## 4. Passphrase salah
- [ ] Ditolak dengan pesan jelas, aplikasi tidak crash
- Hasil:

## 5. Cabut flashdisk saat streaming
- [ ] Flashdisk dicabut di tengah streaming, lalu dicolok lagi
- [ ] Laporan pemulihan tampil saat dibuka lagi
- [ ] Pesan yang terputus ditandai (tidak dilanjutkan otomatis)
- Hasil:

## 6. Jalankan Nibras.exe dua kali
- [ ] Instance kedua menampilkan jendela pertama, tidak membuka jendela baru
- Hasil:

## 7. Jejak di PC host
- [ ] Setelah ditutup, tidak ada file Nibras baru di %TEMP% dan %LOCALAPPDATA%
- Hasil:

## 8. Waktu cold-start (setelah colok ulang)
- Waktu sampai jendela tampil:
- Waktu sampai provider siap:
