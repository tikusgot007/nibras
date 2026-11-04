[CmdletBinding()]
param (
    [Parameter()]
    [string]$OutputDir = "App",

    [Parameter()]
    [string]$PythonVersion = "3.14.10",

    [Parameter()]
    [switch]$NoPrecompile,

    [Parameter()]
    [switch]$Clean,

    [Parameter()]
    [string]$CacheDir = ""
)

$ErrorActionPreference = "Stop"

$packages = @(
    "PySide6",
    "numpy",
    "onnxruntime",
    "openai",
    "anthropic",
    "httpx",
    "markdown-it-py",
    "Pygments",
    "cryptography",
    "argon2-cffi",
    "psutil",
    "pywin32",
    "mcp"
)

$resolvedOutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$pythonDir = Join-Path $resolvedOutputDir "python"
$sitePackagesDir = Join-Path $pythonDir "Lib\site-packages"

if ([string]::IsNullOrWhiteSpace($CacheDir)) {
    $CacheDir = [System.IO.Path]::GetFullPath("build_cache")
} else {
    $CacheDir = [System.IO.Path]::GetFullPath($CacheDir)
}

Write-Host "=== Nibras Fase 0 - Uji #2: Build Bundle ==="
Write-Host "Output Dir     : $resolvedOutputDir"
Write-Host "Python Dir     : $pythonDir"
Write-Host "Site-Packages  : $sitePackagesDir"
Write-Host "Python Version : $PythonVersion"
Write-Host "Cache Dir      : $CacheDir"
Write-Host "Precompile     : $(!$NoPrecompile)"
Write-Host "==========================================="

if ($Clean -and (Test-Path -LiteralPath $resolvedOutputDir)) {
    Write-Host "[1/7] Cleaning existing output directory..."
    Remove-Item -LiteralPath $resolvedOutputDir -Recurse -Force
}

if (!(Test-Path -LiteralPath $CacheDir)) {
    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
}
if (!(Test-Path -LiteralPath $sitePackagesDir)) {
    New-Item -ItemType Directory -Path $sitePackagesDir -Force | Out-Null
}

$embedZipName = "python-$PythonVersion-embed-amd64.zip"
$embedZipPath = Join-Path $CacheDir $embedZipName
$embedUrl = "https://www.python.org/ftp/python/$PythonVersion/$embedZipName"

if (!(Test-Path -LiteralPath $embedZipPath)) {
    Write-Host "[2/7] Downloading Python embeddable ($PythonVersion) from $embedUrl..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
    Invoke-WebRequest -Uri $embedUrl -OutFile $embedZipPath -UseBasicParsing
    Write-Host "Downloaded to: $embedZipPath"
} else {
    Write-Host "[2/7] Using cached Python embeddable archive: $embedZipPath"
}

Write-Host "[3/7] Extracting Python embeddable archive into $pythonDir..."
Expand-Archive -LiteralPath $embedZipPath -DestinationPath $pythonDir -Force

$pthFiles = Get-ChildItem -LiteralPath $pythonDir -Filter "*._pth"
if ($pthFiles.Count -eq 0) {
    throw "ERROR: No ._pth file found in $pythonDir"
}
$pthFile = $pthFiles[0].FullName
Write-Host "[4/7] Configuring ._pth file: $pthFile..."

$pthContent = Get-Content -LiteralPath $pthFile -Raw
$pthLines = $pthContent -split "`r?`n"
$newPthLines = @()
$hasSitePackages = $false
$hasImportSite = $false

foreach ($line in $pthLines) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "Lib\site-packages" -or $trimmed -eq "Lib/site-packages") {
        $hasSitePackages = $true
        $newPthLines += "Lib\site-packages"
    } elseif ($trimmed -eq "import site" -or $trimmed -eq "#import site") {
        $hasImportSite = $true
        $newPthLines += "import site"
    } else {
        $newPthLines += $line
    }
}

if (!$hasSitePackages) {
    $newPthLines += "Lib\site-packages"
}
if (!$hasImportSite) {
    $newPthLines += "import site"
}

Set-Content -LiteralPath $pthFile -Value ($newPthLines -join "`r`n") -Encoding Ascii
Write-Host "Updated ._pth content:"
Get-Content -LiteralPath $pthFile | ForEach-Object { Write-Host "   $_" }

$majorMinor = ($PythonVersion -split "\.")[0..1] -join "."
Write-Host "[5/7] Installing dependencies via pip --target for Python $majorMinor..."
$pipArgs = @(
    "install",
    "--target", $sitePackagesDir,
    "--platform", "win_amd64",
    "--python-version", $majorMinor,
    "--only-binary=:all:",
    "--upgrade"
) + $packages

Write-Host "Running: python -m pip $pipArgs"
& python -m pip @pipArgs
if ($LASTEXITCODE -ne 0) {
    throw "ERROR: pip install failed with exit code $LASTEXITCODE"
}

if (!$NoPrecompile) {
    Write-Host "[6/7] Precompiling bytecode (.py -> .pyc) using bundled Python ($PythonVersion)..."
    $bundlePythonExe = Join-Path $pythonDir "python.exe"
    & "$bundlePythonExe" -m compileall -q "$pythonDir"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "compileall returned non-zero exit code: $LASTEXITCODE"
    } else {
        Write-Host "Bytecode precompilation completed."
    }
} else {
    Write-Host "[6/7] Precompilation skipped (-NoPrecompile requested)."
}

Write-Host "[7/7] Copying startup probe into bundle..."
$probeSource = Join-Path $PSScriptRoot "startup_probe.py"
$probeDir = Join-Path $resolvedOutputDir "probe"
$probeDest = Join-Path $probeDir "startup_probe.py"
if (!(Test-Path -LiteralPath $probeSource)) {
    throw "ERROR: Startup probe script not found at: $probeSource"
}
if (!(Test-Path -LiteralPath $probeDir)) {
    New-Item -ItemType Directory -Path $probeDir -Force | Out-Null
}
Copy-Item -LiteralPath $probeSource -Destination $probeDest -Force
Write-Host "Copied probe to: $probeDest"

Write-Host "Gathering package versions from metadata..."
$packageVersions = @{}
$distInfos = Get-ChildItem -LiteralPath $sitePackagesDir -Directory -Filter "*.dist-info"
foreach ($di in $distInfos) {
    if ($di.Name -match "^(.+)-([^-]+)\.dist-info$") {
        $pkgName = $Matches[1]
        $pkgVer = $Matches[2]
        $packageVersions[$pkgName] = $pkgVer
    }
}

$allFiles = Get-ChildItem -LiteralPath $resolvedOutputDir -Recurse -File
$totalBytes = ($allFiles | Measure-Object -Property Length -Sum).Sum
$totalMB = [math]::Round($totalBytes / 1MB, 2)
$fileCount = $allFiles.Count

$buildInfo = [ordered]@{
    "build_timestamp"   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    "python_version"    = $PythonVersion
    "python_embed_url"  = $embedUrl
    "precompiled"       = (![bool]$NoPrecompile)
    "total_size_mb"     = $totalMB
    "total_files"       = $fileCount
    "packages"          = $packageVersions
}

$buildInfoPath = Join-Path $resolvedOutputDir "BUILD_INFO.json"
$buildInfo | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $buildInfoPath -Encoding utf8
Write-Host "Wrote BUILD_INFO.json -> $buildInfoPath"

Write-Host "=== BUILD SUMMARY ==="
Write-Host "Bundle Location : $resolvedOutputDir"
Write-Host "Total Size      : $totalMB MB"
Write-Host "Total Files     : $fileCount files"
Write-Host "Precompiled     : $(!$NoPrecompile)"
Write-Host "Packages count  : $($packageVersions.Count)"
Write-Host "Build completed successfully."
