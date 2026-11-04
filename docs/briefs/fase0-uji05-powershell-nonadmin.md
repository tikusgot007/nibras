# Brief Tugas — Fase 0, Uji #5: PowerShell di Akun Non-Admin dan PC Kantor

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md` (D-17)
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.
**Dijalankan di:** PC Windows fisik (sesi Claude Code lokal operator), idealnya termasuk satu PC kantor/terkelola jika operator punya akses ke salah satu.

---

## 1. Tujuan

D-17 menetapkan Nibras memanggil PowerShell 5.1 bawaan OS (dengan `-NoProfile`) untuk sebagian fungsi (misalnya skill tertentu, deteksi info sistem). Di akun non-admin, dan terutama di PC kantor yang diatur Group Policy/AppLocker/ExecutionPolicy restriktif, pemanggilan ini bisa gagal. Uji ini memastikan kegagalan tersebut **selalu gagal dengan aman** (tidak membuat data korup atau aplikasi crash tanpa pesan) dan menampilkan pesan yang jelas ke pengguna — bukan untuk membuat PowerShell selalu berhasil.

Pertanyaan yang dijawab:
1. Apa saja mode kegagalan PowerShell yang mungkin terjadi di non-admin dan PC terkelola (ExecutionPolicy `Restricted`, AppLocker memblokir `powershell.exe`, Constrained Language Mode, dll)?
2. Apakah panggilan dari Python (`subprocess`) bisa membedakan tiap mode kegagalan itu (lewat exit code, stderr, atau timeout), atau semuanya terlihat sama dari luar?
3. Apakah Nibras bisa mendeteksi kegagalan ini **sebelum** mencoba (preflight check) agar tidak selalu menunggu timeout?

## 2. Ruang Lingkup

**Termasuk:** wrapper pemanggilan PowerShell minimal yang meniru pola pemanggilan skill Nibras, skrip simulasi tiap mode kegagalan, panduan prosedur.

**Tidak termasuk:** skill nyata apa pun (deteksi PC, dll — itu scope Uji #9 dan implementasi produksi). Uji ini hanya memanggil PowerShell dengan command no-op (misalnya `Write-Output "ok"`) untuk mengisolasi masalah pemanggilan dari logika skill.

## 3. Keputusan Desain yang WAJIB Diikuti

- Panggil `powershell.exe -NoProfile -NonInteractive -Command <script>` (D-17) — bukan `powershell.exe -File`, dan jangan ubah jadi `pwsh` (PowerShell Core) karena D-17 menetapkan **PowerShell 5.1 bawaan OS**.
- Panggilan dari Python memakai `subprocess.run` dengan `timeout` eksplisit (tentukan nilainya sendiri berdasarkan hasil uji, catat alasannya).

## 4. Larangan (Jangan Dilakukan)

- ❌ Jangan mengubah ExecutionPolicy, AppLocker, atau Group Policy PC kantor untuk "membuat lulus". Catat kegagalan apa adanya.
- ❌ Jangan menaikkan privilege (UAC prompt, `RunAs`) untuk mengakali non-admin — Nibras **wajib** berjalan tanpa hak admin (AGENTS.md).
- ❌ Jangan membuat wrapper yang menyembunyikan error asli dari PowerShell — pesan error asli harus tetap tersedia untuk logging, meski pesan ke pengguna disederhanakan.
- ❌ Jangan menebak mode kegagalan. Setiap mode di bagian 5 harus benar-benar dipicu dan diamati.

## 5. Mode Kegagalan yang Disimulasikan

Simulasikan tiap mode berikut (di akun non-admin pada PC yang operator kendalikan sendiri — **jangan** mengubah setting PC kantor orang lain, lihat bagian 6 untuk itu):

| Mode | Cara simulasi |
|---|---|
| ExecutionPolicy `Restricted` | `Set-ExecutionPolicy Restricted -Scope CurrentUser` (dari akun yang sama, tidak perlu admin untuk scope `CurrentUser`) |
| `powershell.exe` diblokir AppLocker/Software Restriction Policy | Jika operator punya PC dengan ini aktif, uji langsung. Jika tidak, catat sebagai **tidak teruji di lingkungan ini** — jangan simulasikan dengan cara yang tidak representatif |
| Timeout (PowerShell hang atau sangat lambat start, misal karena profile berat — meski kita pakai `-NoProfile`) | Picu dengan command yang sengaja lama (`Start-Sleep -Seconds 30`) untuk menguji jalur timeout wrapper, bukan untuk menguji PowerShell itu sendiri |
| `powershell.exe` tidak ditemukan di `PATH` | Jalankan dengan `PATH` yang dimodifikasi sementara di proses uji (tidak mengubah `PATH` sistem) |
| Constrained Language Mode | Jika tersedia untuk disimulasikan tanpa mengubah kebijakan sistem secara permanen, catat caranya; jika tidak bisa disimulasikan aman, catat sebagai **tidak teruji**, jangan dipaksakan |

## 6. Prosedur Uji (oleh operator manusia)

1. Untuk setiap mode di bagian 5 yang bisa disimulasikan di PC operator sendiri: jalankan wrapper, catat exit code, stderr, durasi, dan apakah wrapper berhasil mengklasifikasikan jenis kegagalannya dengan benar.
2. **Jika operator punya akses ke PC kantor/terkelola** (dengan izin memakainya untuk uji, bukan mengubah kebijakannya): jalankan wrapper apa adanya di sana (tanpa mengubah setting apa pun di PC itu), catat hasil nyata. Ini data paling berharga karena mewakili kondisi dunia nyata yang tidak bisa disimulasikan penuh di PC pribadi.
3. Setelah selesai menyimulasikan ExecutionPolicy `Restricted` di langkah 1, **kembalikan** `Set-ExecutionPolicy` ke nilai semula di akun uji.

## 7. Kriteria Lulus

Kriteria Fase 0: *"Gagal dengan aman dan menampilkan pesan yang jelas"* (`decisions.md` bagian 10). Secara konkret:

| Kriteria | Target | Sifat |
|---|---|---|
| Tidak ada crash tanpa pesan (unhandled exception sampai ke UI/pengguna) pada semua mode yang diuji | 0 kejadian | **Wajib** |
| Tidak ada data korup atau state aplikasi rusak akibat kegagalan PowerShell | 0 kejadian | **Wajib** |
| Wrapper mengklasifikasikan jenis kegagalan dan menghasilkan pesan yang bisa ditampilkan ke pengguna (bukan stack trace mentah) | Untuk setiap mode yang **bisa** dibedakan dari luar (lihat pertanyaan 2 di bagian 1) | **Wajib** |
| Mode yang tidak bisa dibedakan dari luar (misalnya semua terlihat sebagai timeout generik) | Dicatat sebagai keterbatasan, bukan kegagalan uji | Informasi |

## 8. Deliverable

```
spikes/uji05-powershell/
├── ps_wrapper.py        wrapper pemanggilan + klasifikasi kegagalan
├── simulate_modes.ps1    skrip bantu untuk memicu tiap mode di bagian 5
└── README.md
results/
└── uji05-powershell.md
```

Isi `results/uji05-powershell.md`:
1. **Lingkungan:** OS, versi PowerShell, apakah PC kantor/terkelola tersedia untuk diuji (dan jenis kebijakannya jika diketahui, tanpa membocorkan info sensitif institusi).
2. **Tabel hasil** per mode kegagalan: exit code, stderr (ringkas), durasi, klasifikasi wrapper, pesan yang ditampilkan ke pengguna.
3. **Mode yang tidak teruji** dan alasannya.
4. **Rekomendasi** nilai timeout dan pesan pengguna untuk implementasi produksi.

## 9. Definisi Selesai

- Semua mode yang bisa disimulasikan aman di bagian 5 benar-benar dipicu dan diamati.
- ExecutionPolicy dikembalikan ke semula setelah uji.
- Tidak ada perubahan kebijakan permanen di PC kantor/terkelola mana pun.
- Kode dikerjakan di branch `fase0/uji05`, lalu dibuka pull request ke `main`.
