# Brief Tugas — Fase 0, Uji #6: Kualitas Embedding Lokal untuk Memori Indonesia–Inggris

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding (dapat dijalankan sepenuhnya tanpa operator)
**Referensi desain:** `docs/decisions.md` (D-14, D-24, D-25, D-26, D-29)
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.

---

## 1. Tujuan

Membuktikan bahwa model embedding lokal `multilingual-e5-small` (ONNX int8, D-26) cukup akurat untuk mencari memori pribadi berbahasa Indonesia, Inggris, dan campuran keduanya, serta cukup cepat dijalankan di CPU.

Pertanyaan yang dijawab:
1. Apakah jawaban yang benar muncul di **top-5** untuk minimal **80%** query?
2. Seberapa besar penurunan kualitas akibat kuantisasi int8 dibanding fp32?
3. Apakah Hybrid Search (FTS5 + vektor + RRF, D-29) lebih baik daripada pencarian vektor saja?
4. Berapa lama waktu indexing 10.000 entri, waktu per query, waktu memuat model, dan pemakaian RAM?

## 2. Ruang Lingkup

**Termasuk:**
- Penyiapan model (`prepare_model.py`).
- Dataset uji sintetis (`dataset/`).
- Evaluasi kualitas (`evaluate.py`).
- Benchmark performa (`bench_index.py`).
- Panduan (`README.md`) dan laporan.

**Tidak termasuk:** integrasi ke aplikasi, UI, cloud embedding, dan penyimpanan vektor final.

## 3. Keputusan Desain yang WAJIB Diikuti

| Aturan | Nilai |
|---|---|
| Model | `intfloat/multilingual-e5-small` (dimensi 384) |
| Runtime inferensi | **ONNX Runtime CPU** (D-14) |
| Varian | **int8** (target D-26) dan **fp32** (pembanding) |
| Prefix e5 | **Wajib** `"query: "` untuk query dan `"passage: "` untuk entri memori |
| Pooling | Mean pooling dengan attention mask, lalu normalisasi L2 |
| Pencarian vektor | Brute-force cosine similarity dengan `numpy` (D-24) |
| Keyword search | SQLite FTS5 dengan `tokenize='unicode61 remove_diacritics 2'` dan ranking `bm25` |
| Hybrid | Reciprocal Rank Fusion dengan `k=60`, menggabungkan top-50 FTS5 dan top-50 vektor (D-29) |
| Python | 3.14 (sama dengan Uji #2), atau catat versi yang dipakai |

**Tentang tokenizer:** gunakan library `tokenizers` (Hugging Face, ringan) untuk memuat `tokenizer.json` milik model. Library ini **belum** ada di D-17. Catat ukuran dan versinya di laporan sebagai **kandidat dependency baru**.

## 4. Larangan (Jangan Dilakukan)

- ❌ Jangan memakai PyTorch, `sentence-transformers`, atau `transformers` saat **evaluasi dan benchmark**. Keduanya hanya boleh dipakai di `prepare_model.py`, dan hanya jika ekspor ke ONNX memang diperlukan.
- ❌ Jangan memakai API embedding cloud atau layanan online apa pun saat evaluasi.
- ❌ Jangan lupa prefix `"query: "` dan `"passage: "`. Tanpa prefix, kualitas e5 turun drastis dan uji menjadi tidak valid.
- ❌ **Jangan mengubah dataset setelah evaluasi pertama dijalankan.** Dataset harus di-commit **sebelum** hasil apa pun di-commit, sehingga riwayat Git membuktikan dataset tidak disesuaikan dengan hasil.
- ❌ Jangan commit file model (`.onnx`, `.bin`, `.safetensors`). Tambahkan polanya ke `.gitignore`.
- ❌ Jangan menebak atau membulatkan hasil secara menguntungkan. Semua angka harus berasal dari eksekusi nyata.

## 5. `prepare_model.py`

1. Ambil model dari Hugging Face. Gunakan file ONNX resmi dari repo model jika tersedia. Jika tidak, ekspor ke ONNX di mesin build.
2. Buat varian int8 dengan **dynamic quantization** dari `onnxruntime.quantization`, kecuali repo menyediakan varian int8 resmi.
3. Simpan model di luar repo, misalnya di `C:\nibras-staging\models\`.
4. Tulis `MODEL_INFO.json` berisi sumber (URL dan revision/commit), **lisensi** (verifikasi dari model card), ukuran file, SHA-256 setiap file, dan cara pembuatan varian int8.

## 6. Dataset (`dataset/`)

Dataset bersifat **sintetis** dan menggambarkan satu pengguna fiktif. **Jangan memakai data pribadi orang sungguhan.**

### `corpus.json`: 500 entri memori
- Setiap entri berupa satu pernyataan atomik (D-25), dengan field `id`, `text`, `lang` (`id`, `en`, atau `mix`), dan `category`.
- Kategori: User Preferences, Personal Context, Projects, Knowledge, Workflows, dan informasi PC.
- Proporsi bahasa kira-kira: 50% Indonesia, 30% Inggris, 20% campuran (code-switching, misalnya *"Deploy project Nibras pakai branch fase0 dulu"*).
- **Wajib ada hard negatives:** minimal 60 kelompok entri yang mirip tetapi berbeda detail. Contoh: *"suka kopi hitam tanpa gula"*, *"istri suka kopi susu"*, dan *"berhenti minum kopi setelah jam 3 sore"*.

### `queries.json`: 200 query
- Setiap query memiliki field `id`, `query`, `type`, dan `relevant_ids` (satu atau lebih id entri yang benar).
- Distribusi tipe:

| Tipe | Jumlah | Keterangan |
|---|---|---|
| `id-id` | 40 | Query Indonesia, entri Indonesia |
| `en-en` | 30 | Query Inggris, entri Inggris |
| `id-en` | 30 | Query Indonesia, entri Inggris (lintas bahasa) |
| `en-id` | 30 | Query Inggris, entri Indonesia (lintas bahasa) |
| `informal` | 40 | Bahasa gaul atau singkatan (*"gw"*, *"kalo"*, *"yg"*, *"gmn"*) |
| `typo` | 30 | Salah ketik yang wajar |

- **Aturan anti-bocor:** minimal **60%** query tidak boleh memakai kata isi (content word) yang sama dengan entri jawabannya. Query semacam ini menguji pemahaman makna, bukan kecocokan kata. Hitung persentasenya secara otomatis dan cantumkan di laporan.

### Data skala untuk benchmark
Untuk benchmark 10.000 entri, buat data tambahan dengan variasi kalimat sintetis. Data ini **hanya** dipakai untuk mengukur kecepatan, bukan kualitas.

## 7. `evaluate.py`

Konfigurasi yang dievaluasi:
- **A.** Vektor int8.
- **B.** Vektor fp32.
- **C.** FTS5 (BM25) saja.
- **D.** Hybrid RRF (FTS5 + vektor int8).

Metrik untuk setiap konfigurasi, baik secara total maupun **per tipe query**:
- **Recall@1** dan **Recall@5** (query dianggap benar jika minimal satu `relevant_ids` muncul).
- **MRR@10**.

Simpan juga daftar query yang gagal di top-5 untuk konfigurasi A, beserta 5 hasil teratasnya, untuk analisis kegagalan.

**Catatan FTS5:** query bahasa alami bisa mengandung karakter yang merupakan sintaks khusus FTS5. Escape query dengan aman (misalnya bungkus setiap token dengan tanda kutip ganda, lalu gabungkan dengan `OR`).

## 8. `bench_index.py`

Catat:
- Waktu memuat model dan tokenizer (int8 dan fp32).
- Waktu indexing **10.000 entri** (total dan rata-rata per entri), dengan batch size 32.
- Waktu satu query end-to-end: embedding query, similarity, dan top-k (median dan p95 dari 200 query).
- Puncak pemakaian RAM proses (`psutil`).
- Ukuran file model int8 dan fp32.
- Spesifikasi CPU, jumlah core, dan RAM PC.

## 9. Kriteria Lulus

| Kriteria | Target | Sifat |
|---|---|---|
| Recall@5 konfigurasi A (int8), total | Minimal 80% | **Wajib** |
| Lisensi model mengizinkan pemakaian dan distribusi | Terverifikasi | **Wajib** |
| Recall@5 lintas bahasa (`id-en` dan `en-id`) konfigurasi A | Minimal 70% | Target lunak |
| Selisih Recall@5 antara int8 dan fp32 | Maksimal 3 poin persen | Target lunak |
| Hybrid (D) dibanding vektor (A) | D ≥ A | Target lunak |
| Indexing 10.000 entri dengan int8 | Kurang dari 15 menit | Target lunak |
| Median waktu query | Kurang dari 200 ms | Target lunak |

Jika kriteria wajib gagal, **jangan** mengganti model atau mengubah dataset. Laporkan apa adanya beserta analisis kegagalan. Pergantian model diputuskan melalui proses review.

## 10. Deliverable

```
spikes/uji06-embedding/
├── prepare_model.py
├── evaluate.py
├── bench_index.py
├── dataset/
│   ├── corpus.json
│   └── queries.json
└── README.md
results/
├── uji06-embedding.md
└── uji06-raw/          JSON metrik mentah dan daftar kegagalan (boleh di-commit)
```

Tambahkan ke `.gitignore`: `*.onnx`, `*.safetensors`, `*.bin`, serta pengecualian agar `results/uji06-raw/*.json` tetap ter-commit.

Isi `results/uji06-embedding.md`:
1. **Lingkungan:** OS, CPU, RAM, versi Python, `onnxruntime`, `numpy`, `tokenizers`, dan SQLite.
2. **Model:** sumber, revision, lisensi, ukuran, dan SHA-256 (dari `MODEL_INFO.json`).
3. **Statistik dataset:** jumlah entri per bahasa dan kategori, jumlah kelompok hard negative, dan persentase query anti-bocor.
4. **Tabel kualitas:** konfigurasi A–D × (total + 6 tipe query) untuk Recall@1, Recall@5, dan MRR@10.
5. **Tabel performa** dari bagian 8.
6. **Analisis kegagalan:** pola umum dari query yang gagal di konfigurasi A.
7. **Evaluasi** terhadap kriteria di bagian 9.
8. **Catatan dependency** `tokenizers`: versi dan ukuran.

## 11. Urutan Commit (wajib)

1. Commit `dataset/` dan script **sebelum** evaluasi pertama dijalankan.
2. Jalankan evaluasi dan benchmark.
3. Commit hasil (`results/`) di commit terpisah.

Kerjakan di branch `fase0/uji06`, lalu buka pull request ke `main`.
