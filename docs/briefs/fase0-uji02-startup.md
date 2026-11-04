# Brief Tugas — Fase 0, Uji #2: Waktu Startup dari USB

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md` (D-02, D-07, D-12, D-14 sampai D-17)
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.

---

## 1. Tujuan

Mengukur waktu yang dibutuhkan bundle Python Embeddable dan PySide6 untuk mencapai kondisi siap pakai ketika dijalankan dari USB. Uji ini juga mengidentifikasi import mana yang paling memperlambat startup.

Pertanyaan yang dijawab:
1. Apakah startup *cold* dari USB 3.x mencapai kondisi siap pakai dalam **kurang dari 10 detik**?
2. Berapa lama sampai jendela pertama muncul?
3. Bagian mana yang paling lambat, dan apakah precompile `.pyc` membantu?
4. Apakah bundle benar-benar terisolasi dari Python yang mungkin terpasang di PC host?

## 2. Ruang Lingkup

**Termasuk:**
- Script build bundle (`build_bundle.ps1`).
- Program probe startup (`startup_probe.py`).
- Script pengukur (`measure_startup.ps1`).
- Script ringkasan (`summarize.py`).
- Panduan prosedur (`README.md`).
- Template laporan.

**Tidak termasuk:** launcher native `Nibras.exe` (bahasanya belum diputuskan), UI chat, Agent Core, Chromium/Playwright, dan pemuatan model ONNX.

## 3. Keputusan Desain yang WAJIB Diikuti

| Aturan | Nilai |
|---|---|
| Runtime | **Python Embeddable Distribution resmi** dari python.org (D-12) |
| Versi Python | Versi terbaru yang memiliki wheel Windows resmi untuk **semua** paket di bagian 5. Catat versi yang dipilih beserta alasannya |
| Lokasi bundle | `App/` di root USB (D-07) |
| Dependency | Dipasang ke bundle saat **build** dengan `pip install --target`, bukan di PC host saat runtime |
| Bytecode | Precompile seluruh `.py` di bundle dengan `compileall` saat build. Saat runtime, set `PYTHONDONTWRITEBYTECODE=1` |
| Isolasi | Set `PYTHONNOUSERSITE=1`. Variabel `PYTHONPATH` dan `PYTHONHOME` milik host tidak boleh berpengaruh |
| Database | Empat database (D-05) dengan `journal_mode=DELETE` dan `synchronous=FULL` (D-01) |

**Catatan teknis:** Python Embeddable menonaktifkan `site` secara default melalui file `._pth`. Paket seperti `pywin32` membutuhkan file `.pth`. Aktifkan `import site` di `._pth` **hanya jika diperlukan**, dan pastikan isolasi tetap terjaga dengan `PYTHONNOUSERSITE=1` serta verifikasi `sys.path` (bagian 6).

## 4. Larangan (Jangan Dilakukan)

- ❌ Jangan memakai PyInstaller, Nuitka, cx_Freeze, atau tool freeze lain dalam mode apa pun.
- ❌ Jangan memakai Python yang terpasang di PC host saat runtime. Python host **hanya boleh** dipakai untuk menjalankan `pip` saat build.
- ❌ Jangan memakai virtualenv atau conda sebagai bundle.
- ❌ Jangan menulis file runtime ke `%TEMP%`, `%APPDATA%`, atau `%LOCALAPPDATA%`. Database uji ditulis ke `Data/` di USB.
- ❌ Jangan menonaktifkan Windows Defender atau antivirus untuk mempercepat hasil. Catat status antivirus apa adanya.
- ❌ Jangan memakai lazy import untuk "mempercepat" angka di uji ini. Uji ini justru mengukur biaya import penuh agar bottleneck terlihat.
- ❌ Jangan menebak hasil. Semua angka harus berasal dari eksekusi nyata.

## 5. Spesifikasi `build_bundle.ps1`

1. Unduh Python Embeddable (`python-X.Y.Z-embed-amd64.zip`) dari python.org, lalu ekstrak ke `App/python/`.
2. Pasang paket berikut ke `App/python/Lib/site-packages/` dengan `pip install --target`:
   `PySide6`, `numpy`, `onnxruntime`, `openai`, `anthropic`, `httpx`, `markdown-it-py`, `Pygments`, `cryptography`, `argon2-cffi`, `psutil`, `pywin32`, `mcp`.
3. Sesuaikan file `._pth` agar `Lib/site-packages` masuk ke `sys.path`.
4. Jalankan `compileall` untuk seluruh bundle.
5. Tulis `App/BUILD_INFO.json` berisi versi Python, versi setiap paket, total ukuran `App/` (MB), dan jumlah file.
6. Sediakan opsi `-NoPrecompile` untuk membangun varian tanpa `.pyc` sebagai pembanding.

## 6. Spesifikasi `startup_probe.py`

Program ini meniru urutan startup aplikasi. Setiap tahap mencatat timestamp, lalu program **keluar otomatis** setelah tahap terakhir.

**Argumen:** `--t0` (epoch ms dari pengukur), `--out` (path JSON hasil), `--data-dir` (folder `Data/` di USB).

| Tanda | Tahap |
|---|---|
| T1 | Baris pertama script dieksekusi (interpreter siap) |
| T2 | `PySide6` diimpor dan `QApplication` dibuat |
| T3 | Jendela sederhana (`QMainWindow` dengan satu label) **ditampilkan dan sudah di-paint**. Gunakan event loop, misalnya `QTimer.singleShot(0, ...)` setelah `show()` |
| T4 | Semua paket lain di bagian 5 sudah diimpor. **Catat waktu setiap import secara terpisah** |
| T5 | Empat database dibuka atau dibuat di `--data-dir` dengan PRAGMA D-01, lalu `PRAGMA quick_check` dijalankan |
| T6 | Siap pakai. Program menulis JSON lalu keluar |

**Verifikasi isolasi** (wajib dicatat di JSON):
- `sys.executable` dan `sys.prefix` berada di dalam folder bundle.
- **Tidak ada** entri `sys.path` yang berada di luar folder bundle.
- `site.ENABLE_USER_SITE` bernilai `False` atau `None`.

Jika verifikasi isolasi gagal, tandai run sebagai **FAIL**.

## 7. Spesifikasi `measure_startup.ps1`

1. Catat `t0` (epoch ms), lalu jalankan `App\python\pythonw.exe startup_probe.py --t0 <t0> ...` dengan environment dari bagian 3.
2. Tunggu proses selesai, dengan timeout 60 detik.
3. Simpan JSON hasil dengan label skenario dan nomor run.
4. Parameter: `-Scenario` (misalnya `usb3-cold`), `-Runs`, `-BundleDir`.

`summarize.py` membaca seluruh JSON dan mencetak tabel Markdown. Isinya median dan maksimum T3 dan T6 per skenario, serta 5 import paling lambat. Hanya memakai standard library.

## 8. Prosedur Uji (oleh operator manusia)

**Cold start** berarti USB dicabut lalu dicolok kembali sebelum run, agar cache file Windows untuk USB tersebut kosong. **Warm start** berarti run langsung diulang tanpa mencabut USB.

| Skenario | Jumlah run |
|---|---|
| `usb3-cold` (port USB 3.x, cabut-colok sebelum setiap run) | 5 |
| `usb3-warm` | 5 |
| `usb2-cold` (USB yang sama di port USB 2.0) | 3 |
| `ssd-cold` (bundle disalin sementara ke disk internal sebagai baseline, lalu dihapus setelah uji) | 3 |
| `usb3-cold-nopyc` (varian `-NoPrecompile`) | 3 |

Gunakan USB yang sama dengan Uji #1 jika memungkinkan. Catat status Windows Defender. Run pertama setelah bundle disalin ke USB boleh lebih lambat karena pemindaian antivirus. Catat run tersebut terpisah sebagai `first-run`, dan jangan masukkan ke skenario mana pun.

## 9. Kriteria Lulus

| Kriteria | Target | Sifat |
|---|---|---|
| Median T6 pada `usb3-cold` | Kurang dari 10 detik | **Wajib** |
| Isolasi `sys.path` | 0 pelanggaran di semua run | **Wajib** |
| Median T3 pada `usb3-cold` | Kurang dari 4 detik | Target lunak |
| `usb2-cold`, `ssd-cold`, `usb3-cold-nopyc` | Dicatat sebagai pembanding | Informasi |

Jika kriteria wajib gagal, **jangan** mengubah pendekatan packaging untuk "membuat lulus". Laporkan apa adanya beserta data bottleneck. Revisi desain diputuskan melalui proses review.

## 10. Deliverable

```
spikes/uji02-startup/
├── build_bundle.ps1
├── startup_probe.py
├── measure_startup.ps1
├── summarize.py
└── README.md        cara build, cara menjalankan, prosedur uji
results/
└── uji02-startup.md
```

**Jangan commit** folder bundle `App/`, file `.zip` Python, atau wheel. Tambahkan pola yang sesuai ke `.gitignore` jika perlu.

Isi `results/uji02-startup.md`:
1. **Lingkungan:** OS, CPU, RAM, merek dan jenis USB, status Windows Defender, versi Python, dan versi paket dari `BUILD_INFO.json`.
2. **Ukuran bundle:** total MB dan jumlah file (versi dengan dan tanpa `.pyc`).
3. **Tabel per skenario:** median dan maksimum T1 sampai T6.
4. **Lima import paling lambat** pada `usb3-cold`.
5. **Hasil verifikasi isolasi.**
6. **Evaluasi** terhadap kriteria di bagian 9.
7. **Catatan anomali**, termasuk hasil `first-run`.

## 11. Definisi Selesai

- Semua larangan di bagian 4 dipatuhi.
- Bundle hanya memakai Python Embeddable dan berjalan tanpa Python host.
- Laporan berisi data nyata dari seluruh skenario di bagian 8.
- Kode dikerjakan di branch `fase0/uji02`, lalu dibuka pull request ke `main`. Pull request kode dan pull request hasil uji boleh dipisah seperti pada Uji #1.
