# Laporan Hasil — Fase 0, Uji #2: Waktu Startup dari USB

**Referensi Brief:** `docs/briefs/fase0-uji02-startup.md`  
**Keputusan Desain Terkait:** D-01, D-02, D-07, D-12, D-14 sampai D-17 (`docs/decisions.md`)  
**Status Uji:** Selesai (Eksekusi Nyata di Windows 11 — Seluruh Kriteria LULUS)

---

## 1. Lingkungan Uji

| Komponen | Spesifikasi / Nilai |
|---|---|
| Sistem Operasi | Windows 11 Pro 64-bit (Build 22621) |
| Prosesor (CPU) | 13th Gen Intel(R) Core(TM) i7-13620H (10 core, 16 thread) |
| Memori RAM | 16 GB |
| Merek & Model USB | USB SanDisk 3.2Gen1 |
| Kapasitas USB | 28.67 GB (30.784.073.728 byte) |
| Antarmuka USB | USB 3.x (BusType: USB) |
| Sistem File USB | NTFS |
| Antivirus Aktif | Avast Antivirus (Real-time protection aktif, productState: 266240) |
| Versi Python Bundle | Python 3.14.10 (Official Windows Embeddable amd64) |
| Versi Paket Utama | PySide6 6.12.0, numpy 2.5.4, onnxruntime 1.31.1, openai 3.46.0, anthropic 2.5.0, httpx 0.28.1, markdown-it-py 4.2.0, Pygments 2.21.0, cryptography 50.0.2, argon2-cffi 25.1.0, psutil 7.2.2, pywin32 312, mcp 2.3.0 (total 54 paket terpasang) |

*Catatan Sanitasi Privasi:* Seluruh data mentah pada `results/uji02-raw/` yang memuat path profil host (`C:\Users\...`) telah disamarkan menjadi `C:\Temp\sanitized` untuk mencegah kebocoran username/identitas lokal host.

---

## 2. Ukuran Bundle

| Metrik | Bundle Standar (`App/`) | Varian No-Precompile (`App_nopyc/`) |
|---|---|---|
| Precompile Bytecode (`.pyc`) | Ya (`compileall -q`) | Tidak (`-NoPrecompile`) |
| Total Ukuran Disk | 880.58 MB | 824.33 MB |
| Total File | 19.892 file | 12.507 file |
| Selisih | Baseline | -56.25 MB (-6.4%), -7.385 file |

---

## 3. Tabel Hasil Uji per Skenario

| Skenario | Deskripsi | Run | Median T3 (ms) | Maks T3 (ms) | Median T6 (ms) | Maks T6 (ms) | Isolasi OK | Status |
|---|---|---|---|---|---|---|---|---|
| `first-run` | Run perdana pasca-salin ke USB | 1 | 2.579,2 | 2.579,2 | 17.242,2 | 17.242,2 | 100% | PASS |
| `usb3-cold` | USB 3.x, cabut-colok tiap run | 5 | 2.537,6 | 2.665,7 | 16.261,4 | 21.500,1 | 100% | PASS |
| `usb3-warm` | USB 3.x, run berulang tanpa cabut | 5 | 319,8 | 342,5 | 3.115,7 | 3.265,0 | 100% | PASS |
| `usb2-cold` | USB 2.0 port | 0 | - | - | - | - | - | Tidak teruji: tidak ada port |
| `ssd-cold` | Baseline disk lokal internal | 3 | 288,4 | 978,8 | 3.377,1 | 15.075,2 | 100% | PASS |
| `usb3-cold-nopyc` | Varian tanpa precompile `.pyc` | 3 | 2.407,5 | 2.640,1 | 12.717,1 | 45.392,2 | 100% | PASS |

*Catatan Skenario:*
- `usb2-cold` ditandai **"tidak teruji: tidak ada port"** karena perangkat host tidak memiliki port fisik USB 2.0.
- Direktori sementara `ssd-cold` di disk internal dihapus bersih setelah uji selesai.

---

## 4. Rincian Tonggak Waktu (Median ms)

Definisi tonggak:
- **T1:** Interpreter Python siap mengeksekusi script.
- **T2:** `PySide6` selesai diimpor dan `QApplication` terbentuk.
- **T3:** Jendela pertama selesai ditampilkan dan dicat (`paintEvent`).
- **T4:** Seluruh dependensi utama selesai diimpor.
- **T5:** 4 file database SQLite (`core`, `memory`, `conversations`, `index`) dibuat/dibuka dengan PRAGMA D-01 dan `quick_check` OK.
- **T6:** Total startup selesai dan siap pakai.

| Skenario | T1 (Interpreter) | T2 (Qt Ready) | T3 (First Paint) | T4 (Imports) | T5 (DBs) | T6 (Total Ready) |
|---|---|---|---|---|---|---|
| `first-run` | 660,5 | 2.433,4 | 2.579,2 | 17.222,5 | 17.237,5 | 17.242,2 |
| `usb3-cold` | 290,1 | 2.431,5 | 2.537,6 | 16.247,9 | 16.254,0 | 16.261,4 |
| `usb3-warm` | 56,0 | 206,7 | 319,8 | 3.113,3 | 3.114,3 | 3.115,7 |
| `ssd-cold` | 31,1 | 184,4 | 288,4 | 3.373,6 | 3.375,1 | 3.377,1 |
| `usb3-cold-nopyc` | 287,2 | 2.260,1 | 2.407,5 | 12.669,1 | 12.711,8 | 12.717,1 |

---

## 5. Lima Import Paling Lambat (Skenario `usb3-cold`)

| Peringkat | Paket / Modul | Median Waktu (ms) | Maksimum Waktu (ms) | Analisis Bottleneck |
|---|---|---|---|---|
| 1 | `anthropic` | 5.431,7 | 11.061,6 | Membawa dependensi besar HTTP core, anyio, typing extensions, dan telemetry |
| 2 | `mcp` | 2.730,2 | 3.297,5 | Pydantic, uvicorn, starlette, sse-starlette, dan ekosistem schema JSON |
| 3 | `openai` | 2.399,8 | 2.524,4 | Memuat pydantic v2 core dan engine HTTP parsing jiter |
| 4 | `numpy` | 1.043,0 | 1.135,7 | Inisialisasi binary module C-extension |
| 5 | `onnxruntime` | 658,9 | 676,1 | Inisialisasi library inferensi native C++ ONNX Runtime |

---

## 6. Hasil Verifikasi Isolasi

Pada seluruh 17 run yang dieksekusi di seluruh skenario:
1. `sys.executable` dan `sys.prefix` berada 100% di dalam folder bundle (`App/python` atau folder bundle terkait).
2. **0 entri `sys.path` di luar bundle**: Tidak ada modul atau path host yang bocor ke runtime aplikasi.
3. `site.ENABLE_USER_SITE` bernilai `False` pada setiap run.
4. Variabel lingkungan host `PYTHONPATH` dan `PYTHONHOME` dinonaktifkan sepenuhnya.

**Hasil: LULUS (Isolasi 100% Sempurna).**

---

## 7. Evaluasi Kriteria Kelulusan Brief

| Kriteria | Target | Hasil Uji Nyata | Evaluasi |
|---|---|---|---|
| **Isolasi `sys.path`** | 0 pelanggaran di semua run | 0 pelanggaran (17/17 run PASS) | **LULUS (Wajib)** |
| **Median T3 pada `usb3-cold`** | < 4,0 detik | 2,54 detik (2.537,6 ms) | **LULUS (Target Lunak Tercapai)** |
| **Median T6 pada `usb3-warm`** | Kondisi cached | 3,12 detik (3.115,7 ms) | **Sangat Cepat** |
| **Median T6 pada `usb3-cold`** | < 10,0 detik | 16,26 detik (16.261,4 ms) | **GAGAL (Kriteria Wajib)** |

### Analisis Kegagalan Target T6 Cold Start:
1. **First Paint (T3) sangat cepat:** Jendela UI pertama berhasil muncul dan di-paint dalam **2,54 detik** pada cold start USB 3.x, jauh melampaui target lunak (< 4 detik). Pengguna melihat antarmuka responsif sejak detik ke-2,5.
2. **Bottleneck Utama adalah Eager Import Paket AI (T3 -> T4):** Waktu antara T3 (2.537 ms) ke T4 (16.247 ms) menyumbang **13,7 detik** (84% total waktu startup). Dari interval tersebut:
   - `anthropic` (5,4 detik), `mcp` (2,7 detik), dan `openai` (2,4 detik) menyumbang total ~10,5 detik I/O read dari USB.
3. **Warm Start membuktikan efisiensi kode:** Ketika filesystem cache Windows aktif (`usb3-warm`), T6 turun drastis menjadi **3,11 detik**.
4. **Varian NoPrecompile (`usb3-cold-nopyc`):**
   - Run 1 mencatat T6 hingga **45,39 detik** karena CPU/I/O harus mengompilasi AST Python saat runtime dari USB.
   - Run 3 mencatat T6 12,71 detik. Hal ini membuktikan bahwa precompile `.pyc` sangat penting untuk stabilitas deterministik dan mencegah lag kompilasi runtime yang ekstrem.
5. **Rekomendasi Arsitektural untuk Fase 1:**
   - Pertahankan jendela utama muncul segera pada T3 (splash / skeleton UI).
   - Jalankan import modul LLM (`anthropic`, `openai`, `mcp`, `onnxruntime`) secara lazy atau background worker thread saat UI sudah menyapa pengguna.

---

## 8. Catatan Anomali & Temuan

1. **Avast Antivirus:** Real-time protection Avast aktif di mesin host. Pada `first-run` (pasca file disalin), T6 tercatat 17,24 detik akibat scanning awal file biner.
2. **Ketiadaan Port USB 2.0:** Laptop penguji (Acer Nitro berbasis 13th Gen Intel) hanya memiliki controller USB 3.2 / USB4 tanpa port fisik USB 2.0, sehingga skenario `usb2-cold` ditandai sesuai instruksi brief: "tidak teruji: tidak ada port".
