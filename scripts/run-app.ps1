param(
  [string]$AppDir = "D:\Python\CISP",
  [string]$Listen = "127.0.0.1:8000"
)
Set-Location $AppDir
$py = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { exit 1 }
& $py -m waitress --listen=$Listen app:app
