@echo off
setlocal
cd /d %~dp0

set PS_FLAGS=
set ARX_ADMIN_USER=
set ARX_ADMIN_PASS=

:copy_args
if "%~1"=="" goto run_ps
if /I "%~1"=="--admin-user" goto parse_admin_user
if /I "%~1"=="--admin-pass" goto parse_admin_pass
set PS_FLAGS=%PS_FLAGS% %1
shift
goto copy_args

:parse_admin_user
shift
if "%~1"=="" goto run_ps
set "ARX_ADMIN_USER=%~1"
set PS_FLAGS=%PS_FLAGS% --AdminUser "%~1"
shift
goto copy_args

:parse_admin_pass
shift
if "%~1"=="" goto run_ps
set "ARX_ADMIN_PASS=%~1"
set PS_FLAGS=%PS_FLAGS% --AdminPass "%~1"
shift
goto copy_args

:run_ps
where pwsh >nul 2>nul
if not errorlevel 1 (
  pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %PS_FLAGS%
  exit /b %ERRORLEVEL%
)

where powershell >nul 2>nul
if not errorlevel 1 (
  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %PS_FLAGS%
  exit /b %ERRORLEVEL%
)

echo PowerShell is required for install.ps1.
echo Install PowerShell 7 (pwsh) or Windows PowerShell, then rerun.
exit /b 1
