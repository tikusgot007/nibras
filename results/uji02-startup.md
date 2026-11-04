# Laporan Hasil — Fase 0, Uji #2: Waktu Startup dari USB

**Referensi Brief:** `docs/briefs/fase0-uji02-startup.md`  
**Keputusan Desain Terkait:** D-02, D-07, D-12, D-14 sampai D-17 (`docs/decisions.md`)  
**Status Uji:** Siap dijalankan oleh operator manusia (Template Laporan)

---

## 1. Lingkungan Uji

| Komponen | Spesifikasi / Nilai |
|---|---|
| Sistem Operasi | Windows 10 / 11 64-bit (build: ...) |
| CPU | ... |
| RAM | ... GB |
| Merek & Model USB | ... |
| Kapasitas USB | ... GB |
| Antarmuka USB | USB 3.x / USB 2.0 |
| Status Windows Defender / Antivirus | Aktif / Non-aktif |
| Versi Python Runtime | Python 3.12.9 Embeddable (Windows x86-64) |
| Alasan Pemilihan Versi Python | Versi stabil terbaru dengan ketersediaan wheel biner resmi Windows (`win_amd64`) untuk seluruh 13 paket dependency tanpa kompilasi C di PC host |

### Versi Paket Dependency (`App/BUILD_INFO.json`):
- `PySide6`: ...
- `numpy`: ...
- `onnxruntime`: ...
- `openai`: ...
- `anthropic`: ...
- `httpx`: ...
- `markdown-it-py`: ...
- `Pygments`: ...
- `cryptography`: ...
- `argon2-cffi`: ...
- `psutil`: ...
- `pywin32`: ...
- `mcp`: ...

---

## 2. Ukuran Bundle Runtime (`App/`)

| Varian Bundle | Ukuran Total (MB) | Total Jumlah File | Keterangan |
|---|---|---|---|
| Standar (Precompiled `.pyc`) | ... MB | ... file | Precompile via `compileall` saat build |
| Tanpa Precompile (`-NoPrecompile`) | ... MB | ... file | Hanya source `.py` tanpa cache `.pyc` |

---

## 3. Tabel Hasil Uji Waktu Startup per Skenario

| Skenario | Run | Median T3 (ms) | Maks T3 (ms) | Median T6 (ms) | Maks T6 (ms) | Isolasi OK | Status |
|---|---|---|---|---|---|---|---|
| `usb3-cold` | 5 | | | | | | |
| `usb3-warm` | 5 | | | | | | |
| `usb2-cold` | 3 | | | | | | |
| `ssd-cold` | 3 | | | | | | |
| `usb3-cold-nopyc` | 3 | | | | | | |

---

## 4. Rincian Tonggak Waktu (Median ms per Skenario)

| Skenario | T1 (Interpreter) | T2 (Qt Ready) | T3 (First Paint) | T4 (Imports) | T5 (DBs) | T6 (Total Ready) |
|---|---|---|---|---|---|---|
| `usb3-cold` | | | | | | |
| `usb3-warm` | | | | | | |
| `usb2-cold` | | | | | | |
| `ssd-cold` | | | | | | |
| `usb3-cold-nopyc` | | | | | | |

---

## 5. Lima Import Paling Lambat (`usb3-cold`)

| Peringkat | Paket / Modul | Median Waktu (ms) | Maksimum Waktu (ms) |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

---

## 6. Hasil Verifikasi Isolasi Lingkungan

- **`sys.executable` & `sys.prefix` di dalam bundle:** [ ] Ya / [ ] Tidak
- **Entri `sys.path` di luar folder bundle:** 0 path (100% terisolasi)
- **`site.ENABLE_USER_SITE`:** `False` / `None`
- **Pengaruh `PYTHONPATH` / `PYTHONHOME` host:** Terabaikan sepenuhnya saat runtime

---

## 7. Evaluasi Kriteria Kelulusan

Sesuai Bagian 9 `docs/briefs/fase0-uji02-startup.md`:

| Kriteria | Target | Sifat | Hasil Nyata | Status |
|---|---|---|---|---|
| Median T6 pada `usb3-cold` | < 10.000 ms (< 10 detik) | **Wajib** | ... ms | [ ] LULUS / [ ] GAGAL |
| Isolasi `sys.path` | 0 pelanggaran di semua run | **Wajib** | 0 pelanggaran | [ ] LULUS / [ ] GAGAL |
| Median T3 pada `usb3-cold` | < 4.000 ms (< 4 detik) | Target lunak | ... ms | [ ] TERCAPAI / [ ] TERTUNDA |
| `usb2-cold`, `ssd-cold`, `usb3-cold-nopyc` | Dicatat sebagai pembanding | Informasi | Data tercatat | [ ] OK |

---

## 8. Catatan dan Anomali

- *Hasil `first-run` (pemindaian antivirus/Defender pertama kali setelah copy):*
- *Pengaruh precompilation `.pyc` terhadap performa cold startup USB:*
- *Bottleneck modul dan rekomendasi optimasi startup MVP:*
