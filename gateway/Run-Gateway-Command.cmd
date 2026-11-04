@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "TEMP=%~dp0temp"
set "TMP=%~dp0temp"
chcp 65001 >nul
set "MGC_GATEWAY_PY=%~dp0..\runtime\python\python.exe"
if not exist "%MGC_GATEWAY_PY%" set "MGC_GATEWAY_PY=%~dp0..\runtime\venv\Scripts\python.exe"
if not exist "%MGC_GATEWAY_PY%" (
  echo MultiGoogleCloud runtime missing. Keep gateway beside the runtime and src folders.
  pause
  exit /b 1
)
"%MGC_GATEWAY_PY%" -B "%~dp0%~1" "%~2"
set "MGC_GATEWAY_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %MGC_GATEWAY_EXIT%
