# Laporan Uji #6b Fase 0: Evaluasi Lanjutan Embedding dan Mitigasi (Tahap 2)

Brief: `docs/briefs/fase0-uji06b-embedding-lanjutan.md`. Melanjutkan Uji #6 (`results/uji06-embedding.md`, PR #4). Tahap 1 (dataset `queries_v2.json`, `corpus_alt.json`) disetujui review manusia pada PR #5 sebelum Tahap 2 ini dijalankan.

**Hasil ringkas:** memisahkan kelemahan model dari dataset adversarial berhasil. Pada query natural (v2), entri dwibahasa (`bi`) menaikkan Recall@5 jauh di atas `mono` untuk kedua model, dan **tiga konfigurasi `multilingual-e5-small` (`S_bi_vec`, `S_bi_hyb1`, `S_bi_hyb05`) memenuhi kriteria Prioritas 1** (Recall@5 v2 ≥ 80% dan Recall@5 `id-en` v2 ≥ 70%). Jadi tidak perlu beralih ke `e5-base`, sesuai arah keputusan Prioritas 1 di bagian 5 — tetapi keputusan akhir tetap menunggu review.

## 1. Lingkungan

| Item | Nilai |
|---|---|
| OS | Linux (container, kernel 6.18.44, glibc 2.39) |
| CPU | Intel(R) Xeon(R) @ 2.10GHz, 4 core fisik / 4 logis (cloud container, bukan PC AAN-PC yang dipakai Uji #6) |
| RAM | 15,7 GB |
| Python | 3.13.18 |
| onnxruntime | 1.29.0 (CPUExecutionProvider) |
| numpy | 2.5.3 |
| tokenizers | 0.23.3 |
| SQLite | 3.53.1 (FTS5 aktif) |

**Catatan penting:** Tahap 2 ini dijalankan di lingkungan agen coding (container Linux cloud), berbeda dari PC AAN-PC (Windows 11, Intel i5-4460) yang dipakai Uji #6. Angka performa (bagian 5) karena itu **tidak boleh dibandingkan langsung** dengan `results/uji06-raw/bench_performance.json` Uji #6 — bandingkan hanya S vs B *di dalam* Tahap 2 ini, pada mesin yang sama. Angka kualitas (Recall@5/@1, MRR@10) tidak bergantung CPU dan dapat dibandingkan dengan Uji #6 untuk v1.

## 2. Model

Kedua model diambil dengan cara yang sama seperti `prepare_model.py` Uji #6 (sekarang diparametrikan lewat `--model small|base`): file ONNX int8 **resmi** dari repo model, tanpa ekspor atau kuantisasi sendiri (karena file resminya ada untuk keduanya), tanpa PyTorch/transformers.

| | `S` = multilingual-e5-small | `B` = multilingual-e5-base |
|---|---|---|
| Repo | `intfloat/multilingual-e5-small` | `intfloat/multilingual-e5-base` |
| Revision (pinned) | `614241f622f53c4eeff9890bdc4f31cfecc418b3` | `d128750597153bb5987e10b1c3493a34e5a4502a` |
| Lisensi (dari front matter model card) | **MIT** | **MIT** |
| int8 | file resmi `onnx/model_qint8_avx512_vnni.onnx`, 118.346.824 byte | file resmi `onnx/model_qint8_avx512_vnni.onnx`, 278.686.411 byte |
| SHA-256 int8 | `dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88` | `2523551878658b305550d8759443822dbfda9ed9c8012ef2c354ba2c5b9de503` |
| SHA-256 fp32 | `ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665` | `84a4d426f7e87a6bf5bf195f0bae2c4a7d15f675b23ca96f42fab8326d7a77aa` |
| Dimensi vektor | 384 | 768 |

Hash lengkap semua file (tokenizer, config, dst.): `results/uji06b-raw/MODEL_INFO_S.json` dan `MODEL_INFO_B.json`. File model sendiri **tidak di-commit** ke repo (larangan mutlak bagian 7).

## 3. Statistik dataset v2

(Disetujui pada Tahap 1 / PR #5, disalin dari `results/uji06b-raw/dataset_stats_v2.json`, dihasilkan oleh `dataset/dataset_stats_v2.py`.)

- 200 query: id-id 40, en-en 30, id-en 30, en-id 30, informal 40, typo 30 — sama seperti v1.
- Sebaran kemiripan kata (query vs kata isi entri jawaban, definisi sama dengan `dataset_stats.py` v1):
  - 0% / semantik: **64 query (32,0%)** — memenuhi syarat minimal 30% di brief bagian 3.
  - 1–25% overlap: 74 query.
  - 26–50% overlap: 62 query.
  - >50% overlap: **0 query** — tidak ada yang melanggar batas "menyalin lebih dari 50% kata isi jawaban".
- Multi-label (`relevant_ids` > 1): **9 query (4,5%)**, tersebar di en-en (1), id-en (1), informal (3), typo (4).
- Korpus v1 tidak diubah: 500 entri (Indonesia 250, Inggris 149, campuran 101). `corpus_alt.json` menambah 500 `text_alt` (satu per entri, arah terjemahan sesuai `lang`), juga tidak diubah di Tahap 2.

## 4. Tabel Recall@5 — 12 konfigurasi × v1/v2

Semua angka dari eksekusi nyata `evaluate_v2.py` (lihat `results/uji06b-raw/quality_metrics_v2.json` untuk Recall@1 dan MRR@10 lengkap per konfigurasi, per qset, total dan 6 tipe).

### v2 — query natural (200 query, n=200 per baris)

| Konfigurasi | Total | id-id | en-en | id-en | en-id | informal | typo |
|---|---|---|---|---|---|---|---|
| S_mono_vec | 77,0 | 75,0 | 100,0 | 50,0 | 83,3 | 70,0 | 86,7 |
| S_mono_hyb1 | 74,0 | 90,0 | 100,0 | 36,7 | 63,3 | 70,0 | 80,0 |
| S_mono_hyb05 | 74,0 | 87,5 | 100,0 | 43,3 | 60,0 | 70,0 | 80,0 |
| **S_bi_vec** | **89,5** | 72,5 | 100,0 | 93,3 | 93,3 | 92,5 | 90,0 |
| **S_bi_hyb1** | **93,5** | 87,5 | 100,0 | 93,3 | 96,7 | 95,0 | 90,0 |
| **S_bi_hyb05** | **94,0** | 85,0 | 100,0 | 96,7 | 96,7 | 95,0 | 93,3 |
| B_mono_vec | 83,5 | 82,5 | 100,0 | 66,7 | 90,0 | 80,0 | 83,3 |
| B_mono_hyb1 | 76,5 | 90,0 | 96,7 | 43,3 | 70,0 | 75,0 | 80,0 |
| B_mono_hyb05 | 79,5 | 90,0 | 100,0 | 53,3 | 70,0 | 77,5 | 83,3 |
| **B_bi_vec** | **92,0** | 80,0 | 100,0 | 100,0 | 93,3 | 95,0 | 86,7 |
| **B_bi_hyb1** | **95,0** | 90,0 | 96,7 | 100,0 | 96,7 | 95,0 | 93,3 |
| **B_bi_hyb05** | **95,5** | 87,5 | 100,0 | 100,0 | 96,7 | 95,0 | 96,7 |

### v1 — query adversarial lama (200 query, dilaporkan sebagai indikator ketahanan, bukan syarat lulus)

| Konfigurasi | Total | id-id | en-en | id-en | en-id | informal | typo |
|---|---|---|---|---|---|---|---|
| S_mono_vec | 60,0 | 52,5 | 86,7 | 30,0 | 76,7 | 60,0 | 56,7 |
| S_mono_hyb1 | 50,0 | 25,0 | 80,0 | 20,0 | 60,0 | 57,5 | 63,3 |
| S_mono_hyb05 | 51,5 | 30,0 | 80,0 | 23,3 | 56,7 | 60,0 | 63,3 |
| S_bi_vec | 75,5 | 50,0 | 83,3 | 80,0 | 100,0 | 80,0 | 66,7 |
| S_bi_hyb1 | 68,5 | 20,0 | 63,3 | 90,0 | 96,7 | 80,0 | 73,3 |
| S_bi_hyb05 | 70,0 | 27,5 | 66,7 | 83,3 | 96,7 | 82,5 | 73,3 |
| B_mono_vec | 71,0 | 70,0 | 90,0 | 50,0 | 96,7 | 67,5 | 53,3 |
| B_mono_hyb1 | 55,5 | 40,0 | 73,3 | 30,0 | 60,0 | 65,0 | 66,7 |
| B_mono_hyb05 | 57,5 | 47,5 | 76,7 | 36,7 | 60,0 | 62,5 | 63,3 |
| B_bi_vec | 83,5 | 70,0 | 86,7 | 93,3 | 100,0 | 87,5 | 66,7 |
| B_bi_hyb1 | 73,5 | 32,5 | 76,7 | 90,0 | 96,7 | 82,5 | 73,3 |
| B_bi_hyb05 | 76,0 | 32,5 | 80,0 | 93,3 | 96,7 | 87,5 | 76,7 |

**Pengamatan utama:**
- `bi` (entri dwibahasa, skor = maksimum kedua vektor) menaikkan Recall@5 total v2 sekitar **12–19 poin** dibanding `mono` yang sepadan, untuk `S` maupun `B`. Kenaikan terbesar pada `id-en`: dari 36,7–66,7% (`mono`) menjadi 93,3–100% (`bi`). Ini sesuai hipotesis bahwa bias bahasa Uji #6 bisa dimitigasi dengan menyimpan terjemahan.
- Hybrid RRF (`hyb1`/`hyb05`) membantu di atas `bi_vec` (naik ~2–4 poin pada v2), tapi **menurunkan** Recall@5 dibanding `mono_vec` ketika entri masih `mono` (karena query-side stopword removal tidak menghapus kata isi seperti "sekolah"/"mobil" yang justru jadi distraktor leksikal BM25 pada korpus tanpa terjemahan — lihat bagian 7).
- Pada v1 (adversarial), Recall@5 semua konfigurasi lebih rendah daripada v2 (seperti diharapkan: query v1 memang didesain sulit), tapi `bi` tetap jauh lebih tinggi dari `mono`, mengonfirmasi mitigasi dwibahasa bekerja juga di set yang sulit.

## 5. Tabel performa — `S` dan `B` (`mono` dan `bi`)

Diukur di **proses terpisah per model** (`bench_index_v2.py --model S` lalu `--model B`, dua invokasi `python3` berbeda) agar RAM tidak tercampur. Lihat `results/uji06b-raw/bench_performance_S.json` dan `_B.json`.

| Metrik | S (e5-small int8) | B (e5-base int8) |
|---|---|---|
| Ukuran file model int8 | 112,9 MB | 265,8 MB |
| Waktu load tokenizer | 0,653 s | 0,642 s |
| Waktu load model (ONNX session) | 0,799 s | 2,010 s |
| Indexing 10.000 entri `mono` (10.000 vektor) | 29,37 s total (2,94 ms/entri) | 56,77 s total (5,68 ms/entri) |
| Indexing 10.000 entri `bi` (20.000 vektor) | 58,41 s total (5,84 ms/entri) | 110,28 s total (11,03 ms/entri) |
| Query — median | 8,01 ms | 19,99 ms |
| Query — p95 | 16,01 ms | 33,53 ms |
| Ukuran matriks vektor (`mono`, 10k entri) | 14,6 MB | 29,3 MB |
| Ukuran matriks vektor (`bi`, 10k entri + terjemahan) | 29,3 MB | 58,6 MB |
| Puncak RAM proses | 581,8 MB | 875,6 MB |

**Ringkasan S vs B:** `B` sekitar **2,4× lebih besar** di disk, **~1,9–1,95× lebih lambat** untuk indexing dan query (median query 20,0 ms vs 8,0 ms — keduanya tetap jauh di bawah skala yang mengganggu pengalaman pengguna untuk ukuran memori yang realistis di Nibras), dan memakai **~1,5× RAM puncak** lebih banyak. Biayanya nyata tapi tidak ekstrem.

## 6. Konfigurasi yang memenuhi kriteria keputusan (brief bagian 5)

| Prioritas | Kondisi | Konfigurasi yang memenuhi (v2) |
|---|---|---|
| **1** | Model `S`, Recall@5 v2 ≥ 80% **dan** Recall@5 `id-en` v2 ≥ 70% | **S_bi_vec** (89,5% / 93,3%), **S_bi_hyb1** (93,5% / 93,3%), **S_bi_hyb05** (94,0% / 96,7%) — **TERPENUHI** |
| 2 | Hanya `B` yang memenuhi kondisi Prioritas 1 | Tidak relevan — Prioritas 1 sudah terpenuhi oleh `S` |
| 3 | Tidak ada yang memenuhi | Tidak relevan |

Karena Prioritas 1 terpenuhi, arah keputusan brief bagian 5 adalah: **pertahankan `multilingual-e5-small`, tambahkan aturan entri dwibahasa (menyimpan `text_alt` dan mengambil skor maksimum) dan/atau Hybrid RRF** sesuai konfigurasi yang lulus di atas. Catatan: `B` juga lulus kondisi yang sama (B_bi_vec/hyb1/hyb05 semuanya ≥80%/≥70%, lihat bagian 4), tetapi kriteria Prioritas 2 secara eksplisit hanya berlaku ketika *hanya* `B` yang lulus — di sini `S` sudah lulus duluan, sehingga Prioritas 1 menang sesuai urutan di brief. Ini **laporan**, bukan keputusan; keputusan revisi D-26/D-29 tetap melalui review manusia.

## 7. Analisis kegagalan konfigurasi terbaik pada v2

Konfigurasi dengan Recall@5 v2 tertinggi secara keseluruhan adalah **B_bi_hyb05 (95,5%, 9 query gagal dari 200)**. Konfigurasi terbaik yang memenuhi Prioritas 1 dengan model `S` adalah **S_bi_hyb05 (94,0%, 12 query gagal)**. Daftar lengkap kegagalan tiap konfigurasi (semua 12 × v1/v2): `results/uji06b-raw/failures_v2_by_config.json`.

**9 kegagalan B_bi_hyb05 pada v2** (5 id-id, 2 informal, 1 en-id, 1 typo):

| Query | Tipe | Jawaban benar | Kenapa gagal |
|---|---|---|---|
| "Aira sekolah di mana?" | id-id | g03a (sekolah Aira) | Top-5 semua berisi kata "sekolah"/"school" dari entri lain tentang Aira (biaya sekolah, bahasa Sunda, laptop sekolah) — BM25 dan vektor sama-sama tertarik ke kata "sekolah" sebagai distraktor leksikal, bukan ke makna "di mana sekolahnya". |
| "Siapa yang nganterin Aira ke sekolah?" | id-id | g03b | Distraktor leksikal "sekolah" yang sama seperti di atas. |
| "Dimas mancing di mana?" / "Dimas mancingnya dimna?" (typo) | id-id, typo | g16b | Tidak ada distraktor leksikal "mancing", tapi juga tidak ada entri lain yang berbagi kata — ini murni kegagalan semantik: top-5 berisi entri "Dimas" acak (sepatu, ulang tahun, golongan darah) yang tak berhubungan sama sekali dengan memancing. |
| "Rumah Dimas ada di mana?" | id-id | g28a (alamat rumah) | Mirip: top-5 berisi entri lain yang menyebut "rumah" (ruang kerja di rumah, kerja dari rumah, rumah kedua) — kata "rumah" sebagai distraktor, bukan alamat spesifiknya. |
| "Dimas mau belajar apa tahun ini?" | id-id | g51a (target belajar Rust/Kubernetes) | Entri jawaban tidak memakai kata "belajar"; top-5 berisi entri lain yang menyebut "tahun ini" (resolusi, ulang tahun pernikahan ortu) — distraktor pada kata "tahun ini", bukan "belajar". |
| "What school does Aira attend?" | en-id | g03a | Sama seperti kegagalan "sekolah" di atas, versi Inggris. |
| "mobil gw merek apa" | informal | g04a (mobil Honda Brio) | Top-5 berisi entri lain bertema "mobil" (rute Garut, servis Brio, family trip naik mobil) — kata "mobil" sebagai distraktor; model/FTS mengambil entri yang membahas pemakaian mobil, bukan merek/mobil mana yang dimiliki. |
| "gw ga boleh makan apa" | informal | g09a (alergi udang) | Tidak ada kata bersama ("ga boleh makan" vs "alergi udang, jangan sarankan seafood") — top-5 berisi entri "makan"/"dilarang" lain (warung langganan, ruang kerja tidak boleh dimasuki, Aira lactose intolerant) yang topiknya dekat tapi bukan jawabannya. |

**Pola kegagalan:** semua 9 kegagalan termasuk kategori yang sudah diidentifikasi review Uji #6 sebagai **kelemahan model yang nyata** (bukan artefak dataset adversarial): query semantik murni yang tak berbagi kata isi dengan jawaban (butuh pemahaman makna, bukan leksikal), dan query dengan satu kata isi umum ("sekolah", "mobil", "rumah", "tahun ini") yang juga muncul di banyak entri lain tentang entitas/topik yang sama (Aira, Dimas, mobil, rumah) — di sini FTS5 BM25 dan kemiripan vektor keduanya condong ke frekuensi kata itu, bukan ke makna spesifik pertanyaannya. Dataset v2 yang natural (bukan adversarial) berhasil **mengisolasi** jenis kegagalan ini dari masalah dataset yang mencampuri Uji #6 — tidak ada kegagalan di sini yang disebabkan oleh parafrase tak natural atau ambiguitas persona, karena dataset v2 sudah dirancang menghindari itu.

## 8. Daftar stopword (Hybrid FTS5, brief bagian 4)

Konstanta `STOPWORDS_ID_EN` di `spikes/uji06-embedding/common.py` (198 kata, Indonesia + Inggris), dihapus **hanya dari sisi query FTS5** sebelum membangun ekspresi MATCH — teks yang diindeks tidak pernah difilter. Daftar ini ditetapkan di kode sebelum evaluasi dijalankan dan **tidak diubah berdasarkan hasil**:

```
a, about, above, ada, adalah, agar, akan, aku, all, am, an, and, antara, any,
apa, are, at, atas, atau, bagaimana, bagi, banget, bawah, be, been, begini,
begitu, being, below, belum, berapa, berikut, both, brp, bukan, but, by, can,
cannot, could, dalam, dan, dari, demikian, dengan, dgn, di, dia, did, dmn, do,
does, each, enggak, few, for, from, ga, gak, gini, gitu, gmn, gue, gw, had,
has, have, he, her, here, him, hingga, his, how, i, in, ini, into, is, it,
its, itu, jika, juga, just, kah, kalau, kami, kapan, karena, ke, kenapa,
ketika, kita, knp, kpn, kurang, lah, lebih, lo, lu, luar, mana, may, me,
mengapa, mereka, might, more, most, must, my, namun, napa, ngga, no, nor, not,
nya, of, oleh, on, only, onto, or, other, our, over, own, pada, paling, pun,
saat, same, sampai, sangat, saya, sebab, sebagai, sebelum, serta, sesudah,
setelah, shall, she, should, siapa, sih, so, some, such, sudah, supaya, tdk,
tentang, tersebut, tetapi, than, that, the, their, them, then, there, these,
they, this, those, tidak, to, too, under, untuk, us, utk, very, was, we,
were, what, when, where, which, who, whom, whose, why, will, with, would,
ya, yaitu, yakni, yang, yet, yg, you, your
```

Aturan Hybrid lain yang ditetapkan sebelum evaluasi (tidak dicari berdasarkan hasil, sesuai larangan bagian 7):
- RRF: `k=60`, top-50 dari masing-masing sumber (FTS5 dan vektor), hasil akhir diambil top-10 untuk metrik.
- Bobot FTS5 hanya diuji pada **1,0** (`hyb1`) dan **0,5** (`hyb05`); bobot vektor selalu 1,0.
- Pada `bi`, indeks FTS5 memakai gabungan `text` + `text_alt` per entri (satu dokumen FTS per entri, bukan dua dokumen terpisah).
