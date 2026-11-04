# Laporan Uji #6 Fase 0: Kualitas Embedding Lokal Indonesia–Inggris

**Hasil ringkas: kriteria wajib Recall@5 ≥ 80% GAGAL.** Konfigurasi A (vektor int8) mencapai **60,5%**. Sesuai brief, dataset dan model tidak diubah. Angka di bawah dari eksekusi nyata pada PC AAN-PC.

## 1. Lingkungan

| Item | Nilai |
|---|---|
| OS | Windows 11 (10.0.26200) |
| CPU | Intel Core i5-4460 @ 3,20 GHz, 4 core fisik / 4 logis |
| RAM | 31,9 GB |
| Python | 3.14.8 |
| onnxruntime | 1.31.1 (CPUExecutionProvider) |
| numpy | 2.5.4 |
| tokenizers | 0.23.3 |
| SQLite | 3.53.1 (FTS5 aktif) |

CPU ini Haswell (2014), tanpa AVX-512. Ini relevan untuk model int8 (lihat bagian 2).

## 2. Model

- Sumber: `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- **Lisensi: MIT** (dari front matter model card pada revision terpin). Kriteria lisensi: **LULUS**.
- fp32: `onnx/model.onnx`, 470.268.510 byte, SHA-256 `ca456c06b3a9505d…`.
- int8: file **resmi** `onnx/model_qint8_avx512_vnni.onnx` dari repo (bukan kuantisasi sendiri), 118.346.824 byte, SHA-256 `dd476dd0c2514e9b…`.
- Hash lengkap semua file: `results/uji06-raw/MODEL_INFO.json`.
- Catatan: nama file int8 menyebut `avx512_vnni`. Ia tetap berjalan di CPU tanpa AVX-512 ini (dibuktikan oleh eksekusi), tetapi kecepatannya tidak mewakili CPU yang mendukung VNNI.

## 3. Statistik dataset

- 500 entri: Indonesia 250 (50%), Inggris 149 (29,8%), campuran 101 (20,2%).
- Kategori: Personal Context 181, Workflows 87, User Preferences 84, Projects 57, PC Information 47, Knowledge 44.
- Hard negative: **60 kelompok** (masing-masing 3 entri mirip).
- 200 query: id-id 40, en-en 30, id-en 30, en-id 30, informal 40, typo 30.
- **Anti-bocor: 145/200 = 72,5%** (syarat ≥ 60%). Per tipe: id-id 37/40, en-en 30/30, id-en 23/30, en-id 21/30, informal 20/40, typo 14/30. Definisi: tidak ada kata isi (≥3 huruf, bukan stopword) yang sama antara query dan entri jawabannya (`dataset/dataset_stats.py`).
- Riwayat: dataset di-commit (`bc59df3`) **sebelum** evaluasi pertama. Sebelum commit itu, anti-bocor awal 47,5% sehingga query `id-id` dan `en-en` yang berbagi kata dengan jawabannya diparafrase. Ini dilakukan tanpa melihat hasil model apa pun. Dataset tidak diubah setelah itu.

## 4. Kualitas (n = 200 query)

**Recall@5 (%)**

| Konfigurasi | Total | id-id | en-en | id-en | en-id | informal | typo |
|---|---|---|---|---|---|---|---|
| A vektor int8 | **60,5** | 57,5 | 83,3 | 33,3 | 80,0 | 60,0 | 50,0 |
| B vektor fp32 | 62,5 | 65,0 | 83,3 | 30,0 | 80,0 | 60,0 | 56,7 |
| C FTS5 BM25 | 29,0 | 10,0 | 26,7 | 10,0 | 20,0 | 50,0 | 56,7 |
| D Hybrid RRF | 46,0 | 30,0 | 70,0 | 16,7 | 46,7 | 52,5 | 63,3 |

**Recall@1 (%)**

| Konfigurasi | Total | id-id | en-en | id-en | en-id | informal | typo |
|---|---|---|---|---|---|---|---|
| A | 39,5 | 27,5 | 56,7 | 20,0 | 63,3 | 35,0 | 40,0 |
| B | 40,5 | 30,0 | 56,7 | 16,7 | 63,3 | 42,5 | 36,7 |
| C | 19,0 | 2,5 | 10,0 | 6,7 | 13,3 | 42,5 | 36,7 |
| D | 28,0 | 7,5 | 43,3 | 10,0 | 23,3 | 45,0 | 40,0 |

**MRR@10**

| Konfigurasi | Total | id-id | en-en | id-en | en-id | informal | typo |
|---|---|---|---|---|---|---|---|
| A | 0,482 | 0,398 | 0,661 | 0,252 | 0,717 | 0,449 | 0,456 |
| B | 0,496 | 0,436 | 0,681 | 0,235 | 0,709 | 0,503 | 0,429 |
| C | 0,234 | 0,063 | 0,173 | 0,078 | 0,153 | 0,459 | 0,460 |
| D | 0,373 | 0,173 | 0,561 | 0,142 | 0,367 | 0,506 | 0,511 |

## 5. Performa (int8 kecuali disebut lain)

| Metrik | Nilai |
|---|---|
| Muat tokenizer + model int8 | 0,755 s + 0,543 s |
| Muat tokenizer + model fp32 | 0,867 s + 1,180 s |
| Indexing 10.000 entri (batch 32) | **260,3 s (4,3 menit)**, 26,0 ms/entri |
| Waktu query end-to-end (embedding + similarity + top-k, 200 query) | median **26,0 ms**, p95 44,6 ms |
| Puncak RAM proses (peak working set) | 1.154,8 MB (memuat int8 dan fp32 dalam satu proses, plus matriks 10.000×384 = 14,6 MB) |
| Ukuran file model | int8 112,9 MB, fp32 448,5 MB |

Catatan: puncak RAM mencakup kedua model karena benchmark memuat int8 lalu fp32 dalam satu proses. RAM untuk int8 saja lebih rendah dan tidak diukur terpisah.

## 6. Analisis kegagalan konfigurasi A (79 dari 200 query gagal di top-5)

Sebaran kegagalan: id-en 20, id-id 17, informal 16, typo 15, en-id 6, en-en 5. Daftar lengkap beserta 5 hasil teratas: `results/uji06-raw/failures_config_A.json`.

1. **Lintas bahasa id→en lemah, en→id kuat.** Query Indonesia terhadap entri Inggris hanya 33,3% (20 gagal), sedangkan Inggris terhadap entri Indonesia 80,0%. Pada 17 dari 20 kegagalan `id-en`, hasil teratasnya entri berbahasa Indonesia. Model cenderung memilih entri yang sama bahasanya dengan query, walaupun jawabannya berbahasa Inggris.
2. **Query Indonesia pendek, pertanyaan generik.** Pada `id-id` (17 gagal), hasil teratas hampir selalu berbahasa Indonesia tetapi topiknya salah (contoh: "Di sekolah mana Aira belajar?" mengembalikan entri rapat orang tua dan perlengkapan sekolah, bukan SDN Cipaganti). Entri yang menyebut nama orang (Aira, Dimas) saling menyerupai.
3. **Hard negative.** Pada 16 dari 79 kegagalan, kembaran dari grup yang sama muncul di top-5 tetapi bukan jawaban yang benar. Jadi mayoritas kegagalan (63 dari 79) bukan sekadar tertukar dengan kembaran, melainkan entri yang tidak relevan lebih tinggi.
4. **Informal dan typo** memantul ke 60,0% dan 50,0%. Singkatan dan salah ketik menurunkan kecocokan token, dan model tidak sepenuhnya memulihkannya.
5. **Hybrid (D) lebih buruk dari vektor saja (A)**: 46,0% lawan 60,5%. FTS5 sendiri hanya 29,0%, karena syarat anti-bocor membuat kecocokan kata jarang. Query diubah menjadi `OR` antar token tanpa penghapusan stopword, sehingga kata umum ("apa", "yang", "the") menghasilkan peringkat BM25 yang berisik, dan RRF dengan bobot setara menyeretnya ke bawah. Ini ciri implementasi brief (RRF setara, k=60), bukan eksperimen tuning.

Validitas pipeline: `en-en` 83,3% dengan prefix `query:`/`passage:`, mean pooling, dan normalisasi L2 menunjukkan embedder benar. Sanity check di luar dataset memberi kemiripan wajar (0,885 untuk pasangan benar).

## 7. Evaluasi terhadap kriteria (bagian 9 brief)

| Kriteria | Target | Hasil | Status |
|---|---|---|---|
| Recall@5 A (int8), total | ≥ 80% | 60,5% | **GAGAL (wajib)** |
| Lisensi mengizinkan pakai dan distribusi | Terverifikasi | MIT | **LULUS (wajib)** |
| Recall@5 lintas bahasa A (id-en dan en-id) | ≥ 70% | id-en 33,3%, en-id 80,0%, gabungan 56,7% | Gagal (lunak) |
| Selisih Recall@5 int8 vs fp32 | ≤ 3 poin | 2,0 poin (60,5 vs 62,5) | Lulus (lunak) |
| Hybrid D ≥ A | D ≥ A | 46,0 < 60,5 | Gagal (lunak) |
| Indexing 10.000 entri int8 | < 15 menit | 4,3 menit | Lulus (lunak) |
| Median waktu query | < 200 ms | 26,0 ms | Lulus (lunak) |

**Kesimpulan:** kriteria wajib kualitas tidak terpenuhi. Brief melarang mengganti model atau mengubah dataset untuk membuatnya lulus, jadi tidak ada yang diubah. Keputusan lanjutan (misalnya model yang lebih besar seperti `multilingual-e5-base`, penambahan terjemahan pada saat penyimpanan memori, penyesuaian Hybrid, atau pelonggaran target) diserahkan ke proses review.

## 8. Catatan dependency `tokenizers`

- Versi 0.23.3, terpasang di venv sebesar **7,9 MB** (folder `tokenizers/` dengan wheel biner `cp310-abi3`). Kandidat dependency baru di luar D-17. Hanya dibutuhkan untuk memuat `tokenizer.json`.

## 9. Anomali dan keterbatasan

- Model int8 resmi dibangun untuk AVX-512 VNNI; PC uji tidak memilikinya. Angka latensi di CPU modern bisa berbeda.
- Dataset sintetis dan ditulis oleh agen yang sama dengan pelaksana uji; bukan data pribadi nyata. Query `id-en` yang rendah mencerminkan tipe campuran yang sengaja sulit.
- Dataset anti-bocor awal 47,5% direvisi sebelum evaluasi (lihat bagian 3). Riwayat Git membuktikan urutan.
- Benchmark mengukur seluruh 10.000 entri sintetis dalam satu proses tanpa penyimpanan ke disk.
- Pengukuran dijalankan tanpa menjalankan tugas berat lain secara sengaja; tidak ada pengukuran terpisah untuk gangguan latar.
