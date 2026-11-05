# Brief Tugas — Fase 0, Uji #9: Identifikasi PC

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md` (D-31 dan Rincian D-31)
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.
**Dijalankan di:** 2–3 PC Windows fisik (dan skenario ganti komponen jika operator memungkinkan), lewat sesi Claude Code lokal operator.

---

## 1. Tujuan

D-31 menetapkan PC dikenali lewat fingerprint gabungan berbobot dari `MachineGuid`, nama komputer, serial BIOS/motherboard, serial disk sistem, dan alamat MAC. Uji ini memvalidasi bahwa skema bobot ini benar-benar mengenali PC yang sama secara konsisten, membedakan PC yang berbeda, dan tetap mengenali PC yang sama meski satu-dua komponen diganti (skenario realistis: ganti disk, upgrade network adapter, dll).

Pertanyaan yang dijawab:
1. Skor fingerprint berapa yang membedakan "PC yang sama" dari "PC yang berbeda" secara andal, di data nyata (bukan asumsi)?
2. Jika satu komponen diganti (misalnya disk sistem), apakah skor fingerprint PC yang sama masih di atas ambang "dikenali otomatis", atau jatuh ke zona "ragu-ragu" (sesuai desain D-31, sistem lalu bertanya ke pengguna)?
3. Apakah ada komponen fingerprint yang ternyata **tidak stabil** antar-boot pada PC yang sama (berubah tanpa ada perubahan hardware), yang akan merusak akurasi?

## 2. Keamanan Data — WAJIB dibaca sebelum mulai

**Repo ini publik.** `MachineGuid`, serial BIOS/motherboard/disk, dan alamat MAC adalah identifier yang bisa dipakai melacak perangkat fisik seseorang. **Dilarang keras** meng-commit nilai asli apa pun dari kelima komponen ini ke git, dalam bentuk apa pun — termasuk di dalam file hasil uji, log, screenshot, atau pesan commit.

**Wajib diterapkan di seluruh kode dan laporan uji ini:**
- Setiap komponen fingerprint **disamarkan** sebelum disimpan ke file apa pun yang akan di-commit: hash satu arah dengan salt acak per sesi uji (`hashlib.sha256(salt + nilai_asli)`), lalu hanya **8 karakter pertama** hash yang dicatat. Ini cukup untuk membandingkan "apakah sama atau beda" antar-run tanpa membocorkan nilai asli.
- **Satu salt untuk seluruh kampanye uji, dipakai di SEMUA PC.** Kalau tiap PC memakai salt sendiri, hash komponen yang sama akan terlihat berbeda antar-PC, dan uji "PC berbeda" lulus tanpa makna. Salt dibuat sekali (minimal 32 byte acak dari `secrets.token_hex`), lalu disimpan di file lokal `spikes/uji09-pc-id/.salt` yang masuk `.gitignore`. Salt dipindahkan ke PC lain secara manual oleh operator.
- **Salt tidak boleh di-commit atau dicetak ke log.** Alamat MAC hanya punya sekitar 24 bit acak setelah prefiks vendor, jadi kalau salt-nya publik, hash MAC bisa ditebak dengan brute force. Laporan cukup mencatat 8 karakter pertama dari `sha256(salt)` sebagai bukti bahwa semua PC memakai salt yang sama.
- Nama PC (hostname) juga disamarkan jika mengandung nama orang atau instansi — ganti dengan label generik (`PC-A`, `PC-B`, `PC-C`) di laporan, dan catat pemetaan label ini **hanya** di file lokal yang **tidak** di-commit (tambahkan ke `.gitignore`).
- Review manual wajib dilakukan terhadap seluruh file di `results/uji09-raw/` sebelum commit, untuk memastikan tidak ada nilai mentah yang lolos.

## 3. Ruang Lingkup

**Termasuk:** script pengambil fingerprint (dengan penyamaran bawaan, bukan tambahan belakangan), implementasi skema bobot D-31, simulator skenario ganti komponen, panduan prosedur.

**Tidak termasuk:** UI permintaan konfirmasi ke pengguna (skenario "ragu-ragu bertanya ke pengguna" cukup dilaporkan sebagai rentang skor, implementasi UI itu scope produksi).

## 4. Keputusan Desain yang WAJIB Diikuti

- Lima komponen fingerprint: `MachineGuid` (registry `HKLM\SOFTWARE\Microsoft\Cryptography`), nama komputer, serial BIOS/motherboard (WMI `Win32_BIOS`/`Win32_BaseBoard`), serial disk sistem (WMI `Win32_DiskDrive` untuk disk yang memuat partisi sistem), alamat MAC (adapter fisik, bukan virtual/VPN).
- Skema skor: **gabungan berbobot** — brief ini **tidak** menetapkan bobot pasti (belum ada di `decisions.md`), jadi agen coding **mengusulkan** bobot awal berdasarkan stabilitas tiap komponen yang diamati di bagian 6, lalu melaporkannya sebagai rekomendasi (keputusan bobot final tetap lewat review, bukan ditetapkan sepihak oleh agen).

## 5. Larangan (Jangan Dilakukan)

- ❌ Jangan commit nilai asli `MachineGuid`, serial, atau MAC dalam bentuk apa pun (lihat bagian 2 — ini larangan paling kritis di brief ini).
- ❌ Jangan mengubah/menulis registry atau WMI apa pun — uji ini hanya **membaca** fingerprint, tidak pernah menulis.
- ❌ Jangan memerlukan hak admin untuk membaca kelima komponen (jika salah satu komponen butuh admin untuk dibaca di non-admin, itu temuan penting — laporkan, jangan dipaksa jalan dengan elevasi).
- ❌ Jangan menebak skor ambang batas. Ambang batas yang diusulkan harus berdasarkan data nyata dari bagian 6, bukan angka bulat yang terasa masuk akal.

## 6. Prosedur Uji (oleh operator manusia)

1. **Stabilitas antar-boot:** di satu PC, ambil fingerprint, restart PC, ambil fingerprint lagi. Ulangi 3 kali. Catat komponen mana yang stabil (identik) dan mana yang berubah.
2. **Beda PC:** ambil fingerprint di 2–3 PC berbeda (sesuai kriteria Fase 0), hitung skor kemiripan antar-PC yang berbeda ini (seharusnya rendah).
3. **PC sama, waktu berbeda:** ambil fingerprint PC yang sama di dua waktu berjauhan (misalnya hari berbeda), untuk menguji stabilitas jangka lebih panjang dibanding langkah 1.
4. **Skenario ganti komponen** (jika operator memungkinkan secara fisik — **tidak wajib** merusak/membongkar PC produksi, boleh memakai mesin virtual sebagai pendekatan jika penggantian hardware fisik tidak praktis, catat jika memakai pendekatan ini):
   - Simulasikan "ganti disk sistem" (misalnya jalankan dari VM dengan virtual disk berbeda, atau PC dengan disk yang benar-benar diganti jika tersedia).
   - Simulasikan "ganti network adapter" (pasang/lepas USB-to-Ethernet, atau nonaktifkan adapter lama dan pakai yang baru) — ini mengubah MAC.
   - Catat skor kemiripan PC yang sama, dengan satu komponen berubah, dibanding baseline langkah 1.
5. Untuk tiap langkah di atas, catat skor mentah **dan** hasil klasifikasi (dikenali otomatis / ragu-ragu / tidak dikenali) menurut bobot yang diusulkan di bagian 4.

## 7. Kriteria Lulus

Kriteria Fase 0: *"PC dikenali dengan benar"* (`decisions.md` bagian 10), termasuk skenario ganti komponen. Secara konkret:

| Kriteria | Target | Sifat |
|---|---|---|
| PC yang sama (langkah 1–3) dikenali sebagai PC yang sama | Skor di atas ambang "dikenali otomatis" pada semua run | **Wajib** |
| PC yang berbeda (langkah 2) tidak salah dikenali sebagai PC yang sama | Skor di bawah ambang "dikenali otomatis" pada semua pasangan | **Wajib** |
| PC yang sama dengan satu komponen diganti (langkah 4) tidak jatuh ke "tidak dikenali" (boleh jatuh ke "ragu-ragu", itu sesuai desain) | 0 kejadian jatuh ke "tidak dikenali" untuk pergantian **satu** komponen | **Wajib** |
| Tidak ada nilai mentah bocor ke file yang akan di-commit | 0 kejadian, diverifikasi manual sebelum commit | **Wajib mutlak** |

## 8. Deliverable

```
spikes/uji09-pc-id/
├── fingerprint_probe.py    baca 5 komponen + penyamaran bawaan
├── scoring.py               skema bobot + klasifikasi (otomatis/ragu-ragu/tidak dikenali)
└── README.md
results/
├── uji09-pc-identifikasi.md
└── uji09-raw/                hash tersamar saja, direview manual sebelum commit (lihat bagian 2)
```

Isi `results/uji09-pc-identifikasi.md`:
1. **Lingkungan:** daftar PC berlabel generik (`PC-A`, dst — lihat bagian 2), spesifikasi ringkas yang tidak mengidentifikasi individu.
2. **Stabilitas antar-boot** per komponen (bagian 6 langkah 1).
3. **Tabel skor** PC sama vs PC berbeda vs PC sama dengan komponen diganti.
4. **Bobot yang diusulkan**, beserta alasan berdasarkan data stabilitas.
5. **Ambang batas yang diusulkan** untuk "dikenali otomatis" vs "ragu-ragu" vs "tidak dikenali".
6. **Konfirmasi tertulis** bahwa seluruh file di `results/uji09-raw/` sudah direview manual dan tidak memuat nilai mentah (lihat bagian 2).

## 9. Definisi Selesai

- Penyamaran (hashing + salt) diterapkan **sejak awal** di kode pengambilan fingerprint, bukan ditambahkan belakangan.
- Review manual anti-kebocoran data sensitif (bagian 2) benar-benar dilakukan sebelum setiap commit, dan dikonfirmasi di laporan.
- Minimal 2 PC berbeda diuji, dan minimal satu skenario ganti komponen (fisik atau VM) dicoba.
- Kode dikerjakan di branch `fase0/uji09`, lalu dibuka pull request ke `main`.
