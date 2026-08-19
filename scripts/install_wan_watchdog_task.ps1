# Install Wan stack watchdog at user logon (GPU PC).
# Run once: powershell -ExecutionPolicy Bypass -File scripts/install_wan_watchdog_task.ps1

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = (Get-Command python -ErrorAction Stop).Source
$script = Join-Path $repo "scripts\wan_stack_watchdog.py"
if (-not (Test-Path $script)) { throw "Missing $script" }

$startup = [Environment]::GetFolderPath("Startup")
$cmdPath = Join-Path $startup "WanStudioGpuWatchdog.cmd"
@(
  "@echo off"
  "cd /d `"$repo`""
  "`"$python`" `"$script`""
) | Set-Content -Path $cmdPath -Encoding ASCII
Write-Host "Installed login starter: $cmdPath"

Write-Host "Starting watchdog now in a new window..."
Start-Process -FilePath $python -ArgumentList "`"$script`"" -WorkingDirectory $repo -WindowStyle Normal
Write-Host "Done. Leave this PC on (disable sleep)."
Write-Host "From phone: unlock PIN 9977 -> Controls -> Restart GPU when stuck."
