# Windows: register the project skills for Claude Code and GitHub Copilot (VS Code).
# Both tools load project skills from .claude\skills\<name>\SKILL.md. On macOS this is a symlink (see README);
# on Windows a directory junction does the same job and needs no admin rights or Developer Mode.
#   powershell -ExecutionPolicy Bypass -File link_skills.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force .claude\skills | Out-Null
foreach ($s in @("openpages-solutions", "openpages-tutorial")) {
  $src = Join-Path $PSScriptRoot "skills\$s"
  $dst = ".claude\skills\$s"
  if (-not (Test-Path "$src\SKILL.md")) { Write-Host "skip $s (no $src\SKILL.md)"; continue }
  if (Test-Path $dst) {
    $item = Get-Item $dst -Force
    if ($item.LinkType) { Write-Host "ok   $dst -> $($item.Target)"; continue }
    Write-Host "STOP $dst exists and is a real folder; move it away first"; exit 1
  }
  New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
  Write-Host "link $dst -> $src"
}
if ((Test-Path .claude\skills\openpages-solutions\SKILL.md) -and (Test-Path .claude\skills\openpages-tutorial\SKILL.md)) {
  Write-Host "skill links OK. Restart VS Code / Claude Code, then type /openpages-tutorial in chat."
}
