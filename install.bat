@echo off
setlocal
cd /d %~dp0

set PS_FLAGS=

:copy_args
if "%~1"=="" goto run_ps
set PS_FLAGS=%PS_FLAGS% %1
shift
goto copy_args

:run_ps
where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell is required for install.ps1.
  echo Please run install.ps1 manually after installing PowerShell.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %PS_FLAGS%
exit /b %ERRORLEVEL%
