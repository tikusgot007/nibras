# Nibras

> **Satu asisten AI pribadi di dalam USB.**

Nibras adalah asisten AI pribadi yang berjalan langsung dari USB Flash Drive di berbagai PC Windows, tanpa instalasi apa pun di PC host. Nama *Nibras* berasal dari bahasa Arab yang berarti cahaya atau pelita.

## Status

🧭 **Desain MVP selesai.** Saat ini proyek berada di **Fase 0**, yaitu prototipe untuk menguji risiko teknis sebelum MVP dibangun.

## Struktur Repo

| Folder | Isi |
|---|---|
| `docs/decisions.md` | Log keputusan desain. Ini sumber kebenaran proyek |
| `docs/briefs/` | Brief tugas untuk agen coding |
| `spikes/` | Kode prototipe Fase 0, satu folder per uji |
| `results/` | Laporan hasil uji |

## Alur Kerja

1. Brief tugas ditulis di `docs/briefs/`.
2. Agen coding mengerjakan brief di branch tersendiri, lalu membuka pull request.
3. Hasil direview terhadap `docs/decisions.md` sebelum di-merge.

## Stack (ringkas)

Python dan PySide6, Python Embeddable Distribution, SQLite (rollback journal), ONNX Runtime, dan Playwright (Chromium di-bundle). Target platform: Windows 10/11 dengan USB berformat NTFS.
