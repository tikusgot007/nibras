# Panduan Uji — Fase 0, Uji #1: Ketahanan SQLite saat USB Dicabut Mendadak

Dokumen ini memandu pelaksanaan **Uji #1 Fase 0** proyek **Nibras**: menguji ketahanan SQLite dalam mode rollback journal (`PRAGMA journal_mode=DELETE` dan `PRAGMA synchronous=FULL`) pada drive USB berformat **NTFS** terhadap pencabutan mendadak saat transaksi aktif.

---

## 1. Persiapan Lingkungan

1. **Format USB Drive**:
   - Format USB sebagai **NTFS** (wajib untuk uji utama).
   - Catat detail drive: merek, kapasitas, antarmuka (USB 2.0 / USB 3.x).
   - Periksa kebijakan penghapusan di Windows Device Manager:
     - Buka `Device Manager` -> `Disk drives` -> klik kanan USB drive -> `Properties` -> tab `Policies`.
     - Catat apakah pengaturannya **Quick removal** (default Windows) atau **Better performance**.
2. **Kebutuhan Software**:
   - Python 3.11+ bawaan / sistem (hanya memakai standard library).
   - Pastikan path terminal berada di root repository `nibras`.

---

## 2. Struktur Script

- `writer.py`: Menulis transaksi berkesinambungan secara atomik ke dua database (`core_test.db` dan `memory_test.db` via `ATTACH`) dengan payload BLOB dan checksum SHA-256. Setiap commit sukses dicatat ke log di PC host.
- `checker.py`: Memeriksa keberadaan hot journal sebelum dibuka, membuka database dengan mode read-write untuk memicu rollback otomatis, menjalankan `integrity_check` penuh, memastikan `MAX(seq)` konsisten, mendeteksi celah sequence, memverifikasi seluruh checksum baris, menguji FTS5, dan membandingkan transaksi dengan host log.
- `summarize.py`: Membaca seluruh file JSON hasil uji di folder `results/` lalu mencetak tabel ringkasan format Markdown yang siap disalin ke laporan hasil.

---

## 3. Parameter Script

### `writer.py`

```bash
python spikes/uji01-sqlite-usb/writer.py \
  --db-dir "<drive_usb>:\uji01_db" \
  --host-log "<path_pc_host>\host_tx.log" \
  [--payload-bytes 1024] \
  [--fts]
```

- `--db-dir` (wajib): Direktori target di USB tempat database disimpan.
- `--host-log` (wajib): Path file log di disk PC host (misal `C:\Temp\host_tx.log`). File ini mencatat transaksi yang sudah sukses di-commit.
- `--payload-bytes` (opsional, default: 1024): Ukuran payload biner per transaksi.
- `--fts` (opsional): Menambahkan penulisan ke tabel virtual FTS5 (`entries_fts`).

### `checker.py`

```bash
python spikes/uji01-sqlite-usb/checker.py \
  --db-dir "<drive_usb>:\uji01_db" \
  --host-log "<path_pc_host>\host_tx.log" \
  --run-id "run-01" \
  --out "results/run-01.json" \
  [--duration "~10 detik"] \
  [--scan-fix "Tidak"]
```

- `--db-dir` (wajib): Direktori database di USB.
- `--host-log` (wajib): Path file log di PC host.
- `--run-id` (wajib): Penanda nomor run (misal `run-01`).
- `--out` (wajib): Path file JSON output hasil evaluasi.
- `--duration` (opsional): Durasi sebelum cabut (misal `~10 detik`).
- `--scan-fix` (opsional): Kemunculan prompt Windows Scan and Fix (`Ya` / `Tidak`).

### `summarize.py`

```bash
python spikes/uji01-sqlite-usb/summarize.py [--dir "results"]
```

- `--dir` (opsional, default: `results`): Direktori penyimpanan file JSON hasil pemeriksaan. Output dicetak sebagai tabel Markdown ke stdout.

---

## 4. Prosedur Uji 20 Run (Operator Manusia)

Ulangi langkah berikut sebanyak **20 kali** di drive USB NTFS:

1. **Jalankan `writer.py`**:
   - Buka PowerShell / Terminal di PC host.
   - Eksekusi `writer.py` dengan parameter yang sesuai.
   - Perhatikan log console menampilkan throughput setiap 5 detik.
2. **Biarkan Berjalan**:
   - Biarkan script menulis data minimal 10 detik.
   - Variasikan durasi berjalan sebelum dicabut:
     - Run 1–7: cabut setelah ~10 detik.
     - Run 8–14: cabut setelah ~30 detik.
     - Run 15–20: cabut setelah ~2 menit.
   - Gunakan opsi `--fts` pada minimal 10 dari 20 run.
3. **Cabut USB Fisik**:
   - **Cabut USB secara mendadak** langsung dari port tanpa menggunakan fitur "Safely Remove Hardware".
   - `writer.py` akan menangkap disconnect I/O error atau dihentikan.
4. **Tancapkan Kembali USB**:
   - Tunggu sekitar 5 detik, lalu colokkan kembali USB ke PC.
   - Jika Windows menampilkan dialog/prompt *"There is a problem with this drive... Scan and fix"*, **JANGAN JALANKAN SCAN / FIX**. Tutup dialog tersebut agar sistem file tidak dimodifikasi oleh chkdsk sebelum pemeriksaan database.
   - Catat apakah prompt Windows tersebut muncul.
5. **Jalankan `checker.py`**:
   - Jalankan `checker.py` dengan `--run-id` yang sesuai (misal `run-01`, `run-02`, dst.).
   - Pastikan output mencatat status PASS/FAIL dan exit code adalah `0`.
6. **Lanjut ke Run Berikutnya**:
   - Jangan hapus file database di USB; `writer.py` otomatis melanjutkan dari `MAX(seq) + 1`, menguji akumulasi data dan pemulihan berulang.
7. *(Opsional)* Lakukan 5 run tambahan pada USB berformat **exFAT** sebagai perbandingan.

---

## 5. Kriteria Lulus Uji

- **0** kegagalan `PRAGMA integrity_check` dari seluruh 20 run di NTFS.
- **0** ketidaksamaan `MAX(seq)` antara `core_test.db` dan `memory_test.db` (atomisitas `ATTACH DATABASE` terjaga).
- **0** celah urutan (`seq`) dan **0** ketidakcocokan checksum SHA-256.
- Maksimal **1** transaksi hilang per run (selisih antara host log dan database).

---

## 6. Pengisian Laporan Hasil

Hasil dari setiap run disimpan di file JSON (`--out`). Setelah 20 run selesai, rangkum hasilnya ke dalam template dokumen `results/uji01-sqlite-usb.md`.
