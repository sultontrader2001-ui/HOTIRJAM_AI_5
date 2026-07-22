# HOTIRJAM Bridge — Windows install (PowerShell)
# Run from the bridge/ folder:
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\install_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "Installing hotirjam-bridge from: $Root"

$Python = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $Python = "py -3"
} else {
    throw "Python not found. Install Python 3.13+ and ensure it is on PATH."
}

Write-Host "Using: $Python"
Invoke-Expression "$Python -m pip install -U pip"
Invoke-Expression "$Python -m pip install -e ."

Write-Host ""
Write-Host "Verifying entry points..."
$scripts = Invoke-Expression "$Python -c `"import importlib.metadata as m; eps=m.entry_points(); sel=eps.select(group='console_scripts') if hasattr(eps,'select') else eps.get('console_scripts',[]); print([e.name for e in sel if 'bridge' in e.name])`""
Write-Host $scripts

Write-Host ""
Write-Host "Try (any of these):"
Write-Host "  1) hotirjam-bridge-sender --help"
Write-Host "  2) bridge_sender --help"
Write-Host "  3) python -m hotirjam_bridge.sender --help"
Write-Host "  4) .\hotirjam-bridge-sender.cmd --help"
Write-Host ""
Write-Host "If (1)/(2) fail with CommandNotFoundException:"
Write-Host "  - You installed from the wrong folder (must be bridge/, not HOTIRJAM_AI_5/)"
Write-Host "  - Or Scripts\ is not on PATH. Use (3) or (4)."
Write-Host "  - Locate Scripts: python -c \"import sysconfig; print(sysconfig.get_path('scripts'))\""
