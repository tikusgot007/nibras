# Hasil Uji #5 — PowerShell di Akun Non-Admin dan PC Kantor

Semua angka berasal dari eksekusi nyata `spikes/uji05-powershell/simulate_modes.ps1` dan `ps_wrapper.py`.

## 1. Lingkungan
- OS: Windows 11 Pro 10.0.26100; Windows PowerShell 5.1.26100.3624; Python 3.14.7.
- Akun non-admin (diverifikasi: bukan anggota peran Administrator). PC tidak tergabung domain, tidak ada kebijakan AppLocker efektif (0 rule collection).
- **PC kantor/terkelola: tidak tersedia** pada uji ini.
- ExecutionPolicy awal: `CurrentUser = RemoteSigned`, scope lain `Undefined`.

## 2. Hasil per mode
| Mode | Exit code | stderr (ringkas) | Durasi | Klasifikasi wrapper | Pesan ke pengguna |
|---|---|---|---|---|---|
| Baseline (`Write-Output ok`) | 0 | kosong | 0,24 s | OK | - |
| ExecutionPolicy `Restricted`, command inline | 0 | kosong | 0,24 s | OK | - |
| ExecutionPolicy `Restricted`, menjalankan file `.ps1` | 1 | `running scripts is disabled on this system` (PSSecurityException) | 0,27 s | EXEC_POLICY | Kebijakan eksekusi skrip PowerShell di PC ini melarang skrip dijalankan. |
| Timeout (`Start-Sleep 30`, timeout 3 s) | - | kosong | 3,03 s | TIMEOUT | PowerShell tidak merespons tepat waktu. |
| `powershell.exe` tidak ada di `PATH` | - | `powershell.exe not found on PATH` (FileNotFoundError) | 0,00 s | NOT_FOUND | Windows PowerShell tidak ditemukan di PC ini. |
| Constrained Language Mode (disimulasikan dalam sesi) | 1 | `Method invocation is supported only on core types in this language mode` | 0,28 s | CONSTRAINED_LANGUAGE | PowerShell di PC ini berjalan dalam mode terbatas. |

Temuan penting:
1. `Restricted` **tidak** memblokir `-Command` inline; hanya memblokir file `.ps1`. Karena D-17 memakai `-Command`, ExecutionPolicy hampir tidak berdampak kecuali skill memuat file skrip.
2. Windows mencari executable memakai `PATH` proses induk, bukan `env=` anak. Tanpa preflight, mode NOT_FOUND tidak terdeteksi (terbukti di percobaan pertama). Wrapper kini me-resolve `powershell.exe` terhadap `PATH` yang diberikan sebelum meluncurkan.
3. Tidak ada crash tanpa pesan dan tidak ada data korup pada semua mode (0 kejadian).
4. ExecutionPolicy `CurrentUser` sudah dikembalikan ke `RemoteSigned` dan diverifikasi.

## 3. Tidak teruji
- **AppLocker/SRP memblokir `powershell.exe`**: tidak ada PC dengan kebijakan ini. Wrapper memetakan `OSError` WinError 1260/5/225 dan teks "blocked by group policy" ke `BLOCKED_BY_POLICY`, tetapi pemetaan ini **belum pernah dipicu** secara nyata.
- **CLM tingkat sistem (WDAC/AppLocker)**: yang diuji hanya CLM dalam sesi; gejala di sistem bisa berbeda.
- **PC kantor/terkelola**: tidak tersedia.

## 4. Rekomendasi
- Timeout produksi: **15 detik** (start normal 0,24 s, sehingga ~60x margin; PC lambat/antivirus yang memindai masih tercakup). Ini nilai default `DEFAULT_TIMEOUT`, belum divalidasi di PC lambat.
- Lakukan preflight `find_powershell()` saat startup dan cache hasilnya.
- Hindari menjalankan file `.ps1`; pakai `-Command` agar tidak terkena ExecutionPolicy.
- Selalu catat `stderr`/`returncode` asli ke log; tampilkan hanya `user_message` ke pengguna.
- Keterbatasan: mode yang tidak punya tanda khas di stderr akan jatuh ke `ERROR` generik.
