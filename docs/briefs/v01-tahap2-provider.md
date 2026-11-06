# Brief Tugas — v0.1 Tahap 2: Provider Lengkap dan Fallback

**Proyek:** Nibras (asisten AI pribadi yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md`, terutama D-11, D-15, D-21, D-41, D-42, D-46, D-59, D-63, D-64
**Melanjutkan:** Tahap 1 (PR #9). Kode di `src/nibras/` dipakai dan diperluas.
**Tingkat:** kode aplikasi.
**Dijalankan di:** PC Windows pengembang (sesi agen lokal), dengan flashdisk NTFS untuk uji penerimaan.

> Sesuai **D-63**, tahap ini **tidak** membuat pemantauan biaya, token, atau budget.

---

## 1. Tujuan

Di akhir tahap ini, pengguna bisa menyimpan beberapa provider (OpenAI, Anthropic, dan OpenAI-compatible), memilih satu model aktif untuk seluruh aplikasi, dan menetapkan satu model cadangan. Kalau provider aktif gagal, aplikasi menawarkan cadangan lewat kartu persetujuan (D-64).

## 2. Ruang Lingkup

**Termasuk:**
1. **Profil provider.** Pengguna bisa menyimpan beberapa profil. Setiap profil punya jenis (`openai`, `anthropic`, `openai_compatible`), nama tampilan, `base_url` (hanya untuk `openai_compatible`), dan API key sendiri di vault. Setiap profil punya daftar model yang diisi pengguna: nama model, context window, dan kemampuan (streaming, tool calling, vision).
2. **Adapter baru:** `openai` (SDK `openai` dengan endpoint resmi) dan `anthropic` (SDK `anthropic`). Keduanya memakai antarmuka `ProviderAdapter` dan format pesan kanonik dari Tahap 1 (D-15).
3. **Satu model global aktif.** Pengguna memilihnya dari daftar model di semua profil. Tidak ada routing otomatis.
4. **Fallback dengan persetujuan** (D-64), berlaku satu pesan sekali.
5. **Status bar** (D-42 tanpa butir biaya, D-63): model aktif beserta nama profilnya, status provider, status vault beserta sisa waktu auto-lock, dan status online/offline. PC Profile ditambahkan di Tahap 5.
6. **Dashboard** sebagai mode tersendiri (D-41, D-46). Untuk tahap ini hanya bagian **Provider & Model** dan **Settings**. Bagian lain dikerjakan di Tahap 3–5.
7. **Migrasi data Tahap 1.** Pengaturan `provider.*` lama dan `api_key` di vault dipindahkan otomatis ke satu profil `openai_compatible`, yang lalu menjadi model aktif. Data lama tidak hilang. Sebelum dimigrasi, vault dan `core.db` di-backup lebih dulu ke `Backups/`.
8. **Tindak lanjut Tahap 1:**
   - Aplikasi mencatat event startup dan shutdown ke `Data/logs/nibras.log`, tanpa data rahasia dan tanpa URL request.
   - Penyebab balasan berstatus `failed` di uji Tahap 1 diselidiki dari log yang ada. Kalau tidak bisa ditemukan, laporkan apa adanya, lalu pastikan error berikutnya tercatat dengan cukup detail (tanpa API key dan tanpa URL).
   - Bagian atas `results/v01-tahap1-penerimaan.md` yang usang diperbaiki ("hasil BELUM diisi", "48 test").
   - Pastikan instance kedua benar-benar memunculkan jendela pertama ke depan. Kalau Windows menolak fokus, tampilkan setidaknya taskbar yang berkedip, lalu catat perilakunya.

**Tidak termasuk** (jangan dibuat):
- Pemantauan token, biaya, harga, atau budget dalam bentuk apa pun (D-63).
- Memori, embedding, Context Builder berlapis (Tahap 3).
- Tools, Policy Engine, kartu persetujuan tindakan, anggaran per tugas (Tahap 4). Kartu fallback di tahap ini adalah kartu khusus, **bukan** sistem persetujuan umum.
- Project, persona, PC Profile, backup/restore umum, dan bagian dashboard lainnya (Tahap 5).
- Custom API Adapter (v0.3).

## 3. Keputusan Desain yang WAJIB Diikuti

Semua aturan di brief Tahap 1 bagian 3 tetap berlaku: tanpa WAL, semua data di flashdisk, tanpa admin, thread Core sesuai D-11, render bertahap, startup bertahap D-59, dan dependency terkunci D-61.

Tambahan untuk tahap ini:

| Aturan | Nilai |
|---|---|
| Impor SDK | Saat startup, hanya SDK provider **aktif** yang diimpor di latar belakang (D-59). SDK provider cadangan diimpor setelah fallback disetujui. Saat startup, jangan mengimpor `anthropic` kalau provider aktifnya bukan Anthropic |
| Fallback | Tidak pernah otomatis. Muncul hanya setelah retry D-21 habis, berlaku untuk satu pengiriman, dan pengiriman berikutnya kembali ke model aktif (D-64) |
| Penyimpanan | Profil dan model disimpan di `core.db`. API key per profil disimpan di vault. Skema dimigrasi dengan mekanisme versi skema dari Tahap 1 |
| Dependency | `anthropic` ditambahkan ke `requirements.in`, lalu `requirements.lock` dibuat ulang dengan hash (D-61) |

## 4. Larangan (Jangan Dilakukan)

- ❌ Semua larangan di brief Tahap 1 bagian 4 tetap berlaku.
- ❌ Jangan berpindah provider secara otomatis.
- ❌ Jangan membuat penghitung token, biaya, harga, atau budget (D-63).
- ❌ Jangan memanggil API sungguhan di test. Gunakan server tiruan lokal untuk format OpenAI dan Anthropic, termasuk streaming.
- ❌ Jangan menghapus data Tahap 1 saat migrasi.
- ❌ Jangan menampilkan atau mencatat API key, termasuk di dashboard. Tampilkan hanya status "tersimpan" atau "kosong".
- ❌ Jangan menulis URL atau nama model milik pengguna di kode, test, atau dokumentasi (repo publik).
- ❌ Jangan mengubah `docs/decisions.md` dan `docs/briefs/`. Kalau ada konflik atau ambiguitas, berhenti dan tanyakan.

## 5. Uji

### 5.1 Unit dan integrasi (`pytest`)
Minimal mencakup:
- Adapter `openai` dan `anthropic` melawan server tiruan: streaming, retry hanya sebelum token pertama (D-21), dan error dipetakan ke pesan yang jelas.
- Pergantian model aktif antar-profil dan antar-jenis provider.
- Fallback: kartu muncul hanya setelah retry habis, persetujuan berlaku untuk satu pengiriman, pengiriman berikutnya kembali ke model aktif, dan penolakan meninggalkan pesan berstatus `failed`.
- Migrasi Tahap 1 ke profil: pengaturan dan API key lama berpindah, lalu backup dibuat lebih dulu.
- Test integrasi `AgentCore` sungguhan untuk alur kirim pesan dengan model aktif dan dengan fallback yang disetujui.
- `anthropic` tidak diimpor saat startup kalau provider aktifnya bukan Anthropic.

### 5.2 Uji penerimaan (operator, di flashdisk NTFS)
Agen menulis checklist di `results/v01-tahap2-penerimaan.md`, lalu operator mengisi hasilnya. Minimal:
1. Data Tahap 1 termigrasi: riwayat chat masih ada, dan profil OpenAI-compatible lama langsung bisa dipakai tanpa mengisi ulang.
2. Tambah profil atau model kedua, lalu pindah model aktif. Status bar ikut berubah.
3. Fallback: isi `base_url` yang salah pada model aktif. Setelah retry habis, kartu fallback muncul. Setujui satu kali, lalu pastikan pengiriman berikutnya kembali ke model aktif dan kartu muncul lagi.
4. Tolak fallback: pesan ditandai gagal dan bisa dicoba lagi.
5. Startup cold start: catat **terpisah** waktu sampai jendela tampil, waktu sampai passphrase selesai diketik, dan waktu sampai provider siap.
6. Log `Data/logs/nibras.log` berisi event startup dan shutdown, tanpa API key dan tanpa URL request.
7. Instance kedua: catat apakah jendela pertama naik ke depan.

Adapter yang tidak punya API key sungguhan (misalnya pengguna tidak punya akun OpenAI resmi atau Anthropic) cukup diuji dengan server tiruan, dan dicatat di laporan sebagai "tidak diuji dengan API asli".

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
