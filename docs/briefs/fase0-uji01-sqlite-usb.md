# Brief Tugas — Fase 0, Uji #1: Ketahanan SQLite saat USB Dicabut Mendadak

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md` (D-01, D-04, D-05)
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.

---

## 1. Tujuan

Membuktikan bahwa SQLite dalam mode **rollback journal (tanpa WAL)** di USB berformat **NTFS** tetap konsisten ketika USB dicabut mendadak saat transaksi sedang ditulis.

Uji ini menjawab dua pertanyaan:
1. Apakah file database pernah rusak (gagal `integrity_check`)?
2. Berapa banyak transaksi yang sudah di-commit tetapi hilang?

## 2. Ruang Lingkup

**Termasuk:**
- Script penulis beban (`writer.py`).
- Script pemeriksa (`checker.py`).
- Panduan prosedur uji (`README.md` di folder spike).
- Template laporan hasil.

**Tidak termasuk:** UI, Agent Core, packaging, dan fitur aplikasi apa pun.

## 3. Keputusan Desain yang WAJIB Diikuti

| Aturan | Nilai |
|---|---|
| Journal mode | `PRAGMA journal_mode=DELETE` (rollback journal) |
| Synchronous | `PRAGMA synchronous=FULL` |
| Lokasi database | Di USB yang diuji (path diberikan lewat argumen) |
| Struktur | **Dua** file database terpisah, `core_test.db` dan `memory_test.db`, untuk meniru D-05 |
| Transaksi lintas database | Melalui `ATTACH DATABASE` dalam **satu** transaksi |
| Dependency | **Hanya Python standard library** (`sqlite3`, `argparse`, `time`, `json`, `os`, `hashlib`, dan sejenisnya) |
| Format USB | NTFS (format utama). exFAT hanya untuk pembanding opsional |

## 4. Larangan (Jangan Dilakukan)

- ❌ Jangan memakai `journal_mode=WAL`, `MEMORY`, atau `OFF`.
- ❌ Jangan memakai `synchronous=OFF` atau `NORMAL`.
- ❌ Jangan menyimpan database di `%TEMP%`, profil pengguna, atau disk PC host.
- ❌ Jangan menghapus atau memindahkan file `-journal` sebelum `checker.py` dijalankan. File ini dibutuhkan SQLite untuk rollback otomatis.
- ❌ Jangan membuka database dalam mode read-only di `checker.py`. Rollback hot journal membutuhkan akses tulis.
- ❌ Jangan menambahkan logika "perbaikan otomatis" atau `VACUUM` di `checker.py`. Tugasnya hanya mengukur.
- ❌ Jangan memakai library pihak ketiga, ORM, PyInstaller, atau framework apa pun.
- ❌ Jangan menebak hasil uji. Semua angka di laporan harus berasal dari eksekusi nyata.

## 5. Spesifikasi `writer.py`

**Argumen:**
- `--db-dir` (wajib): folder di USB.
- `--host-log` (wajib): path file log di disk PC host. Ini **satu-satunya pengecualian** penulisan ke host, karena USB akan dicabut. Log ini hanya untuk keperluan uji dan tidak berlaku untuk aplikasi.
- `--payload-bytes` (default 1024).
- `--fts`: aktifkan juga penulisan ke tabel FTS5.

**Skema:**
- `core_test.db`: tabel `events(seq INTEGER PRIMARY KEY, ts REAL, payload BLOB, checksum TEXT)`.
- `memory_test.db`: tabel `entries(seq INTEGER PRIMARY KEY, ts REAL, text TEXT, checksum TEXT)`. Jika `--fts` aktif, tambahkan tabel virtual FTS5 `entries_fts(text)`.

**Perilaku:**
1. Buka `core_test.db`, lalu `ATTACH` `memory_test.db`. Terapkan PRAGMA di bagian 3 pada **kedua** database.
2. Lanjutkan dari `seq` terakhir yang ada (`MAX(seq) + 1`), sehingga satu pasang database dapat dipakai untuk beberapa kali cabut.
3. Ulangi terus sampai proses mati:
   - `BEGIN`.
   - Insert satu baris dengan `seq` yang sama ke `events` dan `entries` (dan `entries_fts` jika aktif).
   - `COMMIT`.
   - **Setelah** `COMMIT` berhasil, tulis `seq` ke `--host-log`, lalu flush dan `os.fsync`.
4. `checksum` adalah SHA-256 dari isi payload atau teks, untuk mendeteksi data yang rusak diam-diam.
5. Cetak throughput (transaksi per detik) ke console setiap 5 detik.
6. Saat start, catat ke host log: versi Python, `sqlite3.sqlite_version`, ketersediaan FTS5, sistem file volume (NTFS atau exFAT), dan path database.

## 6. Spesifikasi `checker.py`

**Argumen:** `--db-dir`, `--host-log`, `--run-id`, `--out` (file JSON hasil per run).

**Langkah pemeriksaan:**
1. Catat apakah file `-journal` ada **sebelum** database dibuka. Ini menandakan ada hot journal.
2. Buka kedua database dalam mode **read-write** agar SQLite dapat melakukan rollback otomatis.
3. Jalankan `PRAGMA integrity_check` (versi penuh, bukan `quick_check`) pada kedua database.
4. Hitung `MAX(seq)` di `events` dan `entries`. Keduanya harus **sama** sebagai bukti atomisitas lintas database.
5. Pastikan `seq` berurutan tanpa celah (tidak ada lompatan).
6. Verifikasi checksum setiap baris.
7. Bandingkan hasilnya dengan `seq` terakhir di host log:
   - `MAX(seq)` di database lebih kecil dari host log berarti ada **transaksi yang sudah di-commit tetapi hilang**. Catat jumlahnya.
   - `MAX(seq)` di database lebih besar dari host log satu angka masih wajar: commit berhasil, tetapi log belum sempat ditulis.
8. Jika `--fts` aktif, jalankan `INSERT INTO entries_fts(entries_fts) VALUES('integrity-check')`.
9. Tulis hasil ke JSON. Exit code `0` berarti lulus, dan nilai selain `0` berarti gagal.

## 7. Prosedur Uji (oleh operator manusia)

1. Format USB sebagai NTFS. Catat merek, kapasitas, jenis (USB 2.0/3.x), dan kebijakan "Quick removal" atau "Better performance" di Device Manager.
2. Jalankan `writer.py` dan tunggu minimal 10 detik.
3. **Cabut USB fisik** tanpa Safely Remove.
4. Tunggu sekitar 5 detik, lalu colok kembali.
5. Catat apakah Windows menampilkan prompt "Scan and fix". **Jangan** jalankan scan sebelum `checker.py`.
6. Jalankan `checker.py`.
7. Ulangi langkah 2–6 sebanyak **20 kali**. Variasikan waktu cabut (sekitar 10 detik, 30 detik, dan 2 menit), serta jalankan sebagian dengan `--fts`.
8. *(Opsional, pembanding)* Ulangi 5 kali di USB berformat exFAT.

## 8. Kriteria Lulus

- **0** kegagalan `integrity_check` dari 20 run di NTFS.
- **0** ketidaksamaan `MAX(seq)` antara kedua database.
- **0** celah urutan dan **0** checksum yang salah.
- Transaksi yang sudah di-commit tetapi hilang **maksimal 1** per run.

Jika satu saja kriteria gagal, D-01 harus ditinjau ulang. Jangan mengubah PRAGMA untuk "membuat lulus". Laporkan apa adanya.

## 9. Deliverable

```
spikes/uji01-sqlite-usb/
├── writer.py
├── checker.py
└── README.md        cara menjalankan dan prosedur uji
results/
└── uji01-sqlite-usb.md
```

Isi `results/uji01-sqlite-usb.md`:
1. Lingkungan uji: OS, versi Python dan SQLite, ketersediaan FTS5, merek dan jenis USB, sistem file, kebijakan removal.
2. Tabel per run: `run_id`, durasi sebelum cabut, `--fts`, ada hot journal, hasil integrity, `MAX(seq)` kedua database, `seq` di host log, jumlah transaksi hilang, prompt "Scan and fix", lulus atau gagal.
3. Throughput rata-rata (transaksi per detik).
4. Ringkasan: lulus atau gagal terhadap kriteria di bagian 8.
5. Catatan anomali, jika ada.

## 10. Definisi Selesai

- Kode hanya memakai standard library dan berjalan dengan Python 3.11 atau lebih baru di Windows 10/11.
- Semua larangan di bagian 4 dipatuhi.
- Laporan hasil berisi data dari 20 run nyata di NTFS.
- Commit ke branch `fase0/uji01`, lalu buka pull request ke `main` untuk direview.
