# Brief Tugas — Fase 0, Uji #7: Chromium Dijalankan dari USB

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md` (D-13)
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.
**Dijalankan di:** PC Windows fisik (sesi Claude Code lokal operator), bukan sesi cloud.

---

## 1. Tujuan

D-13 menetapkan Chromium milik Playwright di-bundle di `App/` untuk kebutuhan browsing/skill web. Chromium adalah binary besar (ratusan MB) dan berat I/O saat start. Dari USB (lebih lambat dari SSD internal, dan beberapa model menulis cache secara agresif), ini bisa jadi bottleneck atau sumber keausan (wear) USB. Uji ini mengukur biaya nyatanya — **bukan** untuk memutuskan apakah Chromium tetap dipakai (itu sudah diputuskan D-13), tapi untuk tahu konsekuensi performanya dan apakah perlu mitigasi (misalnya profil Chromium diarahkan ke lokasi tertentu).

Pertanyaan yang dijawab:
1. Berapa lama waktu start-to-ready Chromium dari USB (cold dan warm), dibanding dari disk internal sebagai baseline?
2. Berapa volume tulis (MB) yang terjadi ke USB untuk satu sesi browsing sederhana?
3. Ke mana saja Chromium/Playwright menulis secara default (profil, cache, lock file), dan apakah semuanya bisa diarahkan untuk tetap di USB (sesuai AGENTS.md: semua data di USB, bukan `%TEMP%`/`%APPDATA%` host)?

## 2. Ruang Lingkup

**Termasuk:** script yang menjalankan Playwright-Chromium dari bundle USB untuk beberapa skenario navigasi sederhana, pengukur waktu start dan volume tulis, panduan prosedur.

**Tidak termasuk:** skill web browsing sungguhan, integrasi dengan Agent Core.

## 3. Keputusan Desain yang WAJIB Diikuti

- Chromium yang diuji adalah **binary yang di-install Playwright** (`playwright install chromium`), di-copy ke `App/` sesuai D-13 — bukan Chromium sistem atau Chrome yang mungkin terpasang di PC host.
- Profil dan cache Chromium **wajib** diarahkan ke folder di USB (misalnya `Data/browser-profile/`), **tidak boleh** memakai lokasi default yang jatuh ke `%LOCALAPPDATA%` host (prinsip desain "semua data di USB").

## 4. Larangan (Jangan Dilakukan)

- ❌ Jangan memakai Chrome/Chromium yang sudah terpasang di PC host. Harus Chromium dari bundle Playwright.
- ❌ Jangan membiarkan profil/cache menulis ke `%TEMP%`, `%APPDATA%`, atau `%LOCALAPPDATA%` host — jika ada jalur default yang menulis ke sana, itu adalah temuan penting (bukan untuk ditutupi), catat dan laporkan.
- ❌ Jangan menebak volume tulis atau waktu start. Ukur dengan alat nyata (`Process Monitor` export, atau selisih "bytes written" dari `psutil`/Performance Counter, dan `time.perf_counter`).
- ❌ Jangan matikan GPU/sandbox Chromium "demi kecepatan" tanpa mencatatnya sebagai varian terpisah — baseline harus pakai konfigurasi yang realistis untuk produksi.

## 5. Skenario yang Diukur

| Skenario | Deskripsi |
|---|---|
| `cold-launch` | USB baru dicabut-colok, buka Chromium, navigasi ke satu halaman lokal statis (file HTML sederhana, bukan internet, agar hasil tidak tercampur variabilitas jaringan), tutup |
| `warm-launch` | Ulangi langsung tanpa cabut-colok |
| `session-5pages` | Satu sesi, navigasi ke 5 halaman lokal statis berurutan, lalu tutup — untuk mengukur volume tulis per sesi yang lebih realistis |
| `baseline-ssd` | Ulangi `cold-launch` dan `session-5pages` dengan bundle disalin sementara ke disk internal, sebagai pembanding — dihapus setelah uji |

Gunakan beberapa halaman HTML statis lokal (bukan ambil dari internet) supaya hasil reproducible dan tidak bergantung jaringan — buat 5 halaman contoh sederhana (boleh ada gambar kecil dan sedikit JS) sebagai fixture.

## 6. Prosedur Uji (oleh operator manusia)

1. Siapkan Chromium dari Playwright di `App/` sesuai D-13, arahkan profil ke `Data/browser-profile/` di USB (lihat bagian 3).
2. Untuk tiap skenario di bagian 5, jalankan **5 kali** (kecuali `baseline-ssd` cukup 3 kali), catat:
   - Waktu dari proses Chromium di-spawn sampai halaman pertama selesai load (`load` event).
   - Total bytes written ke USB selama skenario berjalan (pakai `psutil.Process().io_counters()` pada proses Chromium dan child-process-nya, atau Resource Monitor Windows sebagai pembanding).
3. Setelah semua skenario, periksa isi `Data/browser-profile/` dan catat ukurannya serta jenis file di dalamnya (cache, cookies, lock file, dll).
4. Periksa apakah ada jejak tulis di luar USB (`%LOCALAPPDATA%\...\Chromium`, `%TEMP%`) — gunakan `Process Monitor` (Sysinternals) dengan filter path, jalankan singkat selama satu skenario `cold-launch` untuk memverifikasi, lalu matikan.

## 7. Kriteria Lulus

Uji ini **tidak punya target pass/fail** di `decisions.md` bagian 10 (kriterianya "Waktu start dan volume tulis tercatat") — ini uji pengumpulan data, bukan validasi ambang batas. Yang **wajib**:

| Kriteria | Sifat |
|---|---|
| Waktu start (cold/warm) dan volume tulis tercatat untuk semua skenario bagian 5 | **Wajib** |
| 0 jejak tulis di luar USB (`%TEMP%`/`%APPDATA%`/`%LOCALAPPDATA%` host) | **Wajib** — jika gagal, ini jadi temuan penting untuk desain launcher, bukan kriteria lulus/gagal uji ini |

## 8. Deliverable

```
spikes/uji07-chromium/
├── run_scenario.py       spawn Chromium, ukur waktu dan I/O
├── fixtures/             5 halaman HTML statis lokal
└── README.md
results/
└── uji07-chromium.md
```

**Jangan commit** binary Chromium atau folder profil browser. Tambahkan ke `.gitignore`.

Isi `results/uji07-chromium.md`:
1. **Lingkungan:** OS, merek/jenis USB, port USB (3.x/2.0).
2. **Tabel hasil** per skenario: median/maksimum waktu start, median volume tulis.
3. **Lokasi tulis** yang teramati (profil, cache) dan hasil verifikasi Process Monitor.
4. **Catatan** jika ada jejak tulis di luar USB, dan saran mitigasinya.

## 9. Definisi Selesai

- Semua skenario bagian 5 benar-benar dijalankan dan diukur.
- Verifikasi Process Monitor benar-benar dilakukan, bukan diasumsikan.
- Kode dikerjakan di branch `fase0/uji07`, lalu dibuka pull request ke `main`.
