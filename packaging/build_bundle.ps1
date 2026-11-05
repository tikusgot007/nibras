# Build bundle Nibras ke folder build/ (D-61, D-62).
# Dijalankan di Windows. Hasil build TIDAK di-commit (build/ di-ignore).
#   powershell -ExecutionPolicy Bypass -File packaging/build_bundle.ps1
#
# Langkah: unduh Python Embeddable 3.14.10 (URL + SHA-256 dikunci di bawah),
# pasang pip, install dependency dari requirements.lock dengan
# --require-hashes, salin kode aplikasi, precompile .pyc, salin font.
param(
    [string]$OutDir = "build"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Python Embeddable yang dipakai (sama dengan versi yang divalidasi Uji #2).
$PythonVersion = "3.14.10"
$PythonUrl = "https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip"
$PythonSha256 = "90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"

$build = Join-Path $root $OutDir
$appPython = Join-Path $build "App\python"
$sitePackages = Join-Path $appPython "Lib\site-packages"

Write-Host "== Bersihkan folder build =="
if (Test-Path $build) { Remove-Item -Recurse -Force $build }
New-Item -ItemType Directory -Force -Path $appPython | Out-Null

Write-Host "== Unduh Python Embeddable $PythonVersion =="
$zip = Join-Path $env:TEMP "python-3.14.10-embed-amd64.zip"
Invoke-WebRequest -Uri $PythonUrl -OutFile $zip
$hash = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
if ($hash -ne $PythonSha256) {
    throw "SHA-256 Python Embeddable tidak cocok! dapat: $hash, harap: $PythonSha256"
}
Expand-Archive -Path $zip -DestinationPath $appPython -Force

Write-Host "== Aktifkan site-packages di python314._pth =="
$pth = Join-Path $appPython "python314._pth"
$lines = Get-Content $pth
if ($lines -notcontains "Lib\site-packages") {
    Add-Content $pth "Lib\site-packages"
}

Write-Host "== Pasang pip (embeddable tidak membawa pip) =="
$getPip = Join-Path $env:TEMP "get-pip.py"
Invoke-WebRequest -Uri $GetPipUrl -OutFile $getPip
& (Join-Path $appPython "python.exe") $getPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "get-pip gagal." }

Write-Host "== Install dependency dari lock (dengan hash) =="
& (Join-Path $appPython "python.exe") -m pip install --no-warn-script-location `
    --require-hashes --no-cache-dir --target $sitePackages `
    -r (Join-Path $root "packaging\requirements.lock")
if ($LASTEXITCODE -ne 0) { throw "pip install dari lock gagal." }

Write-Host "== Salin kode aplikasi =="
Copy-Item -Recurse -Force -Exclude __pycache__ `
    (Join-Path $root "src\nibras") (Join-Path $sitePackages "nibras")

Write-Host "== Precompile .pyc =="
& (Join-Path $appPython "python.exe") -m compileall -q $sitePackages
if ($LASTEXITCODE -ne 0) { throw "compileall gagal." }

Write-Host "== Unduh font (Inter + JetBrains Mono, OFL) =="
$fonts = Join-Path $build "App\fonts"
New-Item -ItemType Directory -Force -Path $fonts | Out-Null
$fontList = @(
    @("https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
      "Inter.ttf",
      "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"),
    @("https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
      "JetBrainsMono.ttf",
      "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda")
)
foreach ($font in $fontList) {
    $url, $name, $want = $font
    $dest = Join-Path $fonts $name
    Invoke-WebRequest -Uri $url -OutFile $dest
    $got = (Get-FileHash -Algorithm SHA256 $dest).Hash.ToLower()
    if ($got -ne $want) { throw "SHA-256 font $name tidak cocok! dapat: $got" }
}

Write-Host "== Salin launcher =="
$launcher = Join-Path $build "Nibras.exe"
if (-not (Test-Path $launcher)) {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $root "launcher\build_launcher.ps1") -OutDir $OutDir
}

Write-Host ""
Write-Host "Bundle jadi di: $build"
Write-Host "Isi: Nibras.exe, App\python, App\fonts"
Write-Host "Lanjut: install_to_usb.ps1 -DriveLetter X:"
