# Uji #6 Fase 0: Kualitas Embedding Lokal (Indonesia–Inggris)

Brief: `docs/briefs/fase0-uji06-embedding.md`.

## Isi
- `prepare_model.py`: unduh ONNX resmi `intfloat/multilingual-e5-small` (fp32 dan int8 resmi) pada revision terpin, tulis `MODEL_INFO.json` (lisensi, ukuran, SHA-256). Tanpa PyTorch.
- `dataset/`: `corpus.json` (500 entri), `queries.json` (200 query), `source/` (sumber teks), `build_dataset.py` (generator), `dataset_stats.py` (statistik + persentase anti-bocor).
- `common.py`: embedder (ONNX Runtime + `tokenizers`), FTS5, RRF.
- `evaluate.py`: konfigurasi A (vektor int8), B (vektor fp32), C (FTS5), D (hybrid RRF).
- `bench_index.py`: waktu muat, indexing 10.000 entri, latensi query, RAM.

## Menjalankan
```
uv venv --python 3.14 C:\nibras-staging\venv06
uv pip install --python C:\nibras-staging\venv06\Scripts\python.exe onnxruntime numpy tokenizers psutil
python prepare_model.py --out C:\nibras-staging\models      # pakai Python apa saja (stdlib)
C:\nibras-staging\venv06\Scripts\python.exe evaluate.py
C:\nibras-staging\venv06\Scripts\python.exe bench_index.py
python dataset\dataset_stats.py
```
Hasil mentah ditulis ke `results/uji06-raw/`. Model disimpan di luar repo.

## Catatan dataset
Parafrase query `id-id` dan `en-en` (agar memenuhi syarat anti-bocor ≥60%) dilakukan sebelum evaluasi pertama dijalankan, dan tidak melihat hasil model. Setelah commit dataset, dataset tidak diubah.
