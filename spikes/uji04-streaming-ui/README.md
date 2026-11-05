# Uji #4 — Streaming respons ~5.000 token di UI

Spike (bukan kode aplikasi). Referensi: D-11, D-16, D-50; brief `docs/briefs/fase0-uji04-streaming-ui.md`.

- `token_stream_sim.py` — simulator token lokal (QThread + Qt signal), tanpa LLM.
- `ui_probe.py` — satu jendela, satu kartu `QTextBrowser`, timer 16 ms, klik dan scroll otomatis, dua mode (`full`, `batched`).
- `run_all.py` — menjalankan baseline + 3 fixture x 2 mode x 3 run (melewati hasil yang sudah ada; batas 420 detik per run).
- `aggregate.py` — membuat tabel dari `results/uji04-raw/`.
- `gen_fixtures.py`, `fixtures/` — fixture deterministik.

Dependensi (jangan `pip install` ke PC host): PySide6, markdown-it-py, Pygments.

Jalankan: `python run_all.py` (membutuhkan jendela GUI nyata). Hasil: `results/uji04-streaming-ui.md`.
