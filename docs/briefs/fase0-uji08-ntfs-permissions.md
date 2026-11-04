# Brief Tugas — Fase 0, Uji #8: Izin NTFS Lintas PC dan Akun

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md` (D-04)
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.
**Dijalankan di:** 2–3 PC Windows fisik berbeda (dan/atau akun Windows berbeda), lewat sesi Claude Code lokal operator.

---

## 1. Tujuan

D-04 menetapkan USB **wajib NTFS**. NTFS membawa ACL (access control list) yang terikat ke SID akun Windows tempat file dibuat. Karena Nibras dipakai dengan mencolokkan USB yang sama ke PC dan akun Windows yang berbeda-beda, ada risiko file/folder yang dibuat di satu PC/akun jadi tidak bisa diakses (atau butuh elevasi) ketika USB dipindah ke PC/akun lain. Uji ini memverifikasi itu **tidak terjadi** untuk operasi normal Nibras (baca, tulis, buat file baru, hapus).

Pertanyaan yang dijawab:
1. Apakah file dan folder yang dibuat Nibras di PC/akun A bisa dibaca dan ditulis ulang tanpa error permission ketika USB dipindah ke PC/akun B dan C?
2. Apakah ACL NTFS default pada removable drive memang permissive (biasanya `Everyone`/`Authenticated Users` penuh) seperti asumsi, atau ada PC/kebijakan yang membuatnya restriktif?
3. Apakah ada perbedaan perilaku antara mencabut USB dengan aman ("Eject") vs mencabut langsung, terhadap ACL file yang baru ditulis?

## 2. Ruang Lingkup

**Termasuk:** script yang membuat struktur folder/file meniru layout data Nibras (database, log, file konfigurasi) dengan beberapa operasi I/O, dijalankan berurutan di tiap PC/akun, pengecekan ACL eksplisit, panduan prosedur.

**Tidak termasuk:** Agent Core atau database Nibras sungguhan — cukup file dan folder dummy dengan layout yang representatif.

## 3. Keputusan Desain yang WAJIB Diikuti

- USB diformat **NTFS** (D-04) — jika USB uji saat ini FAT32/exFAT, format ulang dulu sebagai bagian prosedur (lihat bagian 6), dan catat itu sebagai langkah eksplisit, bukan diasumsikan.
- Tidak boleh mengubah ACL secara manual (`icacls`) sebagai "solusi" — Nibras di produksi tidak akan punya hak admin untuk mengubah ACL sistem, jadi solusinya harus jalan dengan ACL default.

## 4. Larangan (Jangan Dilakukan)

- ❌ Jangan menjalankan sebagai admin untuk "mengakali" error permission — harus diuji di akun standard user (non-admin), sesuai target produksi.
- ❌ Jangan mengubah ACL USB secara manual sebagai solusi. Jika ditemukan masalah ACL, laporkan sebagai temuan untuk desain (misalnya perlu `icacls` otomatis **sekali saat pertama kali USB dipakai**, bukan setiap kali jalan), jangan diterapkan diam-diam di uji ini.
- ❌ Jangan menebak hasil. Setiap kombinasi PC × akun di bagian 5 harus benar-benar dicoba dengan USB fisik yang sama berpindah tangan.

## 5. Spesifikasi Script Uji

Buat `ntfs_probe.py` dengan dua mode:

**Mode `--init`** (dijalankan sekali, di PC/akun pertama):
1. Buat struktur folder meniru layout Nibras: `Data/core.db`, `Data/memory.db`, `Data/vectors.db`, `Data/Logs/app.log`, beberapa file dummy berisi data acak ~1 MB per "database".
2. Tulis file `Data/.ntfs_probe_manifest.json` berisi daftar file, ukuran, dan hash SHA-256 masing-masing, serta SID akun pembuat (`whoami /user` atau API Windows) dan nama PC.

**Mode `--verify`** (dijalankan di setiap PC/akun berikutnya):
1. Baca manifest, verifikasi tiap file bisa **dibaca** (hash cocok) dan **ditulis ulang** (append lalu hash ulang, lalu kembalikan ke isi semula supaya tidak merusak uji berikutnya).
2. Coba **buat file baru** di tiap folder, lalu **hapus** file itu — ini menguji permission folder, bukan hanya file yang sudah ada.
3. Catat SID akun saat ini dan PC saat ini, bandingkan dengan manifest, dan catat exit code/exception apa pun secara spesifik (jangan hanya "berhasil"/"gagal" — catat pesan error asli jika ada).

## 6. Prosedur Uji (oleh operator manusia)

1. Siapkan USB ber-format NTFS (format ulang jika perlu — catat ini di laporan).
2. Jalankan `ntfs_probe.py --init` di PC pertama, akun pertama.
3. Pindahkan USB (cabut lewat "Safely Remove Hardware") ke PC kedua, akun berbeda (idealnya memang akun Windows yang berbeda, bukan cuma PC berbeda dengan akun sama). Jalankan `--verify`.
4. Ulangi ke PC ketiga jika operator punya akses (minimal 2 PC **wajib**, PC ketiga nice-to-have sesuai kriteria "2–3 PC").
5. Ulangi sekali lagi dengan mencabut USB **tanpa** "Safely Remove" (langsung cabut) setelah salah satu langkah `--verify`, lalu colok ke PC lain dan jalankan `--verify` sekali lagi — untuk membandingkan apakah cara cabut mempengaruhi ACL.
6. Di salah satu langkah, jalankan `icacls <path file>` manual (hanya untuk **mencatat** ACL yang berlaku, bukan mengubahnya) dan sertakan outputnya di laporan sebagai bukti.

## 7. Kriteria Lulus

| Kriteria | Target | Sifat |
|---|---|---|
| Error permission (akses ditolak) pada operasi baca/tulis/buat/hapus di semua kombinasi PC × akun bagian 6 | **0 kejadian** (`decisions.md` bagian 10) | **Wajib** |
| Hash file sebelum dan sesudah berpindah PC/akun tetap identik (sebelum operasi tulis ulang) | Identik di semua kombinasi | **Wajib** |
| Perbedaan ACL akibat cara cabut USB (aman vs langsung) | Dicatat, tidak harus sama | Informasi |

Jika ditemukan error permission, **jangan** diatasi dengan mengubah ACL USB secara manual sebagai "solusi" di uji ini (larangan bagian 4) — laporkan apa adanya untuk direview.

## 8. Deliverable

```
spikes/uji08-ntfs/
├── ntfs_probe.py
└── README.md
results/
└── uji08-ntfs.md
```

Isi `results/uji08-ntfs.md`:
1. **Lingkungan:** daftar PC (nama/spesifikasi ringkas, cukup untuk identifikasi, tanpa data sensitif) dan akun yang dipakai, tipe/merek USB.
2. **Tabel hasil** per kombinasi PC × akun: hasil baca/tulis/buat/hapus, hash cocok atau tidak, pesan error jika ada.
3. **Output `icacls`** yang dicatat di langkah 6 bagian 6.
4. **Perbandingan** cabut aman vs cabut langsung.
5. **Evaluasi** terhadap kriteria bagian 7.

## 9. Definisi Selesai

- Minimal 2 PC dan akun berbeda benar-benar diuji dengan USB fisik yang sama.
- Tidak ada ACL yang diubah manual sebagai solusi.
- Kode dikerjakan di branch `fase0/uji08`, lalu dibuka pull request ke `main`.
