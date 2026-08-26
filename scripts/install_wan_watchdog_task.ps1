# Install hidden Wan GPU watchdog at user logon (no taskbar consoles).
# Prefer the full installer:
#   powershell -ExecutionPolicy Bypass -File scripts/install_mobile_autostart.ps1
#
# This script remains as a thin wrapper for older docs / shortcuts.

$ErrorActionPreference = "Stop"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "install_mobile_autostart.ps1") @args
