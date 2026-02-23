param(
  [string]$AppDir = "D:\Python\CISP",
  [string]$CispUsername = "",
  [string]$CispPassword = "",
  [string]$Postgres = "",
  [string]$DbHost = "127.0.0.1",
  [string]$DbPort = "5432",
  [string]$DbName = "dbDataLakePrd",
  [string]$DbUser = "postgres",
  [string]$DbSchema = "scsilverlayer",
  [int]$ListenPort = 8000
)
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
$p=new-object Security.Principal.WindowsPrincipal($id)
if(-not $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)){Write-Error "admin";exit 1}
if(-not (Test-Path $AppDir)){Write-Error "path";exit 1}
Set-Location $AppDir
$pyexe = "$env:SystemDrive\Python311\python.exe"
try{& py -3.11 -c "print('ok')"|Out-Null;$usePy=$true}catch{$usePy=$false}
if($usePy){& py -3.11 -m venv .venv}else{& python -m venv .venv}
& .\.venv\Scripts\pip.exe install --no-cache-dir -r .\requirements.txt waitress
if($CispUsername){& cmd /c setx /M CISP_USERNAME "$CispUsername" | Out-Null}
if($CispPassword){& cmd /c setx /M CISP_PASSWORD "$CispPassword" | Out-Null}
if($Postgres){& cmd /c setx /M POSTGRES "$Postgres" | Out-Null}
if($DbHost){& cmd /c setx /M DB_HOST "$DbHost" | Out-Null}
if($DbPort){& cmd /c setx /M DB_PORT "$DbPort" | Out-Null}
if($DbName){& cmd /c setx /M DB_NAME "$DbName" | Out-Null}
if($DbUser){& cmd /c setx /M DB_USER "$DbUser" | Out-Null}
if($DbSchema){& cmd /c setx /M DB_SCHEMA "$DbSchema" | Out-Null}
$taskName="CISP-API"
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue|Out-Null}catch{}
$action=New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$AppDir\scripts\run-app.ps1`" -AppDir `"$AppDir`" -Listen `"127.0.0.1:$ListenPort`""
$trigger=New-ScheduledTaskTrigger -AtStartup
$principal=New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force|Out-Null
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2
Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$ListenPort/api/health" -TimeoutSec 5 | Out-Null
