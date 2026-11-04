# Uji #6 / #6b Fase 0: Kualitas Embedding Lokal (Indonesia–Inggris)

Brief Uji #6: `docs/briefs/fase0-uji06-embedding.md`. Brief Uji #6b (lanjutan): `docs/briefs/fase0-uji06b-embedding-lanjutan.md`.

## Isi (Uji #6)
- `prepare_model.py`: unduh ONNX resmi `intfloat/multilingual-e5-small` **atau** `multilingual-e5-base` (fp32 dan int8 resmi) pada revision terpin (`--model small|base`), tulis `MODEL_INFO.json` (lisensi, ukuran, SHA-256). Tanpa PyTorch.
- `dataset/`: `corpus.json` (500 entri), `queries.json` (200 query), `source/` (sumber teks), `build_dataset.py` (generator), `dataset_stats.py` (statistik + persentase anti-bocor).
- `common.py`: embedder (ONNX Runtime + `tokenizers`), FTS5, RRF.
- `evaluate.py`: konfigurasi A (vektor int8), B (vektor fp32), C (FTS5), D (hybrid RRF).
- `bench_index.py`: waktu muat, indexing 10.000 entri, latensi query, RAM.

## Isi tambahan (Uji #6b Tahap 2)
- `dataset/queries_v2.json` (200 query natural), `dataset/corpus_alt.json` (terjemahan 500 entri), `dataset/build_queries_v2.py`, `dataset/build_corpus_alt.py`, `dataset/dataset_stats_v2.py` — dari Tahap 1, disetujui di PR #5, tidak diubah lagi.
- `common.py` diperluas: `STOPWORDS_ID_EN` (konstanta stopword Hybrid), `fts_query_stopwords()`, `FtsIndex.topk(..., query_builder=...)`, `rrf(..., weights=...)`.
- `evaluate_v2.py`: 12 konfigurasi (model S/B × entri mono/bi × pencarian vec/hyb1/hyb05) × query set v1/v2 = 24 run. Lihat `results/uji06b-embedding.md`.
- `bench_index_v2.py`: performa `S` dan `B` **di proses terpisah**, indexing 10.000 entri `mono` dan 10.000 entri `bi` (20.000 vektor).

## Menjalankan (Uji #6)
```
uv venv --python 3.14 C:\nibras-staging\venv06
uv pip install --python C:\nibras-staging\venv06\Scripts\python.exe onnxruntime numpy tokenizers psutil
python prepare_model.py --out C:\nibras-staging\models      # pakai Python apa saja (stdlib)
C:\nibras-staging\venv06\Scripts\python.exe evaluate.py
C:\nibras-staging\venv06\Scripts\python.exe bench_index.py
python dataset\dataset_stats.py
```

## Menjalankan (Uji #6b Tahap 2)
```
python prepare_model.py --model small --out /path/models_s
python prepare_model.py --model base  --out /path/models_b
python evaluate_v2.py --models-s /path/models_s --models-b /path/models_b
python bench_index_v2.py --model S --models-dir /path/models_s   # proses 1
python bench_index_v2.py --model B --models-dir /path/models_b   # proses 2 (terpisah)
```
Hasil mentah ditulis ke `results/uji06-raw/` (Uji #6) dan `results/uji06b-raw/` (Uji #6b). Model disimpan di luar repo, tidak pernah di-commit.

## Catatan dataset
Parafrase query `id-id` dan `en-en` Uji #6 (agar memenuhi syarat anti-bocor ≥60%) dilakukan sebelum evaluasi pertama dijalankan, dan tidak melihat hasil model. Setelah commit dataset, dataset Uji #6 (`corpus.json`, `queries.json`) dan dataset Uji #6b (`queries_v2.json`, `corpus_alt.json`, disetujui di PR #5) tidak diubah lagi.
