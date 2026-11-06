# Nibras

> **Satu asisten AI pribadi di dalam USB.**

Nibras adalah asisten AI pribadi yang berjalan langsung dari USB Flash Drive di berbagai PC Windows, tanpa instalasi apa pun di PC host. Nama *Nibras* berasal dari bahasa Arab yang berarti cahaya atau pelita.

## Status

🧭 **Desain MVP selesai.** Saat ini proyek berada di **v0.1 Tahap 2 (provider lengkap dan fallback)**:
- Dukungan tiga jenis provider: OpenAI, Anthropic, dan OpenAI-Compatible dengan profil dan model tersimpan di `core.db`.
- API key tersimpan aman di brankas per profil.
- Satu model aktif global, dengan opsi model cadangan (fallback).
- Fallback transparan dengan persetujuan pengguna per satu pesan (D-64).
- Mode Dashboard khusus untuk manajemen profil/model dan pengaturan.
- Status bar informatif (model aktif, kesiapan provider, hitung mundur brankas, indikator online).

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

Provider: base URL, nama model, dan context window diisi pengguna di Pengaturan (tidak ada default pribadi di repo publik). API key tidak pernah ditulis di log, database, atau commit.

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
