' Hidden GPU stack: watchdog only. It starts Cloudflare with no console.
' WindowStyle 0 = hidden, no taskbar button.
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
cmd = "cmd /c cd /d """ & repo & """ && python """ & wd & """ >> """ & logFile & """ 2>&1"
sh.Run cmd, 0, False
