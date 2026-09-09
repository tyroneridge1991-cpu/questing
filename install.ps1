$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  Write-Host 'Python launcher (py) was not found. For the easiest install, use the GitHub Actions EXE instead.'
  exit 1
}

py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean OSRSQuestNavigator.spec
Write-Host ''
Write-Host 'BUILD COMPLETE'
Write-Host (Join-Path $root 'dist\OSRSQuestNavigator.exe')
