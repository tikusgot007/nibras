# Build Nibras.exe dari launcher/nibras.c (D-60).
# Dijalankan di Windows dengan mingw-w64 terpasang.
#   powershell -ExecutionPolicy Bypass -File launcher/build_launcher.ps1 [-OutDir build]
param(
    [string]$OutDir = "build"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$gcc = Get-Command x86_64-w64-mingw32-gcc -ErrorAction SilentlyContinue
if (-not $gcc) {
    Write-Error "mingw-w64 tidak ditemukan. Pasang dulu (misal: winget install --id MSYS2.MSYS2, lalu pacman -S mingw-w64-x86_64-gcc) dan pastikan x86_64-w64-mingw32-gcc ada di PATH."
}
$outDirFull = Join-Path $root $OutDir
New-Item -ItemType Directory -Force -Path $outDirFull | Out-Null
$exe = Join-Path $outDirFull "Nibras.exe"
& x86_64-w64-mingw32-gcc -mwindows -O2 -Wall -o $exe (Join-Path $root "launcher\nibras.c")
if ($LASTEXITCODE -ne 0) { throw "Kompilasi launcher gagal." }
Write-Host "Launcher jadi: $exe"
