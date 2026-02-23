param(
  [string]$RepoUrl,
  [string]$Branch = "main",
  [string]$AppDir = "D:\Python\CISP",
  [string]$TaskName = "CISP-API",
  [int]$ListenPort = 8000
)
if(-not $RepoUrl){Write-Error "repo";exit 1}
if(-not (Test-Path $AppDir)){New-Item -ItemType Directory -Path $AppDir | Out-Null}
if(Test-Path (Join-Path $AppDir ".git")){
  git -C $AppDir fetch origin $Branch
  git -C $AppDir reset --hard origin/$Branch
}else{
  git clone -b $Branch $RepoUrl $AppDir
}
if(-not (Test-Path (Join-Path $AppDir ".venv"))){
  try{& py -3.11 -m venv (Join-Path $AppDir ".venv")}catch{& python -m venv (Join-Path $AppDir ".venv")}
}
& (Join-Path $AppDir ".venv\Scripts\pip.exe") install --no-cache-dir -r (Join-Path $AppDir "requirements.txt") waitress
try{Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue|Out-Null}catch{}
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 2
try{Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$ListenPort/api/health" -TimeoutSec 5 | Out-Null}catch{}
