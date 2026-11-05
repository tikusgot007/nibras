# Brief Tugas — v0.1 Tahap 1: Chat Dasar dari USB

**Proyek:** Nibras (asisten AI pribadi yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md`, terutama D-01–D-12, D-15, D-16, D-38–D-40, D-47, D-50, D-51, D-56–D-62
**Tingkat:** **kode aplikasi** (bukan spike). Kode ini menjadi fondasi untuk Tahap 2–5.
**Dijalankan di:** PC Windows pengembang (sesi agen lokal), dengan flashdisk NTFS untuk uji penerimaan.

---

## 1. Tujuan

Di akhir tahap ini, pengguna bisa mencolokkan flashdisk, menjalankan `Nibras.exe`, membuka brankas dengan passphrase, lalu chat dengan satu provider OpenAI-compatible. Riwayat percakapan tersimpan di flashdisk dan muncul lagi saat aplikasi dibuka ulang.

Tahap ini juga meletakkan fondasi yang dipakai semua tahap berikutnya: struktur folder dan database, lock dan recovery, vault, Agent Core thread, adapter provider dengan format pesan kanonik, dan build bundle yang terkunci versinya.

## 2. Ruang Lingkup

**Termasuk:**
1. Launcher `Nibras.exe` (D-60).
2. Startup: layar pemeriksaan, setup pertama atau passphrase, laporan pemulihan jika ada, lalu chat (D-47). Pemeriksaan tulis-baca-hapus di `Data/` (D-58).
3. Lock instance tunggal, penanda `clean_shutdown`, dan alur recovery (D-08).
4. Empat database dengan PRAGMA D-01 dan tabel versi skema (D-05).
5. Vault untuk API key: Argon2id, AES-256-GCM, passphrase setiap peluncuran, auto-lock saat idle (D-09, D-10, D-39).
6. Audit log append-only, minimal untuk event buka dan kunci vault (D-40).
7. Satu adapter provider: **OpenAI-Compatible** (SDK `openai` dengan `base_url`, D-15) di balik antarmuka adapter dan format pesan kanonik.
8. Agent Core di thread asyncio khusus, komunikasi ke UI hanya lewat Qt signal (D-11). Hanya thread ini yang mengakses database.
9. UI chat: sidebar daftar percakapan, area chat dengan kartu per pesan (D-50), Markdown dan highlighting (D-16), render bertahap (D-57), tombol Batalkan selama streaming (D-44), `Ctrl+N` dan `Esc` (D-48).
10. Startup bertahap: jendela tampil dulu, SDK dimuat di latar belakang, pesan ditahan sampai provider siap (D-59).
11. Halaman pengaturan sederhana untuk provider: `base_url`, nama model, dan API key (masuk vault).
12. Status bar minimal: model aktif, status provider, dan status vault beserta sisa waktu auto-lock (sebagian D-42).
13. Tema gelap dasar Midnight Agent beserta font Inter dan JetBrains Mono yang di-bundle (D-51).
14. Tombol "Tutup & Aman Dilepas" dengan indikator progres. Menutup jendela = shutdown penuh (D-47).
15. Logging ke `Data/logs/` dengan rotasi (D-17).
16. Build bundle dengan dependency terkunci (D-61) dan struktur kode sesuai D-62.

**Tidak termasuk** (dikerjakan di tahap lain, **jangan dibuat**):
- Provider OpenAI resmi dan Anthropic, fallback provider, token tracking, budget, dashboard (Tahap 2).
- Memori, embedding, Hybrid Search, Context Builder berlapis (Tahap 3).
- Tools, PowerShell, Policy Engine, kartu persetujuan, Plan Executor (Tahap 4).
- Project, persona, PC Profile, backup/restore, panel kanan, bahasa UI Inggris (Tahap 5).

## 3. Keputusan Desain yang WAJIB Diikuti

| Aturan | Nilai |
|---|---|
| Runtime | Python Embeddable Distribution di `App/python/` (D-12). **Dilarang** PyInstaller, Nuitka, cx_Freeze, atau tool freeze lain |
| Launcher | C, dikompilasi dengan mingw-w64 (D-60). Tugasnya hanya: cek NTFS, set environment, jalankan `pythonw.exe`. Tanpa console |
| Dependency | Dikunci di `requirements.lock` dengan hash (D-61). Build memakai `pip install --require-hashes --target` |
| Struktur kode | `src/nibras/`, `launcher/`, `packaging/`, `tests/` (D-62) |
| SQLite | `journal_mode=DELETE`, `synchronous=FULL`. **Tanpa WAL** (D-01) |
| Lokasi data | Semua di flashdisk: `Data/`, `Temp/`, `Backups/`. **Dilarang** menulis ke `%TEMP%`, `%APPDATA%`, `%LOCALAPPDATA%` |
| Bytecode | `.pyc` di-precompile saat build. Saat runtime `PYTHONDONTWRITEBYTECODE=1` |
| Hak akses | Berjalan tanpa hak admin (D-38). Tidak ada background service atau system tray |
| Threading | UI thread hanya mengurus widget. Agent Core thread menjalankan asyncio, memanggil provider, dan satu-satunya yang mengakses database |
| Render chat | Bertahap, minimal tiap 10 token, plus render akhir (D-57). Tidak render per token |
| Startup | Jendela tampil sebelum SDK `openai` diimpor. Impor SDK di thread latar belakang (D-59) |

### 3.1 Launcher (`launcher/nibras.c`)
1. Tentukan root flashdisk dari lokasi `Nibras.exe` sendiri, bukan dari working directory.
2. Cek file system volume dengan `GetVolumeInformationW`. Kalau bukan NTFS, tampilkan `MessageBox` berisi penjelasan dan panduan singkat konversi (dengan peringatan backup data dulu), lalu keluar. Jangan mengonversi atau memformat apa pun.
3. Set environment untuk proses anak saja: `PYTHONHOME`, `PYTHONNOUSERSITE=1`, `PYTHONDONTWRITEBYTECODE=1`, hapus `PYTHONPATH`, arahkan `TEMP`/`TMP` dan cache Qt ke `Temp/` di flashdisk.
4. Jalankan `App\python\pythonw.exe -m nibras` tanpa jendela console, lalu launcher keluar.
5. Kalau `App\python\pythonw.exe` tidak ada, tampilkan `MessageBox` yang jelas.

### 3.2 Database (D-05)
- `core.db`: pengaturan, penanda sesi, audit log, versi skema.
- `conversations.db`: percakapan dan pesan.
- `memory.db` dan `index.db`: dibuat kosong, hanya berisi tabel versi skema (dipakai Tahap 3).
- Setiap database punya tabel versi skema dan mekanisme migrasi sederhana berbasis nomor versi.
- Pesan yang sedang di-stream saat aplikasi berhenti tidak bersih ditandai `interrupted`, tidak dilanjutkan otomatis (D-08).

### 3.3 Vault (D-09, D-10, D-39)
- File di `Data/vault.bin`. Kunci diturunkan dengan Argon2id, parameternya dikalibrasi agar memakan sekitar 0,5–1 detik di PC pengembang. Parameter disimpan di header file vault.
- Enkripsi AES-256-GCM. Passphrase salah menghasilkan pesan yang jelas, bukan crash.
- Setup pertama: buat passphrase (dua kali ketik), dengan penjelasan tegas bahwa **tidak ada cara memulihkan passphrase yang lupa** (D-10).
- Auto-lock setelah idle. Default 30 menit, bisa diubah di pengaturan. Saat terkunci, pesan yang akan dikirim ditahan dan pengguna diminta memasukkan passphrase. Pesan tidak dibuang.
- API key tidak pernah ditulis ke log, database, atau file lain dalam bentuk terbuka.
- Setiap buka dan kunci vault dicatat di audit log.

### 3.4 Adapter provider (D-15)
- Agent Core hanya mengenal **format pesan kanonik** (role, isi teks, metadata). Adapter menerjemahkannya ke format provider.
- Adapter mendeklarasikan kemampuan model secara eksplisit: streaming, tool calling, vision, dan context window. Di Tahap 1 hanya streaming teks yang dipakai.
- Konfigurasi: `base_url`, nama model, context window (diisi pengguna, dengan default yang jelas), dan API key dari vault.
- Kegagalan teknis (jaringan, timeout, rate limit) **sebelum token pertama diterima** di-retry otomatis maksimal 3 kali dengan jeda bertahap (D-21). Kegagalan di tengah streaming tidak di-retry. Pesan ditandai gagal, teks yang sudah diterima tetap tersimpan, dan pengguna bisa menekan "Coba lagi".
- Konteks yang dikirim: seluruh percakapan selama muat di context window. Kalau tidak muat, pesan terlama dibuang dan UI menampilkan penanda bahwa sebagian riwayat tidak dikirim. Ringkasan bertahap (D-22) dikerjakan di Tahap 3.

## 4. Larangan (Jangan Dilakukan)

- ❌ PyInstaller atau tool freeze apa pun.
- ❌ WAL atau `synchronous` selain `FULL`.
- ❌ Menulis file apa pun di luar flashdisk saat runtime, termasuk cache Qt dan `__pycache__`.
- ❌ Meminta hak admin, membuat service, atau ikon system tray.
- ❌ `pip install` di PC host saat runtime.
- ❌ Menyimpan atau mencatat API key dan passphrase dalam bentuk terbuka di mana pun, termasuk log, test, dan pesan commit.
- ❌ Mengakses database dari UI thread.
- ❌ Memanggil method widget dari thread non-UI.
- ❌ Membuat fitur Tahap 2–5 (lihat bagian 2).
- ❌ Commit bundle `App/`, file `.zip` Python, wheel, database, `vault.bin`, atau file `.env`.
- ❌ Mengubah `docs/decisions.md` dan `docs/briefs/`. Kalau ada konflik atau ambiguitas, berhenti dan tanyakan.

## 5. Uji

### 5.1 Unit test (`tests/`, dijalankan dengan `pytest` di PC pengembang)
Minimal mencakup:
- PRAGMA keempat database benar (`journal_mode=delete`, `synchronous=2`).
- Vault: simpan dan buka dengan passphrase benar, gagal dengan passphrase salah, file vault rusak terdeteksi, API key tidak muncul di file log.
- Lock: instance kedua gagal mengambil lock.
- Recovery: tanpa `clean_shutdown`, startup menjalankan `quick_check`, membersihkan `Temp/`, dan menandai pesan streaming sebagai `interrupted`.
- Adapter: streaming, retry sebelum token pertama, tidak retry di tengah streaming, dan pemotongan konteks. Gunakan server tiruan lokal, **bukan** API sungguhan.
- Migrasi skema dari versi 0 ke versi terbaru.

### 5.2 Uji penerimaan (oleh operator, di flashdisk NTFS)
Agen menulis checklist ini di `results/v01-tahap1-penerimaan.md` (bukan di `docs/`), lalu operator mengisi hasilnya. Checklist minimal:
1. Setup pertama: buat passphrase, isi `base_url`, model, dan API key.
2. Chat dengan respons panjang (minta kode dan tabel). UI tetap responsif, dan Batalkan/`Esc` menghentikan streaming.
3. Tutup dengan "Tutup & Aman Dilepas", buka lagi. Riwayat percakapan masih ada.
4. Passphrase salah ditolak dengan pesan yang jelas.
5. Cabut flashdisk saat streaming, colok lagi, buka aplikasi. Laporan pemulihan muncul, dan pesan yang terputus ditandai.
6. Jalankan `Nibras.exe` dua kali. Instance kedua menampilkan jendela instance pertama, tidak membuka jendela baru.
7. Setelah aplikasi ditutup, periksa `%TEMP%` dan `%LOCALAPPDATA%`: tidak ada file baru dari Nibras.
8. Waktu startup cold start (cabut-colok dulu): catat waktu sampai jendela tampil dan sampai provider siap.

## 6. Deliverable

```
launcher/                    nibras.c dan skrip build launcher
packaging/                   requirements.in, requirements.lock, build_bundle.ps1, install_to_usb.ps1
src/nibras/                  kode aplikasi (lihat D-62)
tests/                       unit test pytest
results/v01-tahap1-penerimaan.md   checklist uji penerimaan beserta hasilnya
README.md                    diperbarui: cara build, cara memasang ke flashdisk, cara menjalankan test
```

## 7. Definisi Selesai

- Semua unit test lulus di PC pengembang. Output `pytest` dilampirkan di pull request.
- Checklist uji penerimaan diisi operator dengan hasil nyata. Butir yang gagal dilaporkan apa adanya.
- `requirements.lock` dipakai saat build, dan build bisa diulang dari repo bersih.
- Kode dikerjakan di branch `v01/tahap1`, lalu dibuka pull request ke `main`. Commit kecil dan bertahap lebih disukai daripada satu commit besar.
