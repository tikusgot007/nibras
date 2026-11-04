# Uji #5 — PowerShell di akun non-admin dan PC kantor

Spike (bukan kode aplikasi). Referensi: `docs/decisions.md` D-17, brief `docs/briefs/fase0-uji05-powershell-nonadmin.md`.

## Isi
- `ps_wrapper.py` — `run_ps(script, timeout, env)` memanggil `powershell.exe -NoProfile -NonInteractive -Command`, mengklasifikasikan kegagalan (`OK`, `NOT_FOUND`, `BLOCKED_BY_POLICY`, `EXEC_POLICY`, `CONSTRAINED_LANGUAGE`, `TIMEOUT`, `ERROR`). stdout/stderr/exit code asli selalu disimpan; `user_message` adalah teks sederhana untuk pengguna.
- `simulate_modes.ps1` — memicu tiap mode. Hanya ExecutionPolicy `CurrentUser` yang diubah sementara, dan dikembalikan di blok `finally`.
- `noop.ps1`, `_execpolicy_probe.py` — bahan bantu uji ExecutionPolicy.

## Menjalankan
```
powershell -NoProfile -File simulate_modes.ps1 -Mode all
```
Mode: `baseline`, `timeout`, `notfound`, `execpolicy`, `clm`, `all`.

Hasil dan rekomendasi: `results/uji05-powershell.md`.
