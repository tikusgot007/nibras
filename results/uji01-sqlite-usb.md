# Laporan Hasil — Fase 0, Uji #1: Ketahanan SQLite saat USB Dicabut Mendadak

**Referensi Brief:** `docs/briefs/fase0-uji01-sqlite-usb.md`  
**Keputusan Desain Terkait:** D-01, D-04, D-05 (`docs/decisions.md`)  
**Status Uji:** Siap dijalankan oleh operator manusia (Template Laporan)

---

## 1. Lingkungan Uji

| Komponen | Spesifikasi / Nilai |
|---|---|
| Sistem Operasi | Windows 10 / 11 (build: ...) |
| Versi Python | Python 3.11+ (versi: ...) |
| Versi SQLite | ... (dari `sqlite3.sqlite_version`) |
| Modul FTS5 | Tersedia / Tidak |
| Merek & Model USB | ... |
| Kapasitas USB | ... GB |
| Antarmuka USB | USB 3.x / USB 2.0 |
| Sistem File | NTFS (Wajib) |
| Kebijakan Removal | Quick removal / Better performance |

---

## 2. Tabel Hasil Uji (20 Run di NTFS)

| Run ID | Durasi Cabut | Opsi `--fts` | Hot Journal Ada? | `integrity_check` (Core / Mem / FTS) | `MAX(seq)` Core | `MAX(seq)` Mem | `seq` Host Log | Tx Hilang | Prompt Scan & Fix? | Status (PASS/FAIL) |
|---|---|---|---|---|---|---|---|---|---|---|
| run-01 | ~10 detik | Tidak | | | | | | | | |
| run-02 | ~10 detik | Tidak | | | | | | | | |
| run-03 | ~10 detik | Tidak | | | | | | | | |
| run-04 | ~10 detik | Tidak | | | | | | | | |
| run-05 | ~10 detik | Ya | | | | | | | | |
| run-06 | ~10 detik | Ya | | | | | | | | |
| run-07 | ~10 detik | Ya | | | | | | | | |
| run-08 | ~30 detik | Tidak | | | | | | | | |
| run-09 | ~30 detik | Tidak | | | | | | | | |
| run-10 | ~30 detik | Tidak | | | | | | | | |
| run-11 | ~30 detik | Ya | | | | | | | | |
| run-12 | ~30 detik | Ya | | | | | | | | |
| run-13 | ~30 detik | Ya | | | | | | | | |
| run-14 | ~30 detik | Ya | | | | | | | | |
| run-15 | ~2 menit | Tidak | | | | | | | | |
| run-16 | ~2 menit | Tidak | | | | | | | | |
| run-17 | ~2 menit | Ya | | | | | | | | |
| run-18 | ~2 menit | Ya | | | | | | | | |
| run-19 | ~2 menit | Ya | | | | | | | | |
| run-20 | ~2 menit | Ya | | | | | | | | |

*(Opsional: Uji Pembanding 5 Run di exFAT)*

| Run ID | Durasi Cabut | Opsi `--fts` | Hot Journal Ada? | `integrity_check` | `MAX(seq)` Core / Mem | `seq` Host Log | Tx Hilang | Prompt Scan & Fix? | Status (PASS/FAIL) |
|---|---|---|---|---|---|---|---|---|---|
| exfat-01 | ~10 detik | Ya | | | | | | | |
| exfat-02 | ~10 detik | Ya | | | | | | | |
| exfat-03 | ~30 detik | Ya | | | | | | | |
| exfat-04 | ~30 detik | Ya | | | | | | | |
| exfat-05 | ~2 menit | Ya | | | | | | | |

---

## 3. Metrik Performa

- **Throughput Rata-rata:** ... tx/s
- **Throughput Minimum:** ... tx/s
- **Throughput Maksimum:** ... tx/s

---

## 4. Evaluasi Kriteria Kelulusan

Sesuai Bagian 8 `docs/briefs/fase0-uji01-sqlite-usb.md`:

| Kriteria | Target | Hasil Nyata | Status |
|---|---|---|---|
| Kegagalan `integrity_check` | 0 dari 20 run | ... | [ ] LULUS / [ ] GAGAL |
| Ketidaksamaan `MAX(seq)` antar DB | 0 | ... | [ ] LULUS / [ ] GAGAL |
| Celah sequence atau checksum rusak | 0 | ... | [ ] LULUS / [ ] GAGAL |
| Transaksi hilang per run | Maksimal 1 tx | ... | [ ] LULUS / [ ] GAGAL |

**Kesimpulan Evaluasi:**  
(Diisi setelah 20 run fisik selesai dieksekusi: apakah keputusan D-01 tervalidasi atau perlu ditinjau ulang).

---

## 5. Catatan dan Anomali

- *Catatan observasi perilaku sistem file NTFS saat pencabutan:*
- *Catatan kemunculan pesan prompt Windows Scan and Fix:*
- *Observasi hot journal rollback:*
