# Uji Penerimaan — v0.1 Tahap 2 (Provider Lengkap dan Fallback)

> Dokumen checklist dan hasil pengujian untuk v0.1 Tahap 2 sesuai brief `docs/briefs/v01-tahap2-provider.md`.
> Bagian otomatis diverifikasi di PC pengembang Windows; bagian checklist di flashdisk diisi oleh operator.

## Status Verifikasi Otomatis (PC Pengembang Windows 11)

Diverifikasi di PC pengembang Windows 11 (Python 3.14.8, PySide6 6.12.0, dependency terkunci dengan hash di `packaging/requirements.lock`):

| Hal | Status | Keterangan |
|---|---|---|
| `pytest` | **Lulus** | 75 test lulus 100% tanpa kegagalan |
| Adapter OpenAI & streaming | **Lulus** | Streaming SSE, retry sebelum token pertama, otentikasi Bearer token |
| Adapter Anthropic & streaming | **Lulus** | Streaming SSE, ekstraksi parameter `system`, translasi pesan kanonikal, retry |
| Lazy import SDK (D-59) | **Lulus** | `anthropic` tidak diimpor ke `sys.modules` saat startup bila model aktif bukan Anthropic |
| CRUD Profil & Model | **Lulus** | Manajemen profil (`openai`, `anthropic`, `openai_compatible`), model, dan cascade delete |
| Vault per profil | **Lulus** | API key disimpan terisolasi per `profile_id`, key legacy tetap aman |
| Migrasi otomatis data Tahap 1 | **Lulus** | Backup otomatis ke `Backups/core_backup_v1_*.db` dan `Backups/vault_backup_v1_*.bin`, pembentukan profil Tahap 1, model aktif, dan pemindahan key |
| Alur Fallback (D-64) | **Lulus** | Retry habis -> kartu fallback muncul -> persetujuan hanya untuk 1 pesan -> pengiriman berikutnya kembali otomatis ke model aktif |
| Penolakan Fallback | **Lulus** | Operator menolak -> pesan berstatus `failed` |
| Kompilasi Launcher C | **Lulus** | `Nibras.exe` (70 KB) berhasil dikompilasi dengan `-municode -mwindows -O2` |
| Build Bundle | **Lulus** | `packaging/build_bundle.ps1` berhasil: Python Embeddable 3.14.10, lock dengan hash, font Inter & JetBrains Mono, launcher |
| Logging startup/shutdown | **Lulus** | Log ditulis ke `Data/logs/nibras.log` pada startup dan shutdown bersih |
| Flashing taskbar instance kedua | **Lulus** | Menggunakan `FlashWindowEx` (`FLASHW_ALL | FLASHW_TIMERNOFG`) saat `SetForegroundWindow` dibatasi Windows |

---

## Checklist Pengujian Operator di Flashdisk USB (NTFS)

- Tanggal pengujian:
- PC pengujian (Windows, CPU/RAM):
- Flashdisk (merek, USB 2.0/3.x, NTFS, Drive Letter):

### 1. Migrasi Data Tahap 1
- [ ] Flashdisk dengan instalasi dan data Tahap 1 dipasang bundle Tahap 2
- [ ] Buka `Nibras.exe`: passphrase lama diterima tanpa error
- [ ] Riwayat percakapan lama masih ada dan tampil utuh
- [ ] Profil `OpenAI-Compatible (Tahap 1)` otomatis terbentuk dan aktif dengan base_url dan API key lama
- [ ] File backup terbentuk di `Backups/core_backup_v1_*.db` dan `Backups/vault_backup_v1_*.bin`
- Catatan / Hasil:

### 2. Tambah Profil & Model Kedua serta Pergantian Model Aktif
- [ ] Buka menu `⚙️ Dashboard` -> tab `Provider & Model`
- [ ] Tambah profil baru (misal: jenis `Anthropic` atau `OpenAI`)
- [ ] Tambah model ke dalam profil tersebut
- [ ] Ganti **Model Aktif** ke model baru yang dibuat
- [ ] Status bar di bagian bawah jendela langsung mencerminkan nama model aktif yang baru
- Catatan / Hasil:

### 3. Fallback: Persetujuan untuk Satu Pengiriman (D-64)
- [ ] Tetapkan **Model Cadangan (Fallback)** di Pengaturan
- [ ] Ubah `base_url` pada model aktif ke alamat yang salah/mati (misal `http://127.0.0.1:9999/v1`)
- [ ] Kirim pesan baru: setelah retry habis, muncul kartu tawaran fallback di bawah pesan
- [ ] Klik **Gunakan Sekali** pada kartu fallback
- [ ] Jawaban berhasil di-stream dari provider cadangan
- [ ] Kirim pesan berikutnya: Nibras otomatis mencoba model aktif kembali (bukan menetap di model cadangan) dan kartu fallback muncul lagi
- Catatan / Hasil:

### 4. Penolakan Fallback
- [ ] Saat kartu fallback muncul, klik tombol **Tolak**
- [ ] Pesan ditandai gagal (`failed`) dan kartu fallback hilang
- Catatan / Hasil:

### 5. Waktu Cold-Start (Diukur Terpisah)
- [ ] Colok ulang flashdisk (cold start)
- [ ] Waktu dari klik `Nibras.exe` sampai jendela tampil: ______ detik
- [ ] Waktu pengetikan passphrase: ______ detik
- [ ] Waktu dari unlock sampai provider siap (status bar hijau/siap): ______ detik
- Catatan / Hasil:

### 6. Kebersihan Log (`Data/logs/nibras.log`)
- [ ] Buka file `Data/logs/nibras.log` setelah aplikasi digunakan
- [ ] Pastikan event startup dan shutdown tercatat
- [ ] Pastikan **TIDAK ADA** API key atau URL request pribadi yang bocor ke file log
- Catatan / Hasil:

### 7. Instance Kedua & Fokus Jendela
- [ ] Buka `Nibras.exe` saat aplikasi sudah berjalan
- [ ] Instance kedua ditolak dan keluar segera (tidak ada jendela ganda)
- [ ] Jendela instance pertama berkedip di taskbar / naik ke depan
- Catatan / Hasil:
