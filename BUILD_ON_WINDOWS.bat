@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required only to build the EXE.
  echo Install it from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
py -m pip install --upgrade pyinstaller
if errorlevel 1 pause & exit /b 1
pyinstaller --noconfirm --clean OSRSQuestNavigator.spec
if errorlevel 1 pause & exit /b 1
echo.
echo BUILD COMPLETE!
echo Your EXE is here:
echo %CD%\dist\OSRSQuestNavigator.exe
pause
