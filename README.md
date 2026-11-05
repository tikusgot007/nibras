# Nibras

> **Satu asisten AI pribadi di dalam USB.**

Nibras adalah asisten AI pribadi yang berjalan langsung dari USB Flash Drive di berbagai PC Windows, tanpa instalasi apa pun di PC host. Nama *Nibras* berasal dari bahasa Arab yang berarti cahaya atau pelita.

## Status

🧭 **Desain MVP selesai.** Saat ini proyek berada di **Fase 0**, yaitu prototipe untuk menguji risiko teknis sebelum MVP dibangun.

**v0.1 Tahap 1 (chat dasar dari USB)** sedang dikerjakan di branch `v01/tahap1`: chat dengan satu provider OpenAI-Compatible, riwayat tersimpan di flashdisk, brankas API key (Argon2id + AES-256-GCM).

## Menjalankan test (PC dev)

```powershell
python -m venv .venv
.venv\Scripts\pip install -r packaging\requirements.in pytest pytest-asyncio
.venv\Scripts\pytest
```

Test adapter memakai server tiruan lokal, bukan API sungguhan.

## Build bundle (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_bundle.ps1
```

Hasilnya di `build/` (tidak di-commit): `Nibras.exe`, `App\python`, `App\fonts`.

## Pasang ke flashdisk (Windows)

Colok flashdisk NTFS, lalu:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\install_to_usb.ps1 -DriveLetter X:
```

Skrip memverifikasi drive target benar-benar flashdisk USB (BusType USB) dan berformat NTFS, menampilkan ringkasannya, dan meminta konfirmasi sebelum menulis. `Data/` yang sudah ada tidak ditimpa. Setelah itu jalankan `X:\Nibras.exe`.

## Pakai Nibras

1. Colok flashdisk, jalankan `Nibras.exe`.
2. Setup pertama: buat passphrase brankas, lalu isi base URL provider, nama model, dan API key. **Tidak ada pemulihan passphrase yang lupa.**
3. Chat seperti biasa. Riwayat tersimpan di flashdisk dan terbawa ke PC lain.

Default provider: base URL `https://9r90.itroute.web.id/v1`, model `aan-hermes`, context window 1.000.000 token. API key tidak pernah ditulis di log, database, atau commit.

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
