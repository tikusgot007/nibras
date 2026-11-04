# Brief Tugas — Fase 0, Uji #6b: Evaluasi Lanjutan Embedding dan Mitigasi

**Proyek:** Nibras
**Untuk:** agen coding
**Referensi:** `docs/decisions.md` (D-24, D-25, D-26, D-27, D-29, dan bagian 12), `results/uji06-embedding.md`
**Melanjutkan:** Uji #6 (PR #4). Kode di `spikes/uji06-embedding/` boleh dipakai ulang.

---

## 1. Latar Belakang

Uji #6 menghasilkan Recall@5 sebesar 60,5% untuk `multilingual-e5-small` int8. Review menemukan dua penyebab yang tercampur:

1. **Kelemahan model yang nyata:** bias bahasa ketika query Indonesia mencari entri berbahasa Inggris.
2. **Dataset terlalu adversarial:**
   - Parafrase query tidak natural.
   - Persona ambigu: "Dimas" dan "the user" sebenarnya orang yang sama, tetapi tidak diperlakukan demikian.
   - FTS5 berjalan tanpa penghapusan stopword.

Uji #6b memisahkan kedua penyebab tersebut dan menguji dua mitigasi.

## 2. Pertanyaan yang Dijawab

1. Berapa Recall@5 pada **query natural** yang menyerupai pemakaian nyata?
2. Apakah **entri dwibahasa** menghilangkan bias bahasa?
3. Apakah **`multilingual-e5-base`** jauh lebih baik, dan berapa biaya ukuran dan kecepatannya?
4. Apakah **Hybrid dengan stopword** lebih baik daripada vektor saja?

## 3. Aturan Dataset

### Yang tidak boleh diubah
`dataset/corpus.json` dan `dataset/queries.json` (v1) **tidak boleh diubah**. Keduanya tetap dievaluasi sebagai set "adversarial". Korpus v1 berisi **500 entri** (Indonesia 250, Inggris 149, campuran 101 — lihat `results/uji06-raw/dataset_stats.json`).

### Definisi persona (berlaku untuk dataset baru)
Pengguna fiktif adalah **Dimas**. Entri yang menyebut "the user" atau "pengguna" merujuk ke Dimas. Query orang pertama ("saya", "aku", "gw", "I", "my") berarti Dimas.

### File baru 1: `dataset/queries_v2.json` (200 query natural)
- Field-nya sama dengan v1, dan distribusi tipenya juga sama (`id-id` 40, `en-en` 30, `id-en` 30, `en-id` 30, `informal` 40, `typo` 30).
- **Gaya query:** pertanyaan yang benar-benar akan diketik orang kepada asistennya. Contoh: *"Sari tidur jam berapa?"*, *"mobil Sari apa?"*, *"gw pake editor apa?"*.
- **Dilarang:** kata arkais atau sastrawi (misalnya "peraduan"), serta query yang membutuhkan pengetahuan dunia untuk dijawab (misalnya "danau" untuk nama tempat tertentu).
- **Kemiripan kata dengan jawaban:**
  - Minimal 30% query tidak berbagi kata isi sama sekali dengan jawabannya (query semantik).
  - Tidak ada query yang menyalin lebih dari 50% kata isi entri jawabannya.
  - Sebaran tingkat kemiripan dihitung otomatis dan dilaporkan.
- **Multi-label:** `relevant_ids` harus memuat **semua** entri yang menurut manusia merupakan jawaban yang benar. Contohnya, *"gw pake editor apa?"* relevan dengan entri tentang VS Code milik "the user" dan entri tema editor milik Dimas. Periksa setiap query terhadap seluruh korpus.
- **Jangan melihat hasil model saat menyusun query.** Daftar kegagalan Uji #6 tidak boleh dijadikan acuan untuk membuat query yang "mudah".

### File baru 2: `dataset/corpus_alt.json` (terjemahan entri)
- Satu terjemahan untuk setiap entri di korpus (500 entri, sama dengan `corpus.json` v1): entri berlabel `lang: "id"` diterjemahkan ke Inggris, entri `lang: "en"` diterjemahkan ke Indonesia, dan entri `lang: "mix"` diterjemahkan ke Inggris. Gunakan field `lang` pada entri asli untuk menentukan arah terjemahan.
- Field: `id` (sama dengan entri asli) dan `text_alt`.
- Terjemahan harus natural, setia pada makna, dan mempertahankan nama diri serta istilah teknis.
- **Konteks desain:** di Nibras, entri memori ditulis oleh AI (D-27). AI dapat menyimpan terjemahan sekaligus saat menulis entri, tanpa panggilan API tambahan.

## 4. Konfigurasi yang Dievaluasi

| Dimensi | Varian |
|---|---|
| Model | `S` = `multilingual-e5-small` int8, `B` = `multilingual-e5-base` int8 |
| Entri | `mono` = teks asli saja, `bi` = teks asli dan `text_alt` di-embed terpisah. Skor entri diambil dari **nilai maksimum** kedua vektor |
| Pencarian | `vec` = vektor saja, `hyb1` = Hybrid RRF bobot setara, `hyb05` = Hybrid RRF dengan bobot FTS5 0,5 |

Total 2 × 2 × 3 = **12 konfigurasi**, masing-masing dievaluasi pada **v1 dan v2**.

### Aturan Hybrid baru
- Hapus stopword Indonesia dan Inggris dari query FTS5. Daftar stopword ditulis sebagai konstanta di kode dan dicantumkan di laporan.
- Pada konfigurasi `bi`, FTS5 mengindeks gabungan `text` dan `text_alt`.
- RRF memakai `k=60` dengan top-50 dari masing-masing sumber.
- Bobot hanya **1,0** dan **0,5**, sesuai yang ditetapkan di sini. **Dilarang mencari bobot terbaik berdasarkan hasil**, karena itu sama dengan overfitting ke set uji.

### Model `e5-base`
- Ambil dengan cara yang sama seperti `prepare_model.py` di Uji #6: gunakan file ONNX int8 resmi jika tersedia. Jika tidak, ekspor lalu lakukan dynamic quantization.
- Verifikasi lisensi dan catat SHA-256 di `MODEL_INFO.json`.

## 5. Kriteria Keputusan (ditetapkan sebelum uji)

Kriteria ini dipakai untuk merekomendasikan revisi D-26. Agen hanya **melaporkan** konfigurasi mana yang memenuhinya. Keputusan akhir diambil melalui review.

| Prioritas | Kondisi | Arah keputusan |
|---|---|---|
| 1 | Ada konfigurasi `S` dengan Recall@5 v2 minimal 80% **dan** Recall@5 `id-en` v2 minimal 70% | Pertahankan e5-small, tambahkan aturan entri dwibahasa atau hybrid sesuai konfigurasi yang lulus |
| 2 | Hanya konfigurasi `B` yang memenuhi kondisi di atas | Pertimbangkan beralih ke e5-base dengan menimbang ukuran dan kecepatannya |
| 3 | Tidak ada yang memenuhi | Strategi pencarian perlu dirancang ulang |

Recall pada v1 tetap dilaporkan sebagai indikator ketahanan terhadap query yang sulit, tetapi tidak menjadi syarat lulus.

## 6. Performa

Untuk model `S` dan `B`, ukur **di proses terpisah** agar angka RAM tidak tercampur:
- Waktu memuat model dan tokenizer.
- Waktu indexing 10.000 entri sintetis (`mono`, dibuat dengan cara yang sama seperti `bench_index.py` di Uji #6 — variasi dari 500 entri asli, dipakai hanya untuk performa) dan 10.000 entri beserta terjemahannya (`bi`, sehingga 20.000 vektor).
- Median dan p95 waktu query.
- Puncak RAM proses.
- Ukuran file model.

## 7. Larangan

- ❌ Jangan mengubah `corpus.json` atau `queries.json` (v1).
- ❌ Jangan mengubah `queries_v2.json` dan `corpus_alt.json` setelah dataset disetujui di Tahap 1.
- ❌ Jangan memakai PyTorch, `transformers`, atau `sentence-transformers` saat evaluasi dan benchmark. Ketiganya hanya boleh dipakai di `prepare_model.py` jika ekspor ONNX memang diperlukan.
- ❌ Jangan memakai layanan online saat evaluasi.
- ❌ Jangan mencari bobot, `k`, atau stopword terbaik berdasarkan hasil.
- ❌ Jangan commit file model.
- ❌ Jangan mengarang atau membulatkan angka secara menguntungkan.

## 8. Tahapan Kerja (WAJIB berurutan)

### Tahap 1: Dataset, lalu BERHENTI untuk review
1. Buat `queries_v2.json`, `corpus_alt.json`, dan script statistik dataset (kemiripan kata dan sebaran tipe).
2. Commit di branch `fase0/uji06b`, lalu buka pull request **draft**.
3. **Berhenti.** Jangan jalankan evaluasi apa pun. Laporkan bahwa dataset siap direview.

### Tahap 2: Evaluasi (setelah dataset disetujui)
4. Jalankan evaluasi dan benchmark.
5. Commit hasil di commit terpisah, lalu ubah pull request dari draft menjadi siap review.

## 9. Deliverable

```
spikes/uji06-embedding/
├── dataset/queries_v2.json
├── dataset/corpus_alt.json
├── (script evaluasi dan benchmark yang diperbarui)
results/
├── uji06b-embedding.md
└── uji06b-raw/         JSON metrik mentah, kegagalan per konfigurasi, MODEL_INFO
```

Isi `results/uji06b-embedding.md`:
1. **Lingkungan** (sama seperti Uji #6).
2. **Model:** sumber, revision, lisensi, ukuran, dan SHA-256 untuk `S` dan `B`.
3. **Statistik dataset v2:** sebaran tipe, sebaran tingkat kemiripan kata, dan jumlah query multi-label.
4. **Tabel Recall@5** untuk 12 konfigurasi × (total dan 6 tipe), untuk v1 dan v2. Recall@1 dan MRR@10 ditulis di file raw.
5. **Tabel performa** `S` dan `B` (`mono` dan `bi`).
6. **Konfigurasi yang memenuhi kriteria bagian 5**, beserta prioritasnya.
7. **Analisis kegagalan** konfigurasi terbaik pada v2.
8. **Daftar stopword** yang dipakai.
