# Brief Tugas — Fase 0, Uji #3: Antivirus dan SmartScreen terhadap Launcher

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md` (D-12)
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.
**Dijalankan di:** PC Windows fisik (sesi Claude Code lokal operator), bukan sesi cloud.

---

## 1. Tujuan

Launcher native kecil (D-12) akan dijalankan dari USB tanpa instalasi. Windows SmartScreen dan antivirus pihak ketiga cenderung mencurigai executable yang tidak dikenal dan tidak ditandatangani, berjalan dari removable drive. Uji ini mencatat blokir apa yang benar-benar terjadi dan solusi apa yang tersedia untuk tiap blokir — **bukan** untuk menghilangkan semua blokir sama sekali, karena sebagian memang di luar kendali kita (misalnya keputusan IT kantor).

Pertanyaan yang dijawab:
1. Apakah Windows Defender SmartScreen memblokir launcher saat pertama dijalankan dari USB?
2. Apakah Windows Defender (real-time protection) men-flag atau men-delay launcher atau bundle Python?
3. Apakah ada perbedaan perilaku antara akun admin dan non-admin?
4. Solusi apa yang tersedia untuk tiap blokir, dan mana yang realistis diterapkan Nibras (bukan solusi yang butuh beli sertifikat code-signing, karena itu di luar scope Fase 0)?

## 2. Ruang Lingkup

**Termasuk:** launcher uji minimal (lihat bagian 5), skenario build dengan dan tanpa tanda tangan self-signed, panduan prosedur, template laporan.

**Tidak termasuk:** UI chat, Agent Core, logika aplikasi apa pun. Launcher di sini **hanya** membuka file teks lalu keluar — cukup untuk memicu pemeriksaan OS/AV terhadap executable-nya.

## 3. Keputusan Desain yang WAJIB Diikuti

- Launcher tetap berupa executable native kecil (D-12) — bahasa implementasi belum diputuskan di `decisions.md`, jadi gunakan bahasa yang paling praktis untuk uji ini (misalnya C minimal yang dikompilasi, atau Rust), dan **catat pilihan beserta alasannya** di laporan. Ini bukan keputusan final bahasa launcher produksi.
- Launcher tidak boleh memerlukan instalasi apa pun di PC host.

## 4. Larangan (Jangan Dilakukan)

- ❌ Jangan menonaktifkan Windows Defender, SmartScreen, atau antivirus pihak ketiga untuk "membuat lulus". Catat blokir apa adanya.
- ❌ Jangan beli atau memakai sertifikat code-signing komersial untuk uji ini.
- ❌ Jangan memakai packer/obfuscator (UPX dan sejenisnya) — itu justru meningkatkan kecurigaan AV dan tidak relevan dengan tujuan Nibras.
- ❌ Jangan menebak hasil blokir. Semua catatan harus dari eksekusi nyata yang benar-benar dicoba.
- ❌ Jangan mengubah pendekatan packaging D-12 berdasarkan hasil uji ini tanpa review — brief ini hanya mengumpulkan data.

## 5. Skenario yang Diuji

Build tiga varian launcher minimal (source sama, hanya metadata/signing yang berbeda):

| Varian | Deskripsi |
|---|---|
| `unsigned` | Executable tanpa tanda tangan apa pun, tanpa metadata versi |
| `unsigned-metadata` | Sama seperti di atas, ditambah metadata versi/deskripsi/ikon (`FileDescription`, `ProductName`, dll via resource file) |
| `selfsigned` | Ditandatangani dengan sertifikat self-signed (dibuat sendiri dengan `New-SelfSignedCertificate` atau `signtool` + sertifikat test lokal) |

Untuk setiap varian, jalankan dari:
- USB, akun **admin**.
- USB, akun **non-admin** (standard user).
- Disalin ke disk internal, akun non-admin (sebagai pembanding — apakah lokasi USB sendiri yang memicu kecurigaan tambahan).

## 6. Prosedur Uji (oleh operator manusia)

Untuk setiap kombinasi varian × lokasi × akun di bagian 5:
1. Pastikan Windows Defender dalam kondisi default (real-time protection aktif, bukan dimatikan).
2. Jalankan launcher dengan **double-click** (bukan dari terminal, supaya SmartScreen "Open File - Security Warning" ikut teruji).
3. Catat: apakah muncul dialog SmartScreen "Windows protected your PC"? Apakah ada opsi "Run anyway"? Apakah Defender men-scan lebih dari beberapa detik (delay eksekusi) atau langsung men-quarantine/menghapus file?
4. Jika ada antivirus pihak ketiga terpasang (bukan cuma Defender), ulangi minimal untuk varian `unsigned` dan catat hasilnya terpisah, sebutkan nama dan versi produknya.
5. Untuk setiap blokir yang terjadi, catat langkah konkret yang berhasil membuatnya jalan (misalnya "Run anyway", "More info", unblock via file Properties, atau menambah exclusion) — ini jadi draft "solusi" di laporan.

## 7. Kriteria Lulus

Uji ini **tidak punya kriteria pass/fail numerik** — kriteria lulusnya adalah: *"Tercatat, dan ada solusi untuk setiap blokir"* (lihat tabel kriteria Fase 0 di `decisions.md` bagian 10). Artinya:
- Setiap blokir yang terjadi di bagian 6 **harus** punya solusi tercatat (meski solusinya "butuh klik Run anyway dan edukasi pengguna", itu valid sebagai solusi).
- Jika ada blokir yang **tidak ada solusi realistisnya** (misalnya di-quarantine permanen tanpa cara restore oleh pengguna biasa), itu dilaporkan sebagai risiko terbuka, bukan kriteria gagal — lanjutkan ke review desain.

## 8. Deliverable

```
spikes/uji03-antivirus/
├── launcher_src/        source minimal launcher + cara build tiap varian
├── README.md            cara build 3 varian, prosedur uji
results/
└── uji03-antivirus.md
```

**Jangan commit** file `.exe` hasil build atau sertifikat self-signed. Tambahkan ke `.gitignore`.

Isi `results/uji03-antivirus.md`:
1. **Lingkungan:** OS, versi Windows, status Windows Defender, antivirus pihak ketiga (jika ada) beserta versi.
2. **Tabel hasil** per varian × lokasi × akun: blokir apa yang terjadi, dan solusi apa yang berhasil.
3. **Risiko terbuka** (blokir tanpa solusi realistis), jika ada.
4. **Rekomendasi** untuk launcher produksi (misalnya perlu metadata versi minimal, perlu halaman onboarding yang menjelaskan "Run anyway").

## 9. Definisi Selesai

- Semua kombinasi di bagian 5 dan 6 benar-benar dicoba, tidak ada yang diasumsikan.
- Laporan berisi data nyata, bukan perkiraan.
- Kode dikerjakan di branch `fase0/uji03`, lalu dibuka pull request ke `main`.
