# Brief Tugas — v0.1 Tahap 2: Provider Lengkap dan Biaya

**Proyek:** Nibras (asisten AI pribadi yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md`, terutama D-11, D-15, D-21, D-41, D-42, D-46, D-59, D-63–D-66, dan bagian 7 (v0.1: Provider dan Biaya)
**Melanjutkan:** Tahap 1 (PR #9). Kode di `src/nibras/` dipakai dan diperluas.
**Tingkat:** kode aplikasi.
**Dijalankan di:** PC Windows pengembang (sesi agen lokal), dengan flashdisk NTFS untuk uji penerimaan.

---

## 1. Tujuan

Di akhir tahap ini, pengguna bisa menyimpan beberapa provider (OpenAI, Anthropic, dan OpenAI-compatible), memilih satu model aktif, dan melihat berapa token dan biaya yang sudah dipakai. Budget harian dan bulanan bisa diatur, dengan tiga mode batas. Kalau provider aktif gagal, aplikasi menawarkan fallback yang harus disetujui pengguna.

## 2. Ruang Lingkup

**Termasuk:**
1. **Profil provider.** Pengguna bisa menyimpan beberapa profil. Setiap profil punya jenis (`openai`, `anthropic`, `openai_compatible`), nama tampilan, `base_url` (hanya untuk `openai_compatible`), dan API key sendiri di vault. Setiap profil punya daftar model yang diisi pengguna: nama model, context window, harga input dan output per 1 juta token (D-63), serta kemampuan model (streaming, tool calling, vision).
2. **Adapter baru:** `openai` (SDK `openai`, tanpa `base_url` khusus) dan `anthropic` (SDK `anthropic`). Keduanya memakai antarmuka `ProviderAdapter` dan format pesan kanonik dari Tahap 1 (D-15).
3. **Satu model global aktif** untuk seluruh aplikasi (bagian 1 `decisions.md`). Tidak ada routing otomatis.
4. **Token tracking** dan perkiraan biaya per respons (D-64).
5. **Budget** harian dan bulanan dengan mode Hard Stop, Ask Permission, dan Soft Limit (D-65).
6. **Fallback dengan persetujuan** (D-66).
7. **Status bar lengkap** untuk tahap ini (D-42): model aktif, status provider, biaya hari ini dibanding budget, status vault beserta sisa waktu auto-lock, dan status online/offline. PC Profile ditambahkan di Tahap 5.
8. **Dashboard** sebagai mode tersendiri (D-41, D-46), untuk tahap ini hanya bagian **Provider & Model**, **Budget & Usage**, dan **Settings**. Bagian lain dikerjakan di Tahap 3–5.
9. **Migrasi data Tahap 1:** pengaturan `provider.*` lama dan `api_key` di vault dipindahkan otomatis ke satu profil `openai_compatible`. Data lama tidak hilang. Vault di-backup lebih dulu ke `Backups/` sebelum dimigrasi.
10. **Tindak lanjut Tahap 1:**
    - Aplikasi mencatat event startup dan shutdown ke `Data/logs/nibras.log` tanpa data rahasia.
    - Penyebab balasan berstatus `failed` di uji Tahap 1 diselidiki dari log yang ada. Kalau penyebabnya tidak bisa ditemukan, laporkan apa adanya, lalu pastikan error berikutnya tercatat dengan cukup detail (tanpa API key dan tanpa URL request).
    - Bagian atas `results/v01-tahap1-penerimaan.md` yang sudah usang diperbaiki ("hasil BELUM diisi", "48 test").

**Tidak termasuk** (jangan dibuat):
- Memori, embedding, Context Builder berlapis (Tahap 3).
- Tools, Policy Engine, kartu persetujuan tindakan (Tahap 4). Kartu fallback dan kartu budget di tahap ini adalah kartu khusus, **bukan** sistem persetujuan umum.
- Project, persona, PC Profile, backup/restore umum, dan bagian dashboard lainnya (Tahap 5).
- Pengambilan daftar harga dari internet.
- Custom API Adapter (v0.3).

## 3. Keputusan Desain yang WAJIB Diikuti

Semua aturan di brief Tahap 1 bagian 3 tetap berlaku (tanpa WAL, semua data di flashdisk, tanpa admin, D-11 thread Core, render bertahap, D-59 startup bertahap, dependency terkunci D-61).

Tambahan untuk tahap ini:

| Aturan | Nilai |
|---|---|
| Impor SDK | Hanya SDK provider **aktif** yang diimpor di latar belakang saat startup (D-59). SDK provider fallback diimpor saat fallback disetujui. Saat startup, jangan mengimpor `anthropic` kalau provider aktifnya bukan Anthropic |
| Harga | Diisi pengguna per model (D-63). Tidak ada harga bawaan di kode |
| Token | Diambil dari data `usage` yang dikirim provider. Kalau provider tidak mengirimnya, pakai perkiraan dan tandai sebagai perkiraan (D-64) |
| Budget | Dicek sebelum setiap pengiriman (D-65) |
| Fallback | Tidak pernah otomatis. Selalu lewat kartu persetujuan, dan hanya untuk satu pengiriman (D-66) |
| Penyimpanan | Profil, model, harga, dan budget disimpan di `core.db`. API key per profil disimpan di vault. Tabel `usage` disimpan di `core.db` |
| Dependency | `anthropic` ditambahkan ke `requirements.in`, dan `requirements.lock` dibuat ulang dengan hash (D-61) |

## 4. Larangan (Jangan Dilakukan)

- ❌ Semua larangan di brief Tahap 1 bagian 4 tetap berlaku.
- ❌ Jangan berpindah provider secara otomatis.
- ❌ Jangan menulis harga model apa pun di kode, test, atau dokumentasi sebagai nilai bawaan.
- ❌ Jangan memanggil API sungguhan di test. Gunakan server tiruan lokal untuk format OpenAI dan Anthropic, termasuk streaming dan data `usage`.
- ❌ Jangan mengirim pesan kalau budget Hard Stop sudah tercapai, termasuk lewat fallback.
- ❌ Jangan menghapus data Tahap 1 saat migrasi.
- ❌ Jangan menampilkan atau mencatat API key, termasuk di dashboard. Tampilkan hanya status "tersimpan" atau "kosong".
- ❌ Jangan mengubah `docs/decisions.md` dan `docs/briefs/`. Kalau ada konflik atau ambiguitas, berhenti dan tanyakan.

## 5. Uji

### 5.1 Unit dan integrasi (`pytest`)
Minimal mencakup:
- Adapter `openai` dan `anthropic` melawan server tiruan: streaming, `usage` dibaca dengan benar, retry hanya sebelum token pertama (D-21), dan error dipetakan ke pesan yang jelas.
- Provider yang tidak mengirim `usage`: token diperkirakan dan ditandai sebagai perkiraan.
- Perhitungan biaya dari `usage` dan harga per model.
- Budget: ketiga mode di batas harian dan bulanan, pergantian hari dan bulan memakai waktu lokal, serta aturan model tanpa harga (D-63).
- Fallback: kartu muncul hanya setelah retry habis, berlaku untuk satu pengiriman, budget tetap dicek, dan penolakan meninggalkan pesan berstatus `failed`.
- Migrasi Tahap 1 ke profil: pengaturan dan API key lama berpindah ke profil, dan vault di-backup lebih dulu.
- Test integrasi `AgentCore` sungguhan untuk alur kirim pesan dengan pencatatan `usage`.

### 5.2 Uji penerimaan (operator, di flashdisk NTFS)
Agen menulis checklist di `results/v01-tahap2-penerimaan.md`, lalu operator mengisi hasilnya. Minimal:
1. Data Tahap 1 termigrasi: riwayat chat masih ada, dan profil OpenAI-compatible lama langsung bisa dipakai.
2. Tambah profil kedua dan pindah model aktif. Status bar ikut berubah.
3. Isi harga model, kirim beberapa pesan, lalu cocokkan token dan biaya di dashboard dengan angka di dashboard provider, kalau tersedia.
4. Set budget harian kecil dengan mode **Hard Stop**: pengiriman diblokir dengan pesan yang jelas. Ulangi untuk **Ask Permission** (muncul kartu konfirmasi) dan **Soft Limit** (hanya peringatan).
5. Model aktif tanpa harga dengan budget aktif: aplikasi meminta harga diisi lebih dulu (D-63).
6. Fallback: matikan jaringan atau isi `base_url` yang salah. Setelah retry habis, kartu fallback muncul. Setujui satu kali, lalu pastikan pengiriman berikutnya kembali ke provider utama.
7. Startup cold start: catat **terpisah** waktu sampai jendela tampil, waktu sampai passphrase selesai diketik, dan waktu sampai provider siap.
8. Log `Data/logs/nibras.log` berisi event startup dan shutdown, tanpa API key dan tanpa URL request.

Adapter yang tidak punya API key sungguhan (misalnya pengguna tidak punya akun Anthropic) cukup diuji dengan server tiruan. Catat itu di laporan sebagai "tidak diuji dengan API asli".

## 6. Deliverable

```
src/nibras/                         kode yang diperluas (providers, core, storage, ui/dashboard)
packaging/requirements.in, .lock    + anthropic
tests/                              test baru dan test yang diperbarui
results/v01-tahap2-penerimaan.md    checklist dan hasil uji penerimaan
results/v01-tahap1-penerimaan.md    hanya bagian atas yang usang yang diperbaiki
README.md                           diperbarui
```

## 7. Definisi Selesai

- Semua test lulus di PC pengembang Windows. Output `pytest` dilampirkan di pull request.
- Bundle dan launcher dibuild di Windows dari `requirements.lock`.
- Checklist uji penerimaan diisi dengan hasil nyata. Butir yang gagal atau tidak diuji ditulis apa adanya.
- Kode dikerjakan di branch `v01/tahap2`, lalu dibuka pull request ke `main`. Gunakan commit kecil dan bertahap.
