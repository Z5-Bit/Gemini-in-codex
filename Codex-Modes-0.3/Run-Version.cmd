@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "MGC_COMBINED_HOME=%~dp0.."
if not exist "%MGC_COMBINED_HOME%\SUITE-COMPONENTS.json" set "MGC_COMBINED_HOME=%~dp0..\versions\0.3-combined"
set "TEMP=%MGC_COMBINED_HOME%\runtime\temp"
set "TMP=%MGC_COMBINED_HOME%\runtime\temp"
if not exist "%TEMP%" mkdir "%TEMP%"
set "MGC_COMBINED_PY=%MGC_COMBINED_HOME%\runtime\python\python.exe"
if not exist "%MGC_COMBINED_PY%" (
  echo Runtime missing. Keep the complete 0.3 suite folder.
  pause
  exit /b 1
)
"%MGC_COMBINED_PY%" -B "%MGC_COMBINED_HOME%\scripts\combined_modes.py" "%~1"
set "MGC_COMBINED_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %MGC_COMBINED_EXIT%
