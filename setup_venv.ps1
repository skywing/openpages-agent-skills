# Windows twin of setup_venv.sh: create/refresh the project virtual environment in .\.venv
#   powershell -ExecutionPolicy Bypass -File setup_venv.ps1              create/update
#   powershell -ExecutionPolicy Bypass -File setup_venv.ps1 -Recreate    force rebuild
#   $env:PYTHON = "C:\Path\python.exe"; .\setup_venv.ps1                 use an explicit interpreter
# Target version comes from .python-version (major.minor, e.g. 3.12). Uses the Windows "py" launcher when present.
param([switch]$Recreate)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$want = if (Test-Path .python-version) { (Get-Content .python-version -Raw).Trim() } else { "3.12" }

function Get-Ver($exe, [string[]]$pre = @()) {
  try { & $exe @pre -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null } catch { $null }
}

$py = $null; $pyArgs = @()
if ($env:PYTHON) { $py = $env:PYTHON }
elseif ((Get-Command py -ErrorAction SilentlyContinue) -and ((Get-Ver py @("-$want")) -eq $want)) { $py = "py"; $pyArgs = @("-$want") }
else {
  foreach ($c in @("python$want", "python3", "python")) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd -and ((Get-Ver $cmd.Source) -eq $want)) { $py = $cmd.Source; break }
  }
}
if (-not $py) {
  Write-Host "Python $want not found. Install it from python.org (tick 'Add python.exe to PATH' and the 'py launcher'),"
  Write-Host "or set `$env:PYTHON to its python.exe and run this script again."
  exit 1
}
$have = Get-Ver $py $pyArgs
Write-Host "Using $py $pyArgs (Python $have)"

$venvPy = ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
  $cur = Get-Ver $venvPy
  if ($Recreate -or $cur -ne $have) { Write-Host "Rebuilding .venv (current: $cur, wanted: $have)"; Remove-Item -Recurse -Force .venv }
}
if (-not (Test-Path .venv)) { & $py @pyArgs -m venv .venv }
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r requirements.txt
# Windows has no system time-zone database: zoneinfo (used for DATE fields, environments.yaml `timezone`) needs tzdata.
& $venvPy -m pip install tzdata
Write-Host "OK: $(& $venvPy --version) at $(Get-Location)\.venv"
Write-Host "Run scripts with:  .\op op.py ping     (op.cmd sets PYTHONUTF8=1 for you)"
Write-Host "Interactive use:   .venv\Scripts\Activate.ps1 ; `$env:PYTHONUTF8 = '1'"
