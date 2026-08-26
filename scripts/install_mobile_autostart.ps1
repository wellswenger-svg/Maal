# Install + start the mobile/anywhere GPU stack so it runs hidden at every login.
#
# Keeps this PC ready for: phone / other PC -> Vercel -> Render -> Cloudflare -> Comfy here.
# Starts (and re-heals): ComfyUI :8188, Comfy tunnel, gpu_agent :8799, agent tunnel,
# Prowler Control :8010 + Prowler tunnel (prowler_url in tokens&cmd).
# Updates Render COMFYUI_URL / GPU_AGENT_URL when a tunnel URL changes.
#
# One-time setup (PowerShell, this GPU PC):
#   powershell -ExecutionPolicy Bypass -File scripts/install_mobile_autostart.ps1
#
# Options:
#   -NoStart           only install login shortcut (do not start now)
#   -Status            print whether startup link + stack look healthy
#   -Uninstall         remove login shortcut only (does not kill running processes)
#
# Requires: python on PATH, cloudflared, gitignored tokens&cmd with render=<key>
# Leave this PC on; disable sleep while you need remote gens.

param(
    [switch]$NoStart,
    [switch]$Status,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$vbs = Join-Path $repo "scripts\start_wan_stack_hidden.vbs"
$watchdog = Join-Path $repo "scripts\wan_stack_watchdog.py"
$tokens = Join-Path $repo "tokens&cmd"
$logFile = Join-Path $repo "tmp_test\watchdog.log"
$startup = [Environment]::GetFolderPath("Startup")
$lnkPath = Join-Path $startup "WanStudioGpuWatchdog.lnk"
$cloudflared = "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
    $cloudflared = "$env:ProgramFiles\cloudflared\cloudflared.exe"
}

function Test-PortOpen([int]$Port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.ReceiveTimeout = 1000
        $c.SendTimeout = 1000
        $c.Connect("127.0.0.1", $Port)
        $c.Close()
        return $true
    } catch {
        return $false
    }
}

function Show-Status {
    Write-Host "=== Mobile stack status ==="
    Write-Host "Repo:     $repo"
    if (Test-Path $lnkPath) {
        Write-Host "Startup:  INSTALLED - $lnkPath"
    } else {
        Write-Host "Startup:  MISSING"
    }
    if (Test-Path $tokens) {
        Write-Host "tokens:   OK"
    } else {
        Write-Host "tokens:   MISSING - need tokens&cmd with render="
    }
    if (Test-Path $cloudflared) {
        Write-Host "cloudflared: OK - $cloudflared"
    } else {
        Write-Host "cloudflared: MISSING"
    }
    if (Test-PortOpen 8188) { Write-Host "Comfy :8188: UP" } else { Write-Host "Comfy :8188: down" }
    if (Test-PortOpen 8799) { Write-Host "gpu_agent :8799: UP" } else { Write-Host "gpu_agent :8799: down" }
    $wd = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match "wan_stack_watchdog\.py" }
    if ($wd) {
        Write-Host ("watchdog: RUNNING (pid {0})" -f ($wd.ProcessId -join ","))
    } else {
        Write-Host "watchdog: not running"
    }
    if (Test-Path $logFile) {
        Write-Host "Log tail ($logFile):"
        Get-Content $logFile -Tail 5 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $_" }
    }
    try {
        $h = Invoke-RestMethod -Uri "https://wan-studio-api.onrender.com/api/health" -TimeoutSec 20
        Write-Host ("Render:   ok={0} comfyui={1} url={2}" -f $h.ok, $h.comfyui, $h.comfyui_url)
    } catch {
        Write-Host ("Render:   unreachable ({0})" -f $_.Exception.Message)
    }
    Write-Host "Frontend: https://frontend-six-chi-37.vercel.app"
}

if ($Status) {
    Show-Status
    exit 0
}

if ($Uninstall) {
    if (Test-Path $lnkPath) {
        Remove-Item $lnkPath -Force
        Write-Host "Removed login starter: $lnkPath"
    } else {
        Write-Host "No login starter to remove."
    }
    exit 0
}

if (-not (Test-Path $vbs)) { throw "Missing $vbs" }
if (-not (Test-Path $watchdog)) { throw "Missing $watchdog" }
if (-not (Test-Path $tokens)) {
    throw "Missing tokens&cmd - add render=<Render API key> (keep file gitignored)"
}
$hasRender = Select-String -Path $tokens -Pattern "^render=.+" -Quiet
if (-not $hasRender) {
    throw "tokens&cmd has no render= line - Render cannot get tunnel URL updates"
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python not on PATH"
}
if (-not (Test-Path $cloudflared)) {
    Write-Warning "cloudflared not found - install from Cloudflare, then re-run. Watchdog will fail tunnels until then."
}

# Login: hidden VBS -> python watchdog (no console, no taskbar)
$w = New-Object -ComObject WScript.Shell
$lnk = $w.CreateShortcut($lnkPath)
$lnk.TargetPath = "wscript.exe"
$lnk.Arguments = "`"$vbs`""
$lnk.WorkingDirectory = $repo
$lnk.WindowStyle = 7
$lnk.Description = "Wan Studio mobile stack (Comfy + tunnels + gpu_agent) - hidden"
$lnk.Save()

foreach ($name in @("WanStudioGpuWatchdog.cmd", "WanStudioCloudflared.cmd")) {
    $p = Join-Path $startup $name
    if (Test-Path $p) { Remove-Item $p -Force }
}

Write-Host "Installed login autostart: $lnkPath"
Write-Host "On every sign-in, the stack starts hidden and heals in the background."
Write-Host "Logs: $logFile"
Write-Host "Disable sleep while you need phone gens from elsewhere."

if ($NoStart) {
    Write-Host "Skipped start (-NoStart). Will run at next login."
    exit 0
}

Write-Host "Starting stack now (hidden)..."
Start-Process -FilePath "wscript.exe" -ArgumentList "`"$vbs`"" -WindowStyle Hidden
Start-Sleep -Seconds 4
Show-Status
Write-Host ""
Write-Host "Done. Generate from phone/other PC at https://frontend-six-chi-37.vercel.app"
