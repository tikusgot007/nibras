[CmdletBinding()]
param (
    [Parameter(Mandatory = $true)]
    [string]$Scenario,

    [Parameter()]
    [int]$Runs = 1,

    [Parameter()]
    [string]$BundleDir = "App",

    [Parameter()]
    [string]$DataDir = "Data",

    [Parameter()]
    [string]$OutDir = "results\startup",

    [Parameter()]
    [string]$ProbeScript = "spikes\uji02-startup\startup_probe.py",

    [Parameter()]
    [int]$TimeoutSeconds = 60,

    [Parameter()]
    [int]$StartRunIndex = 1
)

$ErrorActionPreference = "Stop"

$resolvedBundleDir = [System.IO.Path]::GetFullPath($BundleDir)
$resolvedDataDir = [System.IO.Path]::GetFullPath($DataDir)
$resolvedOutDir = [System.IO.Path]::GetFullPath($OutDir)
$resolvedProbeScript = [System.IO.Path]::GetFullPath($ProbeScript)

$pythonDir = Join-Path $resolvedBundleDir "python"
$pythonwExe = Join-Path $pythonDir "pythonw.exe"
$pythonExe = Join-Path $pythonDir "python.exe"

$targetExe = if (Test-Path -LiteralPath $pythonwExe) { $pythonwExe } else { $pythonExe }

if (!(Test-Path -LiteralPath $targetExe)) {
    throw "ERROR: Target Python executable not found at: $targetExe"
}
if (!(Test-Path -LiteralPath $resolvedProbeScript)) {
    throw "ERROR: Probe script not found at: $resolvedProbeScript"
}

if (!(Test-Path -LiteralPath $resolvedDataDir)) {
    New-Item -ItemType Directory -Path $resolvedDataDir -Force | Out-Null
}
if (!(Test-Path -LiteralPath $resolvedOutDir)) {
    New-Item -ItemType Directory -Path $resolvedOutDir -Force | Out-Null
}

Write-Host "=== Nibras Startup Measurement ==="
Write-Host "Scenario     : $Scenario"
Write-Host "Runs count   : $Runs"
Write-Host "Start Index  : $StartRunIndex"
Write-Host "Executable   : $targetExe"
Write-Host "Bundle Dir   : $resolvedBundleDir"
Write-Host "Data Dir     : $resolvedDataDir"
Write-Host "Output Dir   : $resolvedOutDir"
Write-Host "Timeout      : $TimeoutSeconds s"
Write-Host "=================================="

$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONNOUSERSITE = "1"
if (Test-Path env:PYTHONPATH) { Remove-Item env:PYTHONPATH }
if (Test-Path env:PYTHONHOME) { Remove-Item env:PYTHONHOME }

for ($i = 0; $i -ge 0 -and $i -lt $Runs; $i++) {
    $runIndex = $StartRunIndex + $i
    $runName = [string]::Format("{0}-run-{1:D2}", $Scenario, $runIndex)
    $outFile = Join-Path $resolvedOutDir "$runName.json"

    Write-Host "`n[RUN $runIndex/$($StartRunIndex + $Runs - 1)] Executing: $runName..."

    $epochStart = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $targetExe
    $psi.Arguments = "`"$resolvedProbeScript`" --t0 $epochStart --out `"$outFile`" --data-dir `"$resolvedDataDir`" --bundle-dir `"$resolvedBundleDir`""
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1"
    $psi.EnvironmentVariables["PYTHONNOUSERSITE"] = "1"

    $proc = [System.Diagnostics.Process]::Start($psi)
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)

    if (!$finished) {
        $proc.Kill()
        Write-Error "TIMEOUT: Run $runName exceeded $TimeoutSeconds seconds and was killed."
        continue
    }

    $exitCode = $proc.ExitCode
    Write-Host "Process completed with exit code: $exitCode"

    if (Test-Path -LiteralPath $outFile) {
        try {
            $jsonContent = Get-Content -LiteralPath $outFile -Raw | ConvertFrom-Json
            $t3 = $jsonContent.elapsed_from_t0_ms.T3
            $t6 = $jsonContent.elapsed_from_t0_ms.T6
            $isolationPassed = $jsonContent.isolation.passed
            $passed = $jsonContent.passed

            Write-Host "  T3 (First Paint): $t3 ms"
            Write-Host "  T6 (Ready)      : $t6 ms"
            Write-Host "  Isolation OK    : $isolationPassed"
            Write-Host "  Status          : $(if ($passed) { 'PASS' } else { 'FAIL' })"
        } catch {
            Write-Warning "Failed to parse result JSON: $_"
        }
    } else {
        Write-Error "Output JSON not created: $outFile"
    }
}

Write-Host "`nAll measurement runs completed."
