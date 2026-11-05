# Hasil Uji #4 — Streaming Respons ~5.000 Token di UI

Semua angka berasal dari eksekusi nyata `spikes/uji04-streaming-ui/ui_probe.py` dengan event loop Qt nyata (jendela tampil, bukan offscreen). Data mentah per run (histogram jeda timer, delta klik, durasi render) ada di `results/uji04-raw/*.json`. Tabel dihasilkan oleh `aggregate.py` dari file-file itu. Tidak ada username, hostname, atau path profil di data mentah (sudah dipindai).

## 1. Lingkungan
- Windows 11 Pro 10.0.26100; Intel Core i7-1065G7 @ 1,30 GHz; RAM 15,7 GB.
- Python 3.14.7; PySide6 6.12.0 (Qt 6.12.0); markdown-it-py 4.2.0; Pygments 2.21.0.
- Laju stream 40 token/detik (ujung atas rentang 20–40 di brief). Tokenizer sederhana (kata, tanda baca, satu karakter CJK per token). Stream berjalan di `QThread` terpisah dan mengirim token lewat Qt signal.
- Fixture: `plain` 5.067 token; `code_heavy` 4.937 token (3 blok kode, masing-masing 205 baris, dengan paragraf di antaranya); `wide_mixed` 5.064 token (tabel 14 kolom, teks CJK dan Arab). Fixture dibuat deterministik oleh `gen_fixtures.py`, bukan teks nyata.
- Mode `full`: render ulang Markdown penuh (`setHtml`) tiap token. Mode `batched`: render ulang tiap N=10 token (+ render akhir).

## 2. Cara pengukuran dan KETERBATASAN
- **Klik dan scroll OTOMATIS, bukan manual.** Tidak ada operator manusia. Scroll: `QTimer` tiap 250 ms ke posisi acak. Klik: `QMouseEvent` di-*post* ke antrean event tombol pada selang acak 0,7–2,2 detik. Delta klik = waktu dari post sampai tombol selesai dicat ulang, sehingga mencakup antrean di main thread. Tidak ada "kesan subjektif operator"; kolom itu tidak diisi.
- Jeda timer = interval tick `QTimer` 16 ms dikurangi 16 ms (dibatasi minimal 0). Baseline idle (10 detik, tanpa stream): p95 0,57 ms, maks 1,67 ms; klik 2,2 ms.
- Run yang dihentikan karena melewati batas 420 detik dicatat `TIMEOUT` dan **tidak punya histogram**, karena proses dimatikan sebelum menulis hasil. `code_heavy` + `full` run 1 dan `wide_mixed` + `full` run 1.
- Durasi stream ideal sekitar 123–127 detik. Stream yang lebih lama dari itu berarti UI tidak mengejar.
- Variasi antar run `full` besar (lihat di bawah). Tiga run per kombinasi tidak cukup untuk memperkirakan distribusi; angka p95 tiap run ditampilkan terpisah, tidak dirata-rata.

## 3. Tabel hasil per run (ms; stream dalam detik)
| fixture | mode | run | status | p95 lag | p99 lag | max lag | p95 klik | max klik | stream s |
|---|---|---|---|---|---|---|---|---|---|
| plain | full | 1 | ok | 13.8 | 36.9 | 19999.6 | 7130.1 | 25969.1 | 154.5 |
| plain | full | 2 | ok | 41.5 | 395.3 | 17928.8 | 13579.0 | 17945.3 | 148.5 |
| plain | full | 3 | ok | 13.4 | 22.4 | 39.1 | 32.6 | 55.1 | 126.7 |
| plain | batched | 1 | ok | 18.6 | 46.3 | 83.8 | 16.7 | 52.4 | 126.7 |
| plain | batched | 2 | ok | 19.4 | 46.4 | 74.4 | 22.8 | 38.4 | 126.7 |
| plain | batched | 3 | ok | 5.0 | 16.7 | 26.6 | 9.6 | 13.7 | 126.7 |
| code_heavy | full | 1 | TIMEOUT | - | - | - | - | - | - |
| code_heavy | full | 2 | ok | 28.6 | 852.6 | 105680.3 | 84483.7 | 107233.5 | 286.9 |
| code_heavy | full | 3 | ok | 35.3 | 200.7 | 34156.4 | 9849.4 | 43240.2 | 172.2 |
| code_heavy | batched | 1 | ok | 62.5 | 122.3 | 188.5 | 31.6 | 40.9 | 123.5 |
| code_heavy | batched | 2 | ok | 53.7 | 113.2 | 168.5 | 26.6 | 30.7 | 123.6 |
| code_heavy | batched | 3 | ok | 15.1 | 46.9 | 66.3 | 6.7 | 14.3 | 123.5 |
| wide_mixed | full | 1 | TIMEOUT | - | - | - | - | - | - |
| wide_mixed | full | 2 | ok | 9.5 | 478.2 | 206043.7 | 68173.1 | 206059.3 | 345.0 |
| wide_mixed | full | 3 | ok | 9.3 | 432.2 | 175238.7 | 114490.4 | 132514.1 | 343.6 |
| wide_mixed | batched | 1 | ok | 153.2 | 206.6 | 469.3 | 75.9 | 317.9 | 126.9 |
| wide_mixed | batched | 2 | ok | 60.5 | 93.9 | 450.4 | 28.5 | 43.8 | 126.7 |
| wide_mixed | batched | 3 | ok | 62.1 | 92.2 | 409.5 | 31.4 | 37.2 | 126.7 |


Kriteria wajib Fase 0: p95 jeda timer < 100 ms dan delta klik < 150 ms.

## 4. Ringkasan per fixture × mode
| Fixture | Mode | Run lulus kriteria wajib | Catatan |
|---|---|---|---|
| plain | full | 1 dari 3 (run 3) | Run 1 dan 2: klik tertahan sampai 26 dan 18 detik; stream molor ke 148–154 detik |
| plain | batched | 3 dari 3 | p95 jeda 5,0–19,4 ms; p95 klik 9,6–22,8 ms |
| code_heavy | full | 0 dari 3 | Run 1 timeout; run 2 klik tertahan 107 detik, stream 287 detik; run 3 p95 klik 9,8 detik |
| code_heavy | batched | 3 dari 3 | p95 jeda 15,1–62,5 ms; tetapi maks jeda sampai 188 ms |
| wide_mixed | full | 0 dari 3 | Run 1 timeout; run 2 dan 3 stream 344–345 detik (±2,7× durasi ideal), klik tertahan 206 dan 133 detik |
| wide_mixed | batched | 2 dari 3 | Run 1 p95 jeda 153,2 ms (**gagal**); run 2 dan 3 p95 ±60 ms, tetapi maks jeda 410–469 ms |

Kriteria wajib "di semua fixture dan mode" **tidak terpenuhi**: mode `full` gagal di semua fixture (konsisten pada `code_heavy` dan `wide_mixed`, tidak konsisten pada `plain`), dan mode `batched` (N=10) gagal satu dari tiga run pada `wide_mixed`.

## 5. Rekomendasi (informasi, bukan syarat lulus)
- **Jangan pakai render ulang penuh per token.** Pada 40 token/detik anggaran per token 25 ms, sedangkan render ulang penuh pada dokumen panjang melebihi itu. Antrean sinyal menumpuk dan klik menunggu di belakangnya (hingga menit). Hasil `plain` + `full` run 3 yang lulus menunjukkan hasilnya bergantung beban sesaat PC, tidak bisa diandalkan.
- Pakai render bertahap. N=10 (±4 render/detik) lulus di 8 dari 9 run, tetapi `wide_mixed` masih menghasilkan lonjakan jeda 400–470 ms. Perlu diuji nilai N lebih besar atau interval berbasis waktu (misalnya tiap 250–500 ms) untuk fixture berat, dan sebaiknya render tabel/blok kode yang sudah lengkap saja. Ini **belum diuji** di sini.
- Syntax highlighting `code_heavy` dan tabel lebar `wide_mixed` jelas lebih mahal daripada teks biasa; render akhir dokumen penuh adalah titik lonjakan jeda.

## 6. Catatan khusus fixture
- `wide_mixed` (tabel 14 kolom, CJK, Arab): fixture terberat untuk `batched`; satu-satunya yang gagal kriteria. Tampilan visual teks Arab (arah RTL, ligatur) dan CJK tidak diperiksa oleh uji ini karena pengukuran otomatis tidak menilai kebenaran tampilan. Perlu dilihat manual.
- `code_heavy`: 3 blok >200 baris, bukan 4 seperti yang mungkin dibayangkan brief; total token 4.937 (lebih pendek dari 5.000).
- Ketiga fixture dihasilkan program, bukan teks LLM nyata, sehingga struktur lebih seragam dari respons sungguhan.
