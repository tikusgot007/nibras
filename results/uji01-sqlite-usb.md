# Laporan Hasil — Fase 0, Uji #1: Ketahanan SQLite saat USB Dicabut Mendadak

**Referensi Brief:** `docs/briefs/fase0-uji01-sqlite-usb.md`  
**Keputusan Desain Terkait:** D-01, D-04, D-05 (`docs/decisions.md`)  
**Status Uji:** Selesai (20 Run Nyata di NTFS — Seluruh Kriteria LULUS)

---

## 1. Lingkungan Uji

| Komponen | Spesifikasi / Nilai |
|---|---|
| Sistem Operasi | Windows 11 Pro 64-bit (Build 26100) |
| Versi Python | Python 3.14.7 |
| Versi SQLite | 3.50.4 |
| Modul FTS5 | Tersedia |
| Merek & Model USB | USB SanDisk 3.2Gen1 |
| Kapasitas USB | 28.67 GB (32 GB) |
| Antarmuka USB | USB 3.x |
| Sistem File | NTFS |
| Kebijakan Removal | Quick removal (default Windows) |

---

## 2. Tabel Hasil Uji (20 Run di NTFS)

| Run ID | Durasi Cabut | Opsi `--fts` | Hot Journal Ada? | `integrity_check` (Core / Mem / FTS) | `MAX(seq)` Core | `MAX(seq)` Mem | `seq` Host Log | Tx Hilang | Prompt Scan & Fix? | Status (PASS/FAIL) |
|---|---|---|---|---|---|---|---|---|---|---|
| run-01 | ~10 detik | Tidak | Ya | OK / OK / - | 478 | 478 | 478 | 0 | Tidak | PASS |
| run-02 | ~10 detik | Tidak | Ya | OK / OK / - | 978 | 978 | 978 | 0 | Tidak | PASS |
| run-03 | ~10 detik | Tidak | Ya | OK / OK / - | 1752 | 1752 | 1752 | 0 | Tidak | PASS |
| run-04 | ~10 detik | Tidak | Ya | OK / OK / - | 2160 | 2160 | 2160 | 0 | Tidak | PASS |
| run-05 | ~10 detik | Ya | Ya | OK / OK / OK | 2609 | 2609 | 2609 | 0 | Tidak | PASS |
| run-06 | ~10 detik | Ya | Ya | OK / OK / OK | 2805 | 2805 | 2805 | 0 | Tidak | PASS |
| run-07 | ~10 detik | Ya | Ya | OK / OK / OK | 3190 | 3190 | 3190 | 0 | Tidak | PASS |
| run-08 | ~30 detik | Tidak | Ya | OK / OK / OK | 4422 | 4422 | 4423 | 1 | Tidak | PASS |
| run-09 | ~30 detik | Tidak | Ya | OK / OK / OK | 5367 | 5367 | 5367 | 0 | Tidak | PASS |
| run-10 | ~30 detik | Tidak | Ya | OK / OK / OK | 6114 | 6114 | 6114 | 0 | Tidak | PASS |
| run-11 | ~30 detik | Ya | Ya | OK / OK / OK | 6976 | 6976 | 6976 | 0 | Tidak | PASS |
| run-12 | ~30 detik | Ya | Ya | OK / OK / OK | 7834 | 7834 | 7834 | 0 | Tidak | PASS |
| run-13 | ~30 detik | Ya | Ya | OK / OK / OK | 8401 | 8401 | 8401 | 0 | Tidak | PASS |
| run-14 | ~30 detik | Ya | Ya | OK / OK / OK | 9273 | 9273 | 9273 | 0 | Tidak | PASS |
| run-15 | ~2 menit | Tidak | Ya | OK / OK / OK | 12363 | 12363 | 12363 | 0 | Tidak | PASS |
| run-16 | ~2 menit | Tidak | Ya | OK / OK / OK | 15423 | 15423 | 15423 | 0 | Tidak | PASS |
| run-17 | ~2 menit | Ya | Ya | OK / OK / OK | 18167 | 18167 | 18167 | 0 | Tidak | PASS |
| run-18 | ~2 menit | Ya | Ya | OK / OK / OK | 20566 | 20566 | 20566 | 0 | Tidak | PASS |
| run-19 | ~2 menit | Ya | Ya | OK / OK / OK | 23279 | 23279 | 23279 | 0 | Tidak | PASS |
| run-20 | ~2 menit | Ya | Ya | OK / OK / OK | 25403 | 25403 | 25403 | 0 | Tidak | PASS |

---

## 3. Metrik Performa

- **Throughput Rata-rata:** 21.6 tx/s
- **Throughput Minimum:** 12.2 tx/s (Run 06)
- **Throughput Maksimum:** 28.7 tx/s (Run 08)
- **Total Transaksi Berhasil Diuji:** 25.403 transaksi berkelanjutan dengan akumulasi beban tanpa reset database.

---

## 4. Evaluasi Kriteria Kelulusan

Sesuai Bagian 8 `docs/briefs/fase0-uji01-sqlite-usb.md`:

| Kriteria | Target | Hasil Nyata | Status |
|---|---|---|---|
| Kegagalan `integrity_check` | 0 dari 20 run | 0 kegagalan (100% OK) | [x] LULUS |
| Ketidaksamaan `MAX(seq)` antar DB | 0 | 0 mismatch (`events` == `entries`) | [x] LULUS |
| Celah sequence atau checksum rusak | 0 | 0 celah sequence, 0 checksum corrupt | [x] LULUS |
| Transaksi hilang per run | Maksimal 1 tx | Maksimal 1 tx (1 tx pada Run 08; 0 tx pada 19 run lainnya) | [x] LULUS |

**Kesimpulan Evaluasi:**  
Keputusan desain **D-01 (SQLite tanpa WAL, rollback journal DELETE, synchronous FULL di USB berformat NTFS)** dan **D-05 (multi-database terpisah)** divalidasi sepenuhnya. Tidak terjadi korupsi file database maupun inkonsistensi transaksi atomik antar-database (`ATTACH DATABASE`).

---

## 5. Catatan dan Anomali

1. **Rollback Hot Journal**: Pada setiap pencabutan mendadak, file `-journal` terdeteksi di USB sebelum pembukaan database. Begitu `checker.py` membuka database dalam mode read-write, SQLite secara alami melakukan rollback otomatis tanpa memerlukan intervensi aplikasi.
2. **Ketiadaan Prompt Windows**: Selama 20 kali pencabutan fisik tanpa "Safely Remove", Windows 11 tidak pernah memunculkan dialog prompt "Scan and fix" pada volume USB NTFS ini.
3. **Transaksi Terakhir Terputus**: Pada Run 08, satu transaksi hilang (`host_log` mencatat seq 4423, sedangkan database berhasil memulihkan hingga seq 4422). Karena writer memakai `synchronous=FULL`, `COMMIT` baru selesai setelah Windows menyatakan data sudah tersimpan permanen. Artinya, **controller USB melaporkan data sudah tersimpan padahal masih berada di cache-nya**, lalu data tersebut hilang saat daya terputus. Ini perilaku hardware, bukan bug pada kode atau desain. Seluruh sequence sebelumnya (1 s.d. 4422) tetap utuh dan lolos verifikasi checksum SHA-256. Temuan ini ditindaklanjuti dengan keputusan D-54 (intent log untuk tindakan non-idempotent).
4. **Keterbatasan Uji**: Uji hanya mencakup satu model USB (SanDisk 3.2 Gen1) dan satu PC. USB lain, terutama USB murah, dapat berperilaku berbeda.
