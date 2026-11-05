# Brief Tugas — Fase 0, Uji #4b: Mitigasi Render Streaming di UI

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md` (D-11, D-16, D-50, dan bagian 12 "Uji #4"), `results/uji04-streaming-ui.md`
**Melanjutkan:** Uji #4 (PR #7). Kode di `spikes/uji04-streaming-ui/` boleh dipakai ulang dan diperluas.
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.
**Dijalankan di:** PC Windows fisik yang **sama** dengan Uji #4 (sesi Claude Code lokal operator), dengan event loop Qt dan jendela sungguhan.

---

## 1. Latar Belakang

Uji #4 gagal karena **strategi render**, bukan karena `QTextBrowser`. Setiap update mengonversi seluruh Markdown dan melakukan highlighting ulang di main thread, sehingga biaya render naik seiring panjang pesan. Mode bertahap N=10 lulus 8 dari 9 run, tetapi satu render dokumen `wide_mixed` makan waktu p50 87–138 ms dan maksimum 480 ms.

Uji #4 juga menunjukkan bahwa metrik "p95 jeda timer" tidak peka terhadap freeze panjang. Tick `QTimer` yang terlewat digabung menjadi satu sampel, sehingga UI yang tertahan 200 detik tetap menghasilkan p95 sekitar 10 ms. Uji #4b memakai metrik berbasis waktu (bagian 5).

## 2. Pertanyaan yang Dijawab

1. Mitigasi mana yang membuat UI tidak macet di **ketiga** fixture, termasuk `wide_mixed`?
2. Berapa biaya tiap mitigasi: keterlambatan tampilan, kompleksitas, dan kebenaran hasil akhir?
3. Seberapa besar porsi biaya render di main thread (`setHtml` dan layout) dibanding konversi Markdown dan highlighting?

## 3. Varian yang Diuji

Semua varian memakai fixture, laju stream, dan PC yang sama dengan Uji #4.

| Varian | Deskripsi |
|---|---|
| `batched10` | **Kontrol.** Persis mode `batched` Uji #4 (render penuh tiap 10 token, di main thread). Dipakai untuk memastikan kondisi PC sebanding dengan Uji #4 |
| `time250` | Render penuh **tiap 250 ms** (hanya jika ada token baru sejak render terakhir), ditambah render akhir. Konversi tetap di main thread |
| `offthread` | Seperti `time250`, tetapi konversi Markdown ke HTML dan highlighting `Pygments` dijalankan di **thread pekerja** (`QThread`). Main thread hanya menerima string HTML lewat signal, lalu memanggil `setHtml`. Jika konversi sebelumnya belum selesai saat jadwal 250 ms tiba, jangan antrekan pekerjaan baru. Konversi berikutnya memakai isi buffer terbaru setelah yang berjalan selesai |
| `incremental` | Seperti `offthread`, ditambah render inkremental. Dokumen dibagi menjadi **blok final** dan **ekor**. Blok final dikonversi **sekali**, lalu ditambahkan ke akhir dokumen `QTextBrowser` lewat `QTextCursor`. Hanya ekor yang dibuang dan dikonversi ulang setiap update. **Dilarang** memanggil `setHtml` untuk seluruh dokumen pada setiap update |

**Aturan blok final** untuk `incremental` (wajib persis seperti ini):
- Sebuah blok dianggap final jika sudah diikuti baris kosong **dan** tidak berada di dalam code fence (```` ``` ````) yang masih terbuka.
- Tabel Markdown adalah satu blok. Tabel menjadi final setelah diikuti baris kosong.
- Semua teks setelah batas blok final terakhir adalah ekor.

**Parameter tetap** (ditetapkan di sini, dilarang diubah berdasarkan hasil):

| Parameter | Nilai |
|---|---|
| Interval render varian `time250`, `offthread`, `incremental` | 250 ms |
| N varian `batched10` | 10 token |
| Laju stream | 40 token/detik |
| Fixture | `plain.md`, `code_heavy.md`, `wide_mixed.md` dari Uji #4, **tidak diubah** |

SHA-256 fixture yang wajib cocok (verifikasi di awal setiap run dan catat di JSON):

| Fixture | SHA-256 |
|---|---|
| `plain.md` | `30d17a569d6a016514675e9fd5134beb4cd552aaa4dcd76eb83c6d5cbec147d6` |
| `code_heavy.md` | `d8e0b7a435f491e1c0aaebe284666afd2ebe42620a665de5e2b3024526b12abe` |
| `wide_mixed.md` | `89372e77548b418a9effc4a7988238e6dc9f820244d29367c5a9ac18b8d31b6b` |

## 4. Keputusan Desain yang WAJIB Diikuti

| Aturan | Nilai |
|---|---|
| Rendering | `QTextBrowser`, Markdown dengan `markdown-it-py`, highlighting dengan `Pygments` (D-16) |
| Struktur | Satu `QTextBrowser` per kartu pesan (D-50) |
| Threading | Sumber stream dan pekerja konversi berkomunikasi dengan UI **hanya lewat Qt signal** (D-11). Tidak ada pemanggilan method widget dari thread non-UI. Data yang dikirim antar-thread berupa salinan string, bukan objek bersama yang bisa berubah |

## 5. Pengukuran

Untuk setiap run, catat di JSON:

1. **Interval tick timer 16 ms**, disimpan lengkap per sampel (daftar angka, bukan hanya persentil), supaya metrik bisa dihitung ulang oleh reviewer.
2. **Waktu tertahan:** jumlah semua interval tick yang lebih dari 100 ms, dibagi durasi stream, dalam persen.
3. **Freeze terpanjang:** interval tick terbesar (ms).
4. **Delta klik-respons:** p95 dan maksimum (ms), dengan klik otomatis yang sama seperti Uji #4.
5. **Biaya render, dipisah:** `convert_ms` (Markdown + highlighting, di thread mana pun ia berjalan) dan `apply_ms` (pekerjaan di main thread: `setHtml` atau sisip/hapus lewat `QTextCursor`). Catat thread tempat `convert_ms` berjalan.
6. **Keterlambatan tampil akhir:** waktu dari token terakhir dikirim simulator sampai render akhir selesai di main thread (ms).
7. **Durasi stream** dibanding durasi ideal.
8. **Kebenaran hasil akhir:** bandingkan `toPlainText()` kartu setelah render akhir dengan `toPlainText()` dari `QTextBrowser` terpisah yang me-render seluruh fixture sekali jadi. Catat `match: true/false`. Jika tidak cocok, simpan diff ringkasnya.
9. Metrik lama dari Uji #4 (p95/p99 jeda timer) tetap dicatat sebagai pembanding, tetapi **bukan** kriteria.

## 6. Prosedur Uji (oleh operator, boleh berjalan otomatis)

1. Gunakan PC yang sama dengan Uji #4. Laptop dicolok ke charger, power plan sama seperti Uji #4, aplikasi lain ditutup, dan PC **tidak dipakai** selama uji berjalan. Catat semua kondisi ini di laporan.
2. Jalankan baseline idle 10 detik.
3. Jalankan 4 varian × 3 fixture × **5 run** = 60 run, masing-masing di proses terpisah. Urutan berselang-seling per nomor run (run 1 semua kombinasi, lalu run 2, dan seterusnya), seperti `run_all.py` di Uji #4. Batas waktu per run: 420 detik. Run yang melewati batas dicatat `TIMEOUT`.
4. Klik dan scroll otomatis sama seperti Uji #4. Laporan wajib menyebutkan bahwa interaksi diotomatisasi.

## 7. Kriteria Lulus (ditetapkan sebelum uji)

Sebuah **run** dinyatakan lulus jika memenuhi **semua** syarat berikut:

| Syarat | Batas |
|---|---|
| Waktu tertahan (interval tick > 100 ms) | ≤ 1% durasi stream |
| Freeze terpanjang | < 300 ms |
| Delta klik p95 | < 150 ms |
| Delta klik maksimum | < 300 ms |
| Durasi stream | ≤ 105% durasi ideal |
| Kebenaran hasil akhir | `match: true` |

Sebuah **varian** dinyatakan lulus jika **15 dari 15** run-nya (3 fixture × 5 run) lulus.

**Arah keputusan** (agen hanya melaporkan, keputusan diambil lewat review):

| Prioritas | Kondisi | Arah |
|---|---|---|
| 1 | Ada varian yang lulus | Rekomendasikan varian lulus yang **paling sederhana**, dengan urutan kesederhanaan `time250` < `offthread` < `incremental` |
| 2 | Tidak ada varian yang lulus | Laporkan varian terbaik dan penyebab kegagalannya. Strategi rendering dirancang ulang melalui review |

Kontrol `batched10` tidak bisa menjadi varian rekomendasi. Fungsinya hanya memastikan PC dalam kondisi sebanding. Jika hasil `batched10` jauh berbeda dari mode `batched` Uji #4, catat hal ini sebagai anomali di laporan.

## 8. Larangan (Jangan Dilakukan)

- ❌ Jangan mengubah fixture. Verifikasi SHA-256 di bagian 3.
- ❌ Jangan mengubah interval 250 ms, N=10, laju 40 token/detik, atau batas di bagian 7 berdasarkan hasil.
- ❌ Jangan memanggil method widget Qt dari thread non-UI.
- ❌ Jangan membuang token atau melewatkan render akhir demi angka yang lebih baik.
- ❌ Jangan memakai LLM sungguhan.
- ❌ Jangan mengganti `QTextBrowser` dengan widget lain (misalnya `QWebEngineView`) di uji ini. Kalau semua varian gagal, usulan widget lain ditulis di laporan, tidak diimplementasikan.
- ❌ Jangan mengarang atau membulatkan angka secara menguntungkan.
- ❌ Jangan mengubah `docs/decisions.md` dan `docs/briefs/`.

## 9. Urutan Commit (wajib)

1. Commit **kode** (varian, pengukuran, `run_all`, `aggregate`) **sebelum** uji dijalankan.
2. Commit **hasil** (JSON mentah dan laporan) di commit terpisah. Kode **tidak boleh diubah** di antara kedua commit tersebut. Jika ditemukan bug setelah uji berjalan, perbaiki kodenya di commit baru, lalu jalankan ulang **seluruh** run. Jangan hanya menjalankan ulang run yang gagal.

## 10. Deliverable

```
spikes/uji04-streaming-ui/
├── (ui_probe.py dan modul pendukung yang diperluas dengan 4 varian)
├── run_all_4b.py
└── aggregate_4b.py      membuat tabel laporan dari results/uji04b-raw/
results/
├── uji04b-streaming-ui.md
└── uji04b-raw/          JSON per run, termasuk daftar interval tick lengkap
```

Tambahkan pengecualian `.gitignore` untuk `results/uji04b-raw/*.json`, mengikuti pola Uji #4. Sebelum commit, pindai data mentah dan pastikan tidak ada username, hostname, atau path profil.

Isi `results/uji04b-streaming-ui.md`:
1. **Lingkungan dan kondisi PC** (charger, power plan, aplikasi lain ditutup).
2. **Verifikasi fixture** (SHA-256 cocok).
3. **Tabel per run:** varian × fixture × run dengan semua metrik di bagian 5.
4. **Ringkasan per varian:** jumlah run lulus dari 15.
5. **Pemisahan biaya render:** `convert_ms` dibanding `apply_ms` per varian dan fixture.
6. **Varian yang memenuhi bagian 7**, beserta prioritasnya.
7. **Perbandingan kontrol `batched10` dengan mode `batched` Uji #4.**
8. **Analisis kegagalan** untuk run yang tidak lulus.

## 11. Definisi Selesai

- Ke-60 run dan baseline benar-benar dijalankan dengan event loop Qt dan jendela sungguhan.
- Urutan commit di bagian 9 dipatuhi.
- Tabel laporan bisa dibuat ulang oleh `aggregate_4b.py` dari JSON mentah, dan hasilnya sama persis.
- Kode dikerjakan di branch `fase0/uji04b`, lalu dibuka pull request ke `main`.
