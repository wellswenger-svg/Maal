' Hidden mobile/anywhere GPU stack at login.
' Starts wan_stack_watchdog.py with no console / no taskbar button.
' Watchdog brings up: Comfy :8188, Cloudflare tunnel, gpu_agent :8799, agent tunnel,
' and pushes new tunnel URLs to Render so phone gens keep working.
'
' Installed by: scripts\install_mobile_autostart.ps1
Option Explicit
Dim sh, fso, repo, wd, logFile, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
repo = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
wd = repo & "\scripts\wan_stack_watchdog.py"
logFile = repo & "\tmp_test\watchdog.log"
If Not fso.FolderExists(repo & "\tmp_test") Then
  fso.CreateFolder repo & "\tmp_test"
End If
If Not fso.FileExists(wd) Then
  WScript.Quit 1
End If
' WindowStyle 0 = completely hidden
cmd = "cmd /c cd /d """ & repo & """ && python """ & wd & """ >> """ & logFile & """ 2>&1"
sh.Run cmd, 0, False
