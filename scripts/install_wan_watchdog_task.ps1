# Install hidden Wan GPU watchdog at user logon (no taskbar consoles).
# Run: powershell -ExecutionPolicy Bypass -File scripts/install_wan_watchdog_task.ps1

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$vbs = Join-Path $repo "scripts\start_wan_stack_hidden.vbs"
if (-not (Test-Path $vbs)) { throw "Missing $vbs" }

$startup = [Environment]::GetFolderPath("Startup")
$lnkPath = Join-Path $startup "WanStudioGpuWatchdog.lnk"
$w = New-Object -ComObject WScript.Shell
$lnk = $w.CreateShortcut($lnkPath)
$lnk.TargetPath = "wscript.exe"
$lnk.Arguments = "`"$vbs`""
$lnk.WorkingDirectory = $repo
$lnk.WindowStyle = 7
$lnk.Description = "Wan GPU watchdog (hidden)"
$lnk.Save()

foreach ($name in @(
    "WanStudioGpuWatchdog.cmd",
    "WanStudioCloudflared.cmd"
  )) {
  $p = Join-Path $startup $name
  if (Test-Path $p) { Remove-Item $p -Force }
}

Write-Host "Installed hidden login starter: $lnkPath"
Write-Host "Logs: $repo\tmp_test\watchdog.log"
Write-Host "Leave this PC on (disable sleep)."
