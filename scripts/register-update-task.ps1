param(
  [string]$RepoUrl,
  [string]$Branch = "main",
  [string]$AppDir = "D:\Python\CISP",
  [string]$TaskName = "CISP-Update",
  [string]$RunnerTask = "CISP-API",
  [int]$ListenPort = 8000,
  [int]$IntervalMinutes = 10
)
if(-not $RepoUrl){Write-Error "repo";exit 1}
$now = Get-Date
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$AppDir\scripts\update-and-restart.ps1`" -RepoUrl `"$RepoUrl`" -Branch `"$Branch`" -AppDir `"$AppDir`" -TaskName `"$RunnerTask`" -ListenPort $ListenPort"
$trigger = New-ScheduledTaskTrigger -Once $now -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration ([TimeSpan]::MaxValue)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
try{Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue|Out-Null}catch{}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force|Out-Null
Start-ScheduledTask -TaskName $TaskName
