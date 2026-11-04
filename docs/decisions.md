# Nibras — Log Keputusan Desain

> **Nibras — Satu asisten AI pribadi di dalam USB.**

Dokumen ini adalah **sumber kebenaran desain** proyek Nibras. Setiap implementasi wajib mengikuti keputusan di sini. Jika implementasi perlu menyimpang, hentikan pekerjaan dan ajukan revisi keputusan. Jangan menyimpang diam-diam.

**Status:** Desain MVP selesai. Fase 0 sedang berjalan (Uji #1, #5, dan #6b lulus).

**Arti status:**
- **Disetujui:** keputusan final.
- **Perlu validasi:** keputusan final, tetapi harus dibuktikan di Fase 0.
- **Tervalidasi:** keputusan sudah dibuktikan melalui uji Fase 0.
- **Ditunda:** belum diputuskan dan akan dibahas pada topik terkait.

---

## 1. Ringkasan Produk

Nibras adalah asisten AI pribadi yang berjalan dari USB Flash Drive di berbagai PC Windows tanpa instalasi apa pun di PC host.

Karakteristik utama:
- **Truly portable.** Runtime dan seluruh dependency di-bundle di USB.
- **On-demand.** Aplikasi berjalan saat diluncurkan dan berhenti total saat ditutup. Tidak ada background service.
- **Single agent** dengan Balanced Autonomy (risk level L0–L4).
- **Memori jangka panjang**, dengan USB sebagai single source of truth.
- **Multi-provider:** OpenAI, Anthropic, OpenAI-Compatible, dan Custom Adapter.
- **Satu model global aktif** untuk semua persona. Tidak ada dynamic routing.
- **Multi-PC sequential.** USB dipakai bergantian di beberapa PC, tidak bersamaan.

### Risk Level

| Level | Arti | Perlakuan |
|---|---|---|
| L0 | Read-only | Langsung dijalankan |
| L1 | Risiko rendah | Otomatis (jika diminta pengguna) |
| L2 | Risiko menengah | Memerlukan persetujuan |
| L3 | Risiko tinggi | Persetujuan eksplisit dan pemeriksaan tambahan |
| L4 | Terlarang | Tidak pernah dijalankan |

AI tidak boleh menurunkan risk level, termasuk ketika pengguna memerintahkannya.

---

## 2. Technical Architecture

| ID | Keputusan | Status |
|---|---|---|
| D-01 | Data kerja ditulis langsung di USB. SQLite **tanpa WAL** (rollback journal), commit sering, backup atomik | Tervalidasi (Uji #1: 20/20 PASS) |
| D-02 | Stack utama: Python dan PySide6, Portable Python Runtime, launcher `Nibras.exe` | Disetujui |
| D-03 | Satu proses aplikasi. Skills dan tool berisiko dijalankan sebagai subprocess | Disetujui |
| D-04 | Format USB **wajib NTFS** | Disetujui |
| D-05 | Database dipisah per domain: `core.db`, `memory.db`, `conversations.db`, `index.db` | Tervalidasi (Uji #1: atomisitas `ATTACH`) |
| D-06 | Data terstruktur dan bervolume tinggi disimpan di database. Konten yang dibaca atau diedit manusia disimpan sebagai file. Perubahan file dideteksi dengan hash | Disetujui |
| D-07 | Struktur folder USB: `App/`, `Data/`, `Backups/`, `Temp/`. Folder temp berada di USB dan dibersihkan saat startup dan shutdown | Disetujui |
| D-08 | Exclusive file lock dari OS ditambah penanda sesi `clean_shutdown`. Pemulihan otomatis setelah shutdown tidak bersih. Tugas yang terputus ditandai *interrupted* | Disetujui |
| D-11 | Event loop asyncio berjalan di thread khusus Agent Core. Komunikasi dengan UI melalui Qt signals | Disetujui |

### Prinsip turunan
- **Single writer:** hanya thread Agent Core yang mengakses database (D-03, D-11).
- Batas modul dijaga bersih: UI, Agent Core, Storage, Tools.
- Subprocess **bukan** sandbox penuh. Sandbox skills dibahas pada Skills Architecture (v0.2).
- Launcher menolak berjalan jika volume bukan NTFS, lalu menampilkan panduan konversi beserta peringatan risiko data.
- `index.db` berisi data turunan dan selalu dapat dibangun ulang dari data sumber.
- Transaksi lintas database menggunakan `ATTACH`. Dalam mode rollback journal, transaksi seperti ini tetap atomik.
- Isolasi project dijaga di level skema (kolom `project_id` dan aturan akses), bukan dengan memecah file database.
- Jika file skill executable diubah secara manual, skill tersebut wajib divalidasi ulang sebelum dipakai.
- Tugas yang berstatus *interrupted* **tidak** dilanjutkan otomatis.
- **Urutan shutdown:** hentikan task, hentikan subprocess, lakukan commit terakhir, tulis `clean_shutdown`, lalu lepas lock.

### Alur startup setelah shutdown tidak bersih (D-08)
1. Aplikasi mencoba mengambil lock. Jika gagal, berarti instance lain sedang berjalan, dan jendela instance tersebut ditampilkan.
2. Jika penanda sesi terakhir bukan `clean_shutdown`, aplikasi menjalankan `PRAGMA quick_check` pada semua database, membersihkan `Temp/`, menandai tugas terputus sebagai *interrupted*, lalu memberi laporan kepada pengguna.
3. Jika ada database yang rusak, aplikasi menawarkan restore dari backup valid terakhir.

### Struktur folder USB (D-07)
```
USB:\
├── Nibras.exe
├── App\          runtime dan kode aplikasi; dapat diganti saat update
├── Data\         databases, personas, projects, skills, vault, logs
├── Backups\
└── Temp\         dibersihkan saat startup dan shutdown
```

---

## 3. Keamanan Dasar

| ID | Keputusan | Status |
|---|---|---|
| D-09 | Enkripsi **hanya untuk credential vault**, menggunakan kunci yang diturunkan dari passphrase. Data lain tidak dienkripsi | Disetujui |
| D-10 | Passphrase diminta setiap peluncuran. Vault terkunci otomatis setelah idle (durasi dapat dikonfigurasi). Kunci hanya disimpan di memori | Disetujui |

### Risiko yang diterima secara sadar
- Jika USB hilang, memori, riwayat percakapan, dan PC profile dapat dibaca orang lain.
- Backup juga tidak terenkripsi, kecuali vault yang tetap terenkripsi di dalam backup.
- Desain ini kompatibel dengan BitLocker To Go jika suatu saat diaktifkan secara manual.

### Prinsip turunan
- Tidak ada mekanisme recovery passphrase. Setup awal wajib menjelaskan konsekuensi lupa passphrase.
- Saat vault terkunci, tugas yang membutuhkan credential dijeda, bukan dibatalkan.
- Tidak ada materi kunci yang disimpan di PC host.

---

## 4. Technology Selection

| ID | Keputusan | Status |
|---|---|---|
| D-12 | Python Embeddable Distribution di `App/`, ditambah launcher native kecil. Interpreter yang sama dipakai untuk subprocess skills | Disetujui |
| D-13 | Chromium milik Playwright di-bundle di `App/` | Disetujui |
| D-14 | Local embedding menggunakan ONNX Runtime (CPU) dengan model multilingual kecil terkuantisasi | Disetujui |
| D-15 | SDK resmi `openai` dan `anthropic` di balik Provider Adapter buatan sendiri. OpenAI-Compatible memakai SDK `openai` dengan `base_url`. Custom Adapter memakai `httpx` | Disetujui |
| D-16 | Chat dirender dengan `QTextBrowser`. Markdown dikonversi ke HTML sederhana dengan `markdown-it-py`, dan syntax highlighting memakai `Pygments` | Disetujui |
| D-17 | Library pendukung: `psutil`, `pywin32`, Windows PowerShell 5.1 bawaan OS (dipanggil dengan `-NoProfile`), `cryptography`, `argon2-cffi`, SDK `mcp`, `pywinauto` (bergantung scope), dan `logging` dengan rotasi | Disetujui |
| D-56 | **PowerShell selalu dipanggil dengan `-Command`, tidak pernah menjalankan file `.ps1`.** Pemanggilan memakai `powershell.exe -NoProfile -NonInteractive -Command <script>`. Skill yang butuh skrip panjang mengirim isi skrip lewat `-Command`, bukan lewat path file. Alasan: Uji #5 menunjukkan ExecutionPolicy `Restricted` hanya memblokir file `.ps1`, tidak memblokir `-Command`. Memperkuat D-17 | Disetujui |

### Prinsip turunan
- Semua dependency di-bundle saat build. **Tidak ada `pip install` di PC host.**
- Tugas launcher: memeriksa NTFS, mengatur `PYTHONHOME` dan `PYTHONDONTWRITEBYTECODE`, mengarahkan cache Qt dan Playwright ke `Temp/`, lalu menjalankan `pythonw.exe` tanpa jendela console.
- Versi Playwright dan Chromium dikunci bersama.
- Profil browser selalu diarahkan ke USB.
- Setiap vektor embedding menyimpan nama model, versi, dan dimensinya. Indeks cloud dan lokal dipisah. Pergantian model memicu re-indexing `index.db`.
- Agent Core hanya mengenal satu **canonical message format**. Adapter bertugas menerjemahkan format ini dan mendeklarasikan kemampuan model secara eksplisit (tool calling, streaming, vision, context window).
- Komponen chat diisolasi di balik antarmuka view agar dapat diganti.
- Log disimpan di `Data/logs/` dengan ukuran terbatas.

### Estimasi ukuran `App/`
Sekitar 0,5–0,9 GB. Rekomendasinya USB 3.x berkapasitas minimal 32 GB dengan performa random write yang baik.

### Ditunda
- Bahasa implementasi launcher (ditentukan saat implementasi).

---

## 5. AI Core Specification

| ID | Keputusan | Status |
|---|---|---|
| D-18 | Kompleksitas tugas ditentukan secara hybrid. Aturan deterministik memaksa mode rencana (tindakan L2 ke atas, banyak langkah, perubahan banyak file). Di luar itu model yang menentukan. Model boleh menaikkan kategori, tetapi tidak boleh menurunkannya | Disetujui |
| D-19 | Persetujuan rencana diikat ke tindakan dan parameter yang spesifik. Langkah L0–L1 dan langkah L2 yang tercantum di rencana disetujui sekali. Langkah L3 dikonfirmasi ulang tepat sebelum eksekusi. Setiap penyimpangan (tindakan baru, target berubah, risiko lebih tinggi) menghentikan eksekusi dan memerlukan persetujuan baru | Disetujui |
| D-20 | Risk level ditentukan dari baseline statis per tool ditambah aturan konteks deterministik di Policy Engine. Model boleh mengusulkan kenaikan, tetapi tidak boleh menurunkan. Tool atau skill baru default L2 | Disetujui |
| D-21 | Retry dibedakan berdasarkan jenis kegagalan dan sifat tindakan, ditambah anggaran per tugas | Disetujui |
| D-22 | Konteks disusun berlapis dengan anggaran per lapisan, diurutkan dari yang paling stabil | Disetujui |
| D-23 | Proactive Initiative bertingkat | Disetujui |

### Rincian D-21: retry dan recovery
- **Kegagalan teknis** (jaringan, timeout, rate limit) pada tindakan idempotent di-retry otomatis dengan jeda bertahap, maksimal 3 kali.
- **Tindakan non-idempotent** (kirim, submit, hapus, transaksi) **tidak pernah** di-retry otomatis. Sistem memverifikasi dulu apakah tindakan sudah terjadi, lalu bertanya kepada pengguna.
- Maksimal 2 pendekatan alternatif per langkah. Alternatif yang memakai tindakan baru tetap mengikuti aturan penyimpangan D-19.
- **Anggaran per tugas** mencakup jumlah langkah, token, dan waktu. Jika terlampaui, tugas dijeda dan pengguna ditanya apakah ingin melanjutkan.
- Metadata `idempotent` disimpan di definisi tool bersama risk level.

### Rincian D-22: lapisan konteks
1. **Lapisan tetap:** aturan sistem dan keamanan, persona aktif, instruksi project.
2. **Memori relevan:** hasil Hybrid Search dari cakupan yang diizinkan, dibatasi top-k dan anggaran token.
3. **Ringkasan bertahap** pesan lama, dibuat hanya ketika ambang tertentu terlampaui.
4. **Pesan terbaru** secara utuh.
5. **Hasil tool:** hasil yang besar disimpan terpisah. Konteks hanya memuat potongan atau ringkasan beserta referensinya.

Konten web, file eksternal, dan hasil tool selalu ditandai sebagai **untrusted data** dan tidak pernah ditempatkan di lapisan aturan sistem. Urutan lapisan dirancang agar ramah terhadap prompt caching.

### Rincian D-23: Proactive Initiative
- Pemeriksaan L0 lokal tanpa panggilan API boleh berjalan otomatis. Contohnya pembaruan PC profile, deteksi known issues, pemeriksaan tugas *interrupted*, dan pemeriksaan ruang disk.
- Tindakan L1 ke atas **atas inisiatif AI** selalu diusulkan dan memerlukan persetujuan.
- Panggilan API untuk inisiatif hanya dipicu oleh temuan lokal yang relevan, dengan anggaran harian terpisah yang tercatat di token tracking.
- Setiap kategori inisiatif dapat dimatikan, dan frekuensi saran dibatasi.

### Komponen yang muncul
Policy Engine, Plan Executor (mencocokkan setiap tindakan dengan rencana yang disetujui), Context Builder, metadata tool (`risk_level`, `idempotent`), dan audit log.

### Ditunda
- Angka default anggaran per tugas.
- Proporsi anggaran setiap lapisan konteks dan ambang ringkasan.

---

## 6. Memory & Storage Specification

| ID | Keputusan | Status |
|---|---|---|
| D-24 | Vektor disimpan sebagai BLOB di `index.db` dan dicari secara brute-force dengan `numpy`, di balik antarmuka `VectorIndex` | Perlu validasi |
| D-25 | Entri memori berupa pernyataan atomik dalam bahasa alami ditambah metadata terstruktur | Disetujui |
| D-26 | Model embedding lokal: `multilingual-e5-small` dalam format ONNX terkuantisasi int8, dengan dimensi 384 | **Lulus** (Uji #6b: Recall@5 94,0% dengan entri dwibahasa + Hybrid, lihat D-55) |
| D-27 | Alur usulan memori melalui chip di akhir respons dan Memory Inbox | Disetujui |
| D-28 | Consolidation dan archiving berbasis usulan yang memerlukan persetujuan | Disetujui |
| D-29 | Ranking Hybrid Search: Reciprocal Rank Fusion, lalu penyesuaian berdasarkan prioritas | **Lulus** (Uji #6b, bobot FTS5 tetap 0,5 — lihat D-55) |
| D-30 | Backup dan restore atomik dengan verifikasi | Disetujui |
| D-31 | Identifikasi PC dengan fingerprint gabungan berbobot | Perlu validasi (Uji #9) |
| D-55 | **Entri memori disimpan dwibahasa untuk pencarian.** Setiap entri menyimpan `text` (bahasa asli) dan `text_alt` (terjemahan), ditulis AI sekaligus saat entri dibuat (tanpa panggilan API tambahan, memperkuat D-27). Kedua teks di-embed terpisah; skor entri diambil dari nilai **maksimum** kedua vektor. Hybrid Search (D-29) memakai bobot FTS5 **0,5** tetap, dengan stopword Indonesia dan Inggris dihapus dari sisi query. Mempertahankan `multilingual-e5-small` (D-26); `multilingual-e5-base` **tidak dipakai** karena ukuran/kecepatan/RAM lebih mahal tanpa kebutuhan nyata | Disetujui |

### Rincian D-25: entri memori
- **Isi:** satu pernyataan atomik.
- **Metadata:**
  - Kategori.
  - Scope (global/persona/project).
  - Sumber (conversation dan pesan asal).
  - Tingkat kepentingan.
  - Waktu dibuat, terakhir dipakai, dan terakhir dikonfirmasi.
  - Status (aktif/diarsipkan/*superseded*).
  - Relasi.
- Pembaruan memori **tidak menimpa** entri lama. Entri lama diberi status *superseded* sehingga riwayat tetap ada.
- PC Profiles (di `core.db`) dan Skills (sebagai file) **bukan** entri memori. Entri memori cukup merujuk ke keduanya.

### Rincian D-27 sampai D-29
- **D-27:** perintah eksplisit seperti "ingat ini" langsung disimpan dan pengguna diberi notifikasi. Usulan yang tidak ditanggapi masuk ke Memory Inbox. **Tidak ada penyimpanan diam-diam.**
- **D-28:** deteksi duplikat dan kontradiksi dijalankan sebagai pemeriksaan L0 lokal. Hasilnya berupa usulan penggabungan yang memerlukan persetujuan. Entri yang lama tidak dipakai dan berprioritas rendah diusulkan untuk diarsipkan. Arsip tetap dapat dicari. **Tidak ada penghapusan otomatis.**
- **D-29:** hasil FTS5 dan vektor digabung dengan Reciprocal Rank Fusion, lalu urutan disesuaikan dengan importance, recency, dan scope. Tidak ada panggilan API tambahan, dan berjalan offline.

### Rincian D-30: backup dan restore
- Menggunakan SQLite backup API. Hasilnya ditulis ke file sementara lalu di-rename.
- Setiap backup diverifikasi dengan `integrity_check` dan manifest hash.
- Backup otomatis dibuat sebelum migrasi skema atau perubahan penting, dan saat shutdown bersih (maksimal sekali sehari).
- Retensi default: 7 backup harian dan 4 mingguan.
- `index.db` tidak di-backup karena dapat dibangun ulang. Folder `Data/` lainnya ikut di-backup.
- Sebelum restore, kondisi saat ini selalu di-backup terlebih dahulu.

### Rincian D-31: identifikasi PC
- Fingerprint gabungan berbobot dari `MachineGuid`, nama komputer, serial BIOS/motherboard, serial disk sistem, dan alamat MAC.
- Skor tinggi berarti PC dikenali otomatis. Skor ragu-ragu membuat sistem bertanya kepada pengguna. Fingerprint yang belum dikenal memicu usulan profil baru.

### Ditunda
- Detail skema tabel (dibuat saat implementasi, mengikuti D-25).

---

## 7. MVP Scope

| ID | Keputusan | Status |
|---|---|---|
| D-32 | Pembagian tahap: Fase 0, v0.1, v0.2, dan v0.3+ seperti di bawah | Disetujui |

### Fase 0: prototipe uji risiko
Prototipe kecil yang terpisah dari aplikasi. Rincian ujinya ada di D-52.

### v0.1 (MVP): asisten inti yang andal
- **Fondasi:** launcher, pemeriksaan NTFS, lock dan recovery, backup dan restore.
- **Keamanan:** vault, passphrase, auto-lock, Policy Engine, audit log.
- **Provider:** OpenAI, Anthropic, OpenAI-Compatible, beserta fallback dengan persetujuan.
- **Biaya:** token tracking, cost estimation, budget limit (Hard Stop, Ask Permission, Soft Limit).
- **UI:** chat dan dashboard dasar.
- **Organisasi:** project, conversation, dan 4 persona bawaan yang instruksinya dapat diedit.
- **AI Core:** seluruh D-18 sampai D-23.
- **Memori:** entri, usulan, dan Hybrid Search dengan **embedding lokal saja**.
- **Tools:** operasi file (workspace USB dan workspace eksternal dengan izin), informasi PC, proses, Event Log, dan PowerShell.
- **PC Profile** beserta identifikasi PC.

### v0.2
- Skills: dibuat manual atau oleh AI, dengan validasi, sandbox, versioning, dan rollback.
- Web research dengan browser read-only.
- MCP.

### v0.3 dan seterusnya
- Interaksi web (submit form, kirim pesan).
- Cloud embedding.
- Custom API Adapter.
- Pembuatan connector.
- Duplicate detection dan file relationships.
- GUI Automation.
- Self-evolution untuk persona dan workflow.

---

## 8. Security Detail (MVP)

| ID | Keputusan | Status |
|---|---|---|
| D-33 | Baseline risk level tool MVP | Disetujui |
| D-34 | Aturan konteks Policy Engine | Disetujui |
| D-35 | Daftar tindakan L4 | Disetujui |
| D-36 | Penghapusan aman | Disetujui |
| D-37 | Izin workspace eksternal | Disetujui |
| D-38 | Aplikasi selalu berjalan tanpa hak admin. Tindakan L3 yang membutuhkan admin memicu prompt UAC per tindakan | Disetujui |
| D-39 | Detail vault | Disetujui |
| D-40 | Audit log append-only | Disetujui |

### D-33: baseline risk level
- **L0:** membaca file, informasi PC, Event Log, pencarian memori, dan cmdlet PowerShell dari **allowlist** read-only.
- **L1:** membuat atau mengedit file di workspace USB (versi lama disimpan), dan menyimpan memori atas perintah eksplisit.
- **L2:** mengubah atau menghapus file di workspace eksternal, menghapus file di workspace USB, menjalankan script PowerShell bebas (script ditampilkan utuh), dan mengubah pengaturan aplikasi.
- **L3:** registry, service, folder sistem, instal atau uninstal software, operasi yang membutuhkan hak admin, operasi massal di luar workspace, dan penghapusan permanen.

### D-34: aturan konteks
Aturan ini hanya boleh **menaikkan** risk level, tidak pernah menurunkan.
- Target di luar workspace yang diizinkan: naik minimal satu level.
- Folder sistem atau registry HKLM: minimal L3.
- Tindakan tidak dapat dibatalkan (hapus permanen, kirim, submit): minimal L2.
- Operasi massal di atas ambang tertentu (misalnya lebih dari 20 file): naik satu level.
- Tool atau skill baru yang belum diklasifikasikan: default L2.
- **Pertahanan prompt injection:** tindakan yang muncul setelah AI membaca konten eksternal dan tidak ada dalam permintaan pengguna dianggap penyimpangan (D-19), sehingga wajib disetujui.

### D-35: daftar L4
- Memodifikasi Security Layer, Policy Engine, atau audit log.
- Membaca isi vault secara mentah.
- Mengirim credential ke pihak luar.
- Menonaktifkan antivirus atau firewall.
- Menghapus seluruh backup.
- Menaikkan hak akses aplikasi secara permanen.

### D-36 dan D-37
- **D-36:** file di workspace USB dipindahkan ke `Data/trash/`, dan file di workspace eksternal dipindahkan ke Recycle Bin. Penghapusan permanen termasuk L3.
- **D-37:** izin diberikan per folder dan per project, dengan mode read-only atau read-write. Izin terikat ke PC Profile, karena path folder bisa berbeda di setiap PC.

### D-39: vault
- Kunci diturunkan dengan Argon2id. Parameternya dikalibrasi sekitar 0,5–1 detik di PC biasa.
- Enkripsi menggunakan AES-256-GCM, dan file vault disimpan di `Data/`.
- Saat passphrase diganti, vault dienkripsi ulang.
- **Catatan jujur:** Python tidak dapat menjamin kunci benar-benar terhapus dari RAM. Penghapusan dilakukan sebaik mungkin (*best effort*).

### D-40: audit log
- Disimpan sebagai tabel append-only di `core.db`.
- Mencatat persetujuan, tindakan L2 ke atas, penolakan oleh Policy Engine, dan setiap buka/kunci vault.
- Retensi dapat dikonfigurasi.

### Ditunda
- Lokasi sesi login browser (`Data/` atau `Temp/`). Dibahas di v0.2.

---

## 9. UI/UX Specification

| ID | Keputusan | Status |
|---|---|---|
| D-41 | Layout: sidebar kiri (project dan conversation), chat di tengah, panel kanan yang dapat diciutkan (rencana aktif, aktivitas tool, memori yang dipakai). Dashboard dibuka sebagai mode tersendiri | Disetujui |
| D-42 | Status bar: model aktif, status provider, biaya hari ini dibanding budget, status vault beserta sisa waktu auto-lock, PC Profile aktif, status online atau offline | Disetujui |
| D-43 | Kartu persetujuan di chat: tindakan, target, parameter, label risk level, dan dampak, dengan tombol Setujui, Edit, dan Tolak. L3 mewajibkan pengguna melihat detail lengkap (diff atau script) dan mencentang konfirmasi. Langkah di kartu rencana dapat diedit | Disetujui |
| D-44 | Transparansi tool: ringkasan aktivitas yang dapat dibuka per respons, penanda konten eksternal, dan tombol **Batalkan** yang selalu terlihat selama tugas berjalan | Disetujui |
| D-45 | Memori: chip usulan (Simpan, Ubah, Tolak), Memory Inbox, dan Memory Browser (filter, edit, arsip, riwayat versi) | Disetujui |
| D-46 | Isi dashboard: Provider & Model, Budget & Usage, Memory, Personas, Projects, PC Profiles, Backup & Restore, Security (vault, audit log, izin workspace), Settings | Disetujui |
| D-47 | **Startup:** layar pemeriksaan, passphrase, laporan pemulihan (jika ada), konfirmasi PC (jika ragu), lalu chat. **Shutdown:** tombol "Tutup & Aman Dilepas" dengan indikator progres. Menutup jendela sama dengan shutdown penuh. Tidak ada system tray | Disetujui |
| D-48 | Bahasa UI: Indonesia dan Inggris. Bahasa respons AI terdeteksi otomatis. Tema mengikuti Windows. Shortcut `Ctrl+N` (chat baru), `Ctrl+K` (cari), dan `Esc` (batalkan tugas) | Disetujui |
| D-49 | Notifikasi proaktif ditampilkan sebagai banner kecil di panel kanan, bukan popup. Jumlahnya dibatasi per sesi, dan setiap kategori dapat dimatikan | Disetujui |
| D-50 | Setiap pesan chat dibuat sebagai widget kartu tersendiri (QSS), dengan Markdown dirender di dalamnya | Disetujui |
| D-51 | Tema **Midnight Agent** | Disetujui |

### Rincian D-51: tema Midnight Agent
- Latar gelap biru-arang dengan aksen cyan/teal. Varian terang juga tersedia.
- **Warna aksen per persona:** Personal Assistant ungu, Windows Administrator cyan, Coding Assistant hijau, Research Analyst amber.
- **Warna risk level:** L0 abu-abu, L1 biru, L2 kuning, L3 merah, L4 merah gelap terkunci.
- Font di-bundle di `App/`: Inter untuk teks dan JetBrains Mono untuk kode (keduanya berlisensi OFL).
- Animasi seperlunya saja (indikator streaming, transisi panel).

---

## 10. Fase 0 dan Identitas

| ID | Keputusan | Status |
|---|---|---|
| D-52 | Rencana Fase 0: 9 uji risiko dengan kriteria lulus | Disetujui |
| D-53 | Nama aplikasi **Nibras** (bahasa Arab: cahaya, pelita). Repo `nibras`, launcher `Nibras.exe` | Disetujui |

### D-52: uji Fase 0

| # | Uji | Kriteria lulus | Keputusan terkait |
|---|---|---|---|
| 1 | Cabut USB saat SQLite sedang menulis, 20 kali | Tidak ada database rusak. Paling banyak hanya transaksi terakhir yang hilang | D-01, D-04, D-05 — **LULUS** (lihat bagian 12) |
| 2 | Waktu startup dari USB 3.x dan 2.0 | Di bawah 10 detik pada USB 3.x | D-02, D-12 |
| 3 | Antivirus dan SmartScreen terhadap launcher | Tercatat, dan ada solusi untuk setiap blokir | D-12 |
| 4 | Streaming respons sekitar 5.000 token di UI | UI tidak macet | D-11, D-16, D-50 |
| 5 | PowerShell di akun non-admin dan PC kantor | Gagal dengan aman dan menampilkan pesan yang jelas | D-17 — **Lulus untuk akun non-admin**. PC kantor dan AppLocker belum teruji (lihat bagian 12) |
| 6 | Embedding pada 200 query campuran Indonesia–Inggris | Jawaban benar muncul di top-5 untuk minimal 80% query | D-14, D-26 — **Lulus** di Uji #6b dengan entri dwibahasa + Hybrid (lihat D-55 dan bagian 12) |
| 7 | Chromium dijalankan dari USB | Waktu start dan volume tulis tercatat | D-13 |
| 8 | Izin NTFS lintas 2–3 PC dan akun | Tidak ada error permission | D-04 |
| 9 | Identifikasi PC, termasuk skenario ganti komponen | PC dikenali dengan benar | D-31 |

Jika ada uji yang gagal, keputusan terkait direvisi sebelum MVP dibangun.

### Pengingat
Sebelum dipublikasikan luas, cek merek "Nibras" di PDKI untuk kelas 9 dan 42.

---

## 11. Risiko yang Masih Perlu Diuji (di luar Fase 0)

- Perilaku USB lain, terutama USB murah. Uji #1 hanya mencakup satu model USB dan satu PC.
- Wear USB akibat profil browser dan cache.
- Jejak yang tertinggal di PC host (Prefetch, jump list, riwayat USB, cache Qt dan Python). Jejak ini tidak dapat dijamin hilang sepenuhnya.
- ExecutionPolicy dan AppLocker di PC kantor.
- Waktu memuat vektor dari USB pada data yang besar.
- Kualitas tampilan tabel lebar, code block panjang, dan teks non-Latin di `QTextBrowser`.

---

## 12. Temuan dan Keputusan dari Hasil Fase 0

### Uji #1: Ketahanan SQLite saat USB dicabut (LULUS)
- **Hasil:** 20/20 PASS di NTFS dengan USB SanDisk 3.2 Gen1, Windows 11 Pro, SQLite 3.50.4. Total 25.403 transaksi.
- **Tidak ada** kegagalan `integrity_check`, ketidaksamaan `MAX(seq)` antar-database, celah urutan, atau checksum rusak.
- **Satu** transaksi yang sudah di-commit hilang (Run 08).
- **Temuan penting:** dengan `synchronous=FULL`, commit baru dianggap berhasil setelah Windows menyatakan data tersimpan permanen. Hilangnya transaksi berarti **controller USB melaporkan data sudah tersimpan padahal masih berada di cache-nya.** Ini perilaku hardware. Konsekuensinya, **commit terakhir yang sudah "berhasil" tetap bisa hilang** jika USB dicabut.
- Laporan lengkap: `results/uji01-sqlite-usb.md`.

| ID | Keputusan | Status |
|---|---|---|
| D-54 | **Intent log untuk tindakan non-idempotent.** (1) Sebelum eksekusi, catat status `pending` lalu commit. (2) Jalankan tindakan. (3) Catat status `done`. (4) Saat recovery, tindakan yang masih berstatus `pending` **tidak pernah diulang otomatis**. Tindakan tersebut ditampilkan sebagai tugas *interrupted*, dan pengguna diminta memverifikasi. Memperkuat D-08 dan D-21 | Disetujui |

### Uji #6: Kualitas embedding lokal (BELUM LULUS)
- **Hasil:** Recall@5 vektor int8 **60,5%** (target 80%). fp32 62,5%, FTS5 29,0%, Hybrid RRF 46,0%. Lisensi model (MIT) terverifikasi. Performa baik: indexing 10.000 entri sintetis (untuk uji performa) 4,3 menit, dan median query 26 ms di Intel i5-4460.
- **Kelemahan model yang nyata:** bias bahasa ketika query Indonesia mencari entri berbahasa Inggris (Recall@5 hanya 33,3%). Model cenderung memilih entri yang bahasanya sama dengan query.
- **Kelemahan dataset:** query dibuat terlalu adversarial. Sebanyak 92,5% query `id-id` sama sekali tidak berbagi kata dengan jawabannya, dan sebagian memakai parafrase yang tidak natural. Persona juga ambigu, karena ada entri tentang "Dimas" dan ada entri tentang "the user". Hybrid dirugikan oleh FTS5 tanpa penghapusan stopword. Karena itu hasilnya kemungkinan **di bawah** performa nyata, tetapi belum cukup untuk memutuskan.
- **Tindak lanjut:** Uji #6b dengan query natural, perbandingan `e5-small` dan `e5-base`, mitigasi entri dwibahasa, dan Hybrid yang adil. Kriteria keputusan ditetapkan di brief sebelum uji dijalankan.
- Laporan lengkap: `results/uji06-embedding.md`.

### Uji #6b: Evaluasi lanjutan embedding dan mitigasi (LULUS)
- **Hasil:** 24 run nyata (model `S`=e5-small / `B`=e5-base int8 × entri `mono`/`bi` × pencarian `vec`/`hyb1`/`hyb05`, pada query v1 adversarial dan v2 natural). Konfigurasi terbaik yang memakai `e5-small`: `S_bi_hyb05` Recall@5 **94,0%** pada v2 (`id-en` 96,7%) — memenuhi kriteria Prioritas 1 brief (≥80% total dan ≥70% `id-en`), ditetapkan sebelum uji dijalankan.
- **Penyebab kegagalan Uji #6 terkonfirmasi tercampur:** menyimpan entri dalam dua bahasa (teks asli + terjemahan, skor = maksimum kedua vektor) menaikkan Recall@5 v2 sekitar 12–19 poin dibanding teks tunggal, terutama tipe `id-en` (36,7–66,7% → 93,3–100%). Jadi bias bahasa Uji #6 bisa dimitigasi tanpa mengganti model.
- **`multilingual-e5-base` tidak diperlukan:** sedikit lebih akurat (95,5% vs 94,0%) tetapi ~2,4× lebih besar di disk, ~2× lebih lambat indexing/query, dan ~1,5× lebih banyak RAM. Karena `e5-small` sudah memenuhi kriteria Prioritas 1, upgrade ini menambah biaya tanpa kebutuhan nyata di USB non-admin.
- **Kegagalan yang tersisa** (9/200 query pada konfigurasi terbaik) murni kelemahan model, bukan artefak dataset: query semantik murni tanpa kata bersama, atau kata isi umum yang menjadi distraktor leksikal antar-entri tentang entitas yang sama.
- Menghasilkan D-55 (entri dwibahasa + Hybrid bobot FTS5 0,5 tetap).
- Laporan lengkap: `results/uji06b-embedding.md`.

### Uji #5: PowerShell di akun non-admin (LULUS untuk non-admin)
- **Hasil:** di Windows 11 Pro dengan PowerShell 5.1 dan akun non-admin, semua mode yang bisa disimulasikan gagal dengan aman dan menampilkan pesan yang jelas. Mode yang diuji: ExecutionPolicy `Restricted`, timeout, `powershell.exe` tidak ada di `PATH`, dan Constrained Language Mode di dalam sesi. Tidak ada crash tanpa pesan dan tidak ada data rusak. ExecutionPolicy dikembalikan ke semula, dan ini terverifikasi.
- **Temuan penting:** `Restricted` hanya memblokir file `.ps1`, sedangkan `-Command` inline tetap berjalan. Temuan ini menjadi dasar D-56.
- **Temuan teknis:** Windows mencari executable memakai `PATH` proses induk, bukan `PATH` yang diberikan ke proses anak. Karena itu, keberadaan `powershell.exe` harus dicek lebih dulu (preflight) supaya kondisi "tidak ditemukan" terdeteksi dengan benar.
- **Rekomendasi implementasi:** timeout 15 detik. Startup normal hanya 0,23–0,38 detik, tetapi angka ini belum divalidasi di PC yang lambat.
- **Belum teruji (risiko terbuka):** AppLocker/SRP yang memblokir `powershell.exe`, CLM tingkat sistem (WDAC/AppLocker), dan PC kantor/terkelola. Pemetaan error untuk AppLocker sudah ada di wrapper, tetapi belum pernah benar-benar terpicu.
- Laporan lengkap: `results/uji05-powershell.md`.

---

## Aturan Perubahan Dokumen

1. Keputusan baru diberi ID berikutnya (D-55, dan seterusnya).
2. Keputusan yang direvisi **tidak dihapus**. Tandai sebagai *superseded oleh D-xx*, lalu tambahkan keputusan baru.
3. Agen coding **tidak boleh** mengubah dokumen ini. Perubahan dilakukan melalui proses desain dan review.
