# Helper for Uji #5. Triggers each simulatable failure mode and prints wrapper JSON.
# Does NOT touch machine policy. Only CurrentUser ExecutionPolicy is changed, and restored in `finally`.
param([ValidateSet('baseline','timeout','notfound','execpolicy','clm','all')][string]$Mode = 'all')
$here = $PSScriptRoot
$py = 'python'
function Invoke-Wrapper($code) { & $py -I -c $code }

if ($Mode -in 'baseline','all') {
  Write-Output '== baseline'
  Invoke-Wrapper "import sys;sys.path.insert(0,r'$here');import ps_wrapper as w,json,dataclasses as d;print(json.dumps(d.asdict(w.run_ps('Write-Output ok')),ensure_ascii=False))"
}
if ($Mode -in 'timeout','all') {
  Write-Output '== timeout'
  Invoke-Wrapper "import sys;sys.path.insert(0,r'$here');import ps_wrapper as w,json,dataclasses as d;print(json.dumps(d.asdict(w.run_ps('Start-Sleep -Seconds 30',timeout=3)),ensure_ascii=False))"
}
if ($Mode -in 'notfound','all') {
  Write-Output '== notfound (PATH override in test process only)'
  Invoke-Wrapper "import sys,os;sys.path.insert(0,r'$here');import ps_wrapper as w,json,dataclasses as d;e={'SystemRoot':os.environ['SystemRoot'],'PATH':r'C:\nonexistent'};print('preflight:',w.find_powershell(e));print(json.dumps(d.asdict(w.run_ps('Write-Output ok',env=e)),ensure_ascii=False))"
}
if ($Mode -in 'execpolicy','all') {
  Write-Output '== execpolicy Restricted (CurrentUser)'
  $orig = Get-ExecutionPolicy -Scope CurrentUser
  Write-Output "original CurrentUser = $orig"
  try {
    Set-ExecutionPolicy Restricted -Scope CurrentUser -Force
    & $py -I "$here\_execpolicy_probe.py"
  } finally {
    Set-ExecutionPolicy $orig -Scope CurrentUser -Force
    Write-Output "restored CurrentUser = $(Get-ExecutionPolicy -Scope CurrentUser)"
  }
}
if ($Mode -in 'clm','all') {
  Write-Output '== constrained language (in-session only; no system policy change)'
  & $py -I "$here\ps_wrapper.py" '$ExecutionContext.SessionState.LanguageMode = "ConstrainedLanguage"; [System.Math]::Sqrt(4)'
}
