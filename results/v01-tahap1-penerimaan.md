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
| Kompilasi `Nibras.exe` dengan mingw-w64 (MSYS2, `-municode`) | **Sudah** (41 KB). Gagal pada percobaan pertama: `undefined reference to WinMain`; diperbaiki dengan `-municode` |
| `build_bundle.ps1` (dependency dari lock, `--require-hashes`) dan pemasangan ke folder uji di drive D: (NTFS internal) | **Sudah** (bundle 765 MB) |
| `Nibras.exe` dijalankan dari folder uji: dialog setup pertama tampil, lalu jendela chat tema gelap | **Sudah** (dialog diisi oleh orang di PC, bukan agen) |
| Instance kedua ditolak lock dan tidak membuka jendela baru | **Sudah**, setelah perbaikan: sebelumnya selalu muncul kotak pesan karena `import win32gui` gagal di bundle (`.pth` pywin32 tidak diproses). Diganti `ctypes` |
| Penutupan dari jendela: proses keluar 0,3 detik, `clean_shutdown=1`, audit `vault_open` dan `vault_lock`, empat DB `journal_mode=delete` dan `quick_check=ok`, `Temp/` kosong | **Sudah** |
| Jejak di `%TEMP%`, `%LOCALAPPDATA%`, `%APPDATA%` | **Sudah**: 133 file baru/berubah, semuanya milik aplikasi lain; tidak ada path berisi nibras/python/qt/pyside/pywin. Dua file `%TEMP%` tanpa nama jelas tidak bisa dipastikan asalnya |
| Log startup | `Data/logs/nibras.log` **kosong** (0 byte) pada start normal. Tidak ada galat, tapi tidak ada baris startup |
| Seluruh checklist 1–8 di bawah (butuh flashdisk dan operator) | **Belum** |

## Temuan operator di flashdisk (dilaporkan lewat chat, bukan hasil checklist)

Dipasang ke flashdisk USB (NTFS) dan dicoba oleh operator. Bug yang ditemukan
lalu diperbaiki di branch ini; operator mengonfirmasi hasilnya "sudah oke"
setelah kode terbaru dipasang ke flashdisk (konfirmasi lisan, tanpa angka).

| Temuan | Penyebab | Perbaikan |
|---|---|---|
| Provider menggantung "menyiapkan AI…", pesan tertahan | Default `base_url`/model kosong (repo publik); tidak ada pengecekan ulang setelah Pengaturan disimpan | `da8c21c` |
| Enter membuat baris baru, bukan mengirim | Tidak ada penanganan tombol di kotak pesan | `a278d94` |
| Pesan pengguna tidak tampil, hanya balasan | Kartu pengguna tidak pernah ditambahkan saat kirim | `a600a20` |
| Balasan lama terpotong satu-dua baris | Tinggi kartu dihitung sebelum dokumen ditata ke lebar sebenarnya | `a600a20` |
| Pesan pertama (tanpa percakapan) tidak pernah terkirim | `_pending_text` tidak dikirim setelah percakapan dibuat | `a600a20` |
| Kartu pesan terputus/dibatalkan/gagal kosong tanpa keterangan setelah dibuka ulang | Status pesan tidak diteruskan ke tampilan | `f76b3e9` |
| "Tutup & Aman Dilepas" membuat aplikasi macet: shutdown selesai, widget nonaktif, proses tidak keluar | `QApplication.quit()` mengirim close event dan `closeEvent` selalu `ignore()`, sehingga quit dibatalkan jendelanya sendiri. Diganti `QApplication.exit(0)`; test memakai `exec()` sungguhan (gagal pada kode lama) | `1110580` |
| Log di flashdisk memuat URL endpoint pribadi di tiap request | Logger HTTP mencatat URL pada level INFO | `1110580` |

Bukti dari data di flashdisk (dibaca saja): `clean_shutdown=1` setelah tiap
penutupan; 5 pesan pengguna; balasan 3 `done`, 1 `cancelled` (Batalkan dicoba),
1 **`failed` (penyebabnya belum diselidiki)**; riwayat percakapan tampil lagi
setelah aplikasi dibuka ulang (terlihat di tangkapan layar operator).

Pengamatan bukan bug (tahap ini memang belum punya alat): Nibras tidak bisa
melihat drive PC karena Tools/PowerShell baru ada di Tahap 4.

Lulus (dilaporkan operator): butir 2 (chat panjang, Batalkan, Esc), 3 (tutup dan buka lagi), 4 (passphrase salah), 5 (cabut saat streaming), dan 6 (dua instance di flashdisk).

Dilaporkan sebagai angka tunggal: butir 8 (waktu cold-start) 11 detik termasuk mengetik passphrase, tanpa pemecahan per tahap.

Belum diuji: butir 7 (jejak di PC host untuk F:).

## Checklist operator

- Tanggal pengujian:
- PC pengujian (Windows, CPU/RAM):
- Flashdisk (merek, USB 2.0/3.x, NTFS):

## 1. Setup pertama
- [ ] Passphrase dibuat (diketik 2x), peringatan "tidak ada pemulihan" tampil
- [ ] base_url, model, API key terisi; jendela chat terbuka
- Hasil:

## 2. Chat panjang (kode + tabel)
- [x] Jawaban panjang tampil utuh (kode + tabel ter-render)
- [x] UI tetap responsif selama streaming
- [x] Tombol Batalkan menghentikan streaming; Esc juga menghentikan
- Hasil: **LULUS** (dilaporkan operator di flashdisk, tanpa angka responsivitas). Data flashdisk mencatat jawaban berstatus `cancelled`; data tidak membedakan Batalkan dari `Esc`. Tinggi kartu panjang sempat salah di versi awal (diperbaiki di `a600a20`).

## 3. Tutup & buka lagi
- [x] Ditutup via tombol "Tutup & Aman Dilepas"
- [x] Dibuka lagi: riwayat percakapan masih ada
- Hasil: **LULUS** setelah perbaikan `1110580`. Sebelumnya tombol itu membuat aplikasi macet (lihat tabel temuan). Setelah perbaikan operator melaporkan "pass"; data flashdisk: proses hilang, lock bebas, `clean_shutdown=1`, audit `vault_open` lalu `vault_lock`. Riwayat setelah dibuka ulang: terlihat di tangkapan layar operator sebelumnya (kartu pengguna dan balasan tampil); data memuat 2 percakapan dan 18 pesan.

## 4. Passphrase salah
- [x] Ditolak dengan pesan jelas, aplikasi tidak crash
- Hasil: **LULUS** (dilaporkan operator di chat, tanpa data pendukung; penolakan passphrase tidak meninggalkan jejak di database)

## 5. Cabut flashdisk saat streaming
- [x] Flashdisk dicabut di tengah streaming, lalu dicolok lagi
- [x] Laporan pemulihan tampil saat dibuka lagi
- [x] Pesan yang terputus ditandai (tidak dilanjutkan otomatis)
- Hasil: **LULUS**. Laporan pemulihan tampil (tangkapan layar operator: DB semua OK, Temp/ dibersihkan, 1 pesan terputus). Data flashdisk: 1 pesan asisten berstatus `interrupted`, tidak dilanjutkan. Tampilan awalnya kartu kosong tanpa keterangan (celah, diperbaiki di `f76b3e9`); setelah kode terbaru dipasang, operator mengonfirmasi keterangan "Terputus" muncul. Catatan: teks yang belum sempat tersimpan (penyimpanan parsial tiap 2 detik) hilang saat dicabut; pesan ini isinya kosong.

## 6. Jalankan Nibras.exe dua kali
- [x] Instance kedua menampilkan jendela pertama, tidak membuka jendela baru
- Hasil: **LULUS** di flashdisk F:. Operator: tidak ada jendela baru. Data proses: hanya 1 `pythonw` dari F: setelah peluncuran kedua. Belum dikonfirmasi operator apakah jendela pertama naik ke depan (Windows dapat menolak fokus dari proses latar).

## 7. Jejak di PC host
- [ ] Setelah ditutup, tidak ada file Nibras baru di %TEMP% dan %LOCALAPPDATA%
- Hasil:

## 8. Waktu cold-start (setelah colok ulang)
- Waktu sampai jendela tampil: **tidak dipisah**
- Waktu sampai provider siap: **tidak dipisah**
- Hasil: operator melaporkan **11 detik** secara keseluruhan, **termasuk mengetik passphrase**, diukur manual. Tidak dipecah per tahap, dan belum dikonfirmasi tersendiri bahwa flashdisk dicabut-colok tepat sebelum run ini. Jadi angka ini bukan perbandingan langsung dengan Uji #2 (`usb3-cold`: T3 median 2,54 detik, T6 median 16,26 detik, tanpa mengetik passphrase). Karena jendela tampil lebih dulu dan SDK dimuat di latar belakang (D-59), waktu sampai jendela tampil kemungkinan jauh di bawah 11 detik, tetapi itu belum diukur. Untuk angka per tahap perlu pengukuran terpisah.
