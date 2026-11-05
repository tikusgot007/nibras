# Pasang bundle Nibras ke flashdisk (D-07).
# Dijalankan di Windows SETELAH build_bundle.ps1.
#   powershell -ExecutionPolicy Bypass -File packaging/install_to_usb.ps1 -DriveLetter X:
#
# Skrip ini memverifikasi dulu bahwa drive target benar-benar flashdisk
# USB (Get-Disk/Get-Volume, BusType harus USB) dan berformat NTFS,
# menampilkan ringkasannya, lalu MEMINTA KONFIRMASI sebelum menulis.
# Data/ yang sudah ada di flashdisk TIDAK ditimpa.
param(
    [Parameter(Mandatory = $true)]
    [string]$DriveLetter,
    [string]$BuildDir = "build",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$letter = $DriveLetter.TrimEnd(':').ToUpper()
$build = Join-Path $root $BuildDir
if (-not (Test-Path (Join-Path $build "Nibras.exe"))) {
    throw "Bundle belum ada di $build. Jalankan dulu packaging/build_bundle.ps1."
}

Write-Host "== Identifikasi drive ${letter}: =="
$disk = Get-Disk | Where-Object { $_.BusType -eq 'USB' }
$volume = Get-Volume -DriveLetter $letter -ErrorAction SilentlyContinue
if (-not $volume) { throw "Drive ${letter}: tidak ditemukan." }
$diskForVolume = $disk | Where-Object { $_.Number -eq (Get-Partition -DriveLetter $letter).DiskNumber }
if (-not $diskForVolume) {
    throw "Drive ${letter}: BUKAN flashdisk USB (BusType bukan USB). Dibatalkan demi keamanan."
}
$volume | Format-Table DriveLetter, FileSystem, SizeRemaining, Size, DriveType
$diskForVolume | Format-Table Number, FriendlyName, BusType, Size
if ($volume.FileSystem -ne 'NTFS') {
    throw "Drive ${letter}: memakai $($volume.FileSystem), bukan NTFS. Nibras butuh NTFS. Dibatalkan."
}

if (-not $Force) {
    $answer = Read-Host "Pasang Nibras ke drive ${letter}: ($($diskForVolume.FriendlyName))? Ketik YA untuk lanjut"
    if ($answer -ne 'YA') { Write-Host "Dibatalkan."; exit 0 }
}

$target = "${letter}:\"
Write-Host "== Salin bundle (Data/ lama dipertahankan) =="
robocopy $build $target /E /XD Data Temp Backups /R:2 /W:2 /NFL /NDL /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Robocopy gagal (kode $LASTEXITCODE)." }
foreach ($dir in @("Data", "Temp", "Backups")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $target $dir) | Out-Null
}
Write-Host ""
Write-Host "Selesai. Jalankan ${letter}:\Nibras.exe untuk memakai Nibras."
