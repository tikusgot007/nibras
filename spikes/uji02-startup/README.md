# Panduan Uji — Fase 0, Uji #2: Waktu Startup dari USB

Dokumen ini memandu pelaksanaan **Uji #2 Fase 0** proyek **Nibras**: mengukur waktu yang dibutuhkan bundle Python Embeddable Distribution dan PySide6 untuk mencapai kondisi siap pakai saat dijalankan dari drive USB, serta mendeteksi import yang menjadi bottleneck.

---

## 1. Persiapan & Komponen

1. **Hardware**:
   - Drive USB NTFS (misalnya SanDisk 3.2 Gen1).
   - Port USB 3.x dan port USB 2.0 pada PC host.
   - Internal SSD pada PC host (untuk skenario pembanding `ssd-cold`).
2. **Software**:
   - Windows 10/11 64-bit.
   - PowerShell 5.1+.
   - Koneksi internet saat fase build untuk mengunduh Python Embeddable resmi dan wheel paket via `pip`.

---

## 2. Struktur Script

```
spikes/uji02-startup/
├── build_bundle.ps1       # Script pembuat bundle Python Embeddable di App/
├── startup_probe.py       # Program probe pencatat tonggak waktu T1 - T6 & cek isolasi
├── measure_startup.ps1    # Pengukur otomatis per skenario dengan timeout 60 detik
├── summarize.py           # Pembuat rekapitulasi Markdown dari seluruh JSON hasil
└── README.md              # Dokumen panduan ini
```

---

## 3. Langkah 1: Membangun Bundle (`build_bundle.ps1`)

Bundle utama dibangun dengan Python 3.14.10 (versi Python Embeddable resmi, dipilih berdasarkan pengecekan wheel pada bagian 3.1):

```powershell
# Build bundle standar dengan precompile bytecode (.pyc) ke folder App/ di USB
.\spikes\uji02-startup\build_bundle.ps1 -OutputDir "F:\App" -PythonVersion "3.14.10" -Clean

# (Untuk Skenario No-Pyc) Build varian tanpa precompile bytecode ke folder terpisah:
.\spikes\uji02-startup\build_bundle.ps1 -OutputDir "F:\App_nopyc" -PythonVersion "3.14.10" -NoPrecompile -Clean
```

Paket yang diinstal secara otomatis:
`PySide6`, `numpy`, `onnxruntime`, `openai`, `anthropic`, `httpx`, `markdown-it-py`, `Pygments`, `cryptography`, `argon2-cffi`, `psutil`, `pywin32`, `mcp`.

Hasil build menghasilkan file `App/BUILD_INFO.json` yang mencatat ukuran bundle, jumlah file, dan versi setiap paket. Build juga menyalin `startup_probe.py` ke `App\probe\startup_probe.py` di dalam bundle; `measure_startup.ps1` menjalankan probe dari lokasi tersebut.

### 3.1 Pemilihan versi Python (pengecekan wheel, 4 November 2026)

Pengecekan dilakukan dengan `pip download` (pip 26.3) untuk 13 paket di atas beserta dependensinya, tanpa kompilasi dari source:

```text
pip download --only-binary=:all: --platform win_amd64 \
  --python-version 314 --implementation cp --abi cp314 \
  --no-cache-dir -d <dir> <13 paket>
```

Perintah yang sama dijalankan untuk Python 3.13 (`--python-version 313 --abi cp313`).

| Versi Python | Hasil | Wheel terunduh |
|---|---|---|
| 3.14 | BERHASIL | 54 wheel, termasuk `numpy` 2.5.4 (`cp314`), `onnxruntime` 1.31.1 (`cp314`), `pywin32` 312 (`cp314`), `PySide6` 6.12.0 (`abi3`), `cryptography` 50.0.2 (`abi3`) |
| 3.13 | BERHASIL | 54 wheel, termasuk `numpy` 2.5.4 (`cp313`), `onnxruntime` 1.31.1 (`cp313`), `pywin32` 312 (`cp313`), `PySide6` 6.12.0 (`abi3`), `cryptography` 50.0.2 (`abi3`) |

Dipilih **Python 3.14** karena merupakan versi tertinggi yang berhasil untuk semua paket. Patch default **3.14.10** adalah rilis 3.14 terbaru di python.org pada tanggal pengecekan, dan file `python-3.14.10-embed-amd64.zip` terverifikasi tersedia (HTTP 200, 12.619.664 byte). Versi paket di atas adalah versi yang terunduh saat pengecekan; `build_bundle.ps1` tidak mem-pin versi paket. Pengecekan ini hanya membuktikan ketersediaan wheel biner Windows, bukan hasil uji startup di USB.

---

## 4. Langkah 2: Mengukur Startup (`measure_startup.ps1`)

Script pengukur menjalankan probe dari dalam bundle (`<BundleDir>\probe\startup_probe.py`) dengan `pythonw.exe` dan isolasi penuh (`PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`, tanpa `PYTHONPATH`/`PYTHONHOME`). Parameter `-BundleDir` dan `-DataDir` wajib diisi dan tidak memiliki nilai default. Probe mencatat T3 saat paint event pertama jendela benar-benar terjadi (`paintEvent`), lalu menutup jendela.

### Sintaks Pengukuran:

```powershell
.\spikes\uji02-startup\measure_startup.ps1 `
    -Scenario "usb3-cold" `
    -Runs 1 `
    -StartRunIndex 1 `
    -BundleDir "F:\App" `
    -DataDir "F:\Data" `
    -OutDir "results\startup"
```

---

## 5. Prosedur Uji 5 Skenario

> **Definisi:**
> - **Cold Start**: Cabut USB fisik, tunggu ~5 detik, colok kembali sebelum run dijalankan agar cache file sistem operasi Windows untuk volume USB kosong.
> - **Warm Start**: Run dijalankan langsung tanpa mencabut USB (cache file Windows masih aktif).
> - **First Run**: Run pertama kali setelah file bundle baru selesai disalin ke USB (antivirus/Defender biasanya memindai file baru secara intensif). Catat sebagai `first-run` dan jangan masukkan ke tabel skenario utama.

### Urutan Skenario:

1. **`usb3-cold` (5 Run Wajib)**:
   - Hubungkan USB ke port **USB 3.x**.
   - Sebelum setiap run: **cabut USB, tunggu 5 detik, colok kembali**.
   - Jalankan `measure_startup.ps1 -Scenario "usb3-cold" -Runs 1 -StartRunIndex <1..5> -BundleDir "F:\App" -DataDir "F:\Data"`.
2. **`usb3-warm` (5 Run)**:
   - Tetap di port USB 3.x tanpa mencabut USB.
   - Jalankan 5 run berturut-turut: `measure_startup.ps1 -Scenario "usb3-warm" -Runs 5 -BundleDir "F:\App" -DataDir "F:\Data"`.
3. **`usb2-cold` (3 Run Pembanding)**:
   - Pindahkan USB ke port **USB 2.0**.
   - Cabut-colok sebelum setiap run.
   - Jalankan 3 run: `measure_startup.ps1 -Scenario "usb2-cold" -Runs 1 -StartRunIndex <1..3> ...`.
4. **`ssd-cold` (3 Run Pembanding Baseline)**:
   - Salin bundle `App/` sementara ke disk lokal (misal `C:\Temp\App_ssd`).
   - Jalankan 3 run: `measure_startup.ps1 -Scenario "ssd-cold" -Runs 3 -BundleDir "C:\Temp\App_ssd" -DataDir "C:\Temp\Data_ssd"`.
   - Hapus folder sementara setelah selesai.
5. **`usb3-cold-nopyc` (3 Run Pembanding)**:
   - Pasang bundle varian `-NoPrecompile` di USB (`F:\App_nopyc`).
   - Hubungkan ke port USB 3.x, cabut-colok sebelum setiap run.
   - Jalankan 3 run: `measure_startup.ps1 -Scenario "usb3-cold-nopyc" -Runs 1 -StartRunIndex <1..3> -BundleDir "F:\App_nopyc" ...`.

---

## 6. Langkah 3: Merekapitulasi Hasil (`summarize.py`)

Setelah seluruh file JSON terkumpul di `results/startup/`, jalankan:

```powershell
python spikes\uji02-startup\summarize.py --dir "results\startup"
```

Script akan mencetak tabel Markdown berisi median & maksimum T3 (First Paint), T6 (Total Ready), rincian tonggak T1–T6, serta 5 import paling lambat pada `usb3-cold`.

---

## 7. Kriteria Kelulusan

- **Median T6 pada `usb3-cold` < 10 detik** (**Wajib**).
- **Isolasi `sys.path`**: 0 pelanggaran path luar bundle di semua run (**Wajib**).
- **Median T3 pada `usb3-cold` < 4 detik** (Target lunak).
