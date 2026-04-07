@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d %~dp0

set YES_MODE=0
set FORCE_ENV=0
set DASHBOARD_PORT=
set AGENT_TRIGGER=
set GEMMA_MODEL=
set GEMMA_CONTEXT_SIZE=
set GEMMA_TEMPERATURE=

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--yes" (
  set YES_MODE=1
  shift
  goto parse_args
)
if /I "%~1"=="--force-env" (
  set FORCE_ENV=1
  shift
  goto parse_args
)
if /I "%~1"=="--port" (
  set DASHBOARD_PORT=%~2
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--trigger" (
  set AGENT_TRIGGER=%~2
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--model" (
  set GEMMA_MODEL=%~2
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--context-size" (
  set GEMMA_CONTEXT_SIZE=%~2
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--temperature" (
  set GEMMA_TEMPERATURE=%~2
  shift
  shift
  goto parse_args
)
echo Unknown flag: %~1
exit /b 1

:args_done
if "%DASHBOARD_PORT%"=="" set DASHBOARD_PORT=18890
if "%AGENT_TRIGGER%"=="" set AGENT_TRIGGER=gemma
if "%GEMMA_MODEL%"=="" set GEMMA_MODEL=gemma4:e2b
if "%GEMMA_CONTEXT_SIZE%"=="" set GEMMA_CONTEXT_SIZE=8192
if "%GEMMA_TEMPERATURE%"=="" set GEMMA_TEMPERATURE=0.2

set UI_ENABLED=1
if "%YES_MODE%"=="1" set UI_ENABLED=0

set STEP_TOTAL=11
set STEP_CUR=0

call :banner
call :introanim
call :transition Opening setup
call :box Interactive First-Run

if "%YES_MODE%"=="0" (
  set /p DASHBOARD_PORT=Dashboard port [18890]: 
  if "%DASHBOARD_PORT%"=="" set DASHBOARD_PORT=18890

  set /p AGENT_TRIGGER=Agent trigger word [gemma]: 
  if "%AGENT_TRIGGER%"=="" set AGENT_TRIGGER=gemma

  set /p GEMMA_MODEL=Gemma model [gemma4:e2b]: 
  if "%GEMMA_MODEL%"=="" set GEMMA_MODEL=gemma4:e2b

  set /p GEMMA_CONTEXT_SIZE=Gemma context size [8192]: 
  if "%GEMMA_CONTEXT_SIZE%"=="" set GEMMA_CONTEXT_SIZE=8192

  set /p GEMMA_TEMPERATURE=Gemma temperature [0.2]: 
  if "%GEMMA_TEMPERATURE%"=="" set GEMMA_TEMPERATURE=0.2

  set /p ADMIN_USER=Admin username [admin]: 
  if "%ADMIN_USER%"=="" set ADMIN_USER=admin

  set /p ADMIN_PASS=Admin password - leave blank for auto-generated: 
) else (
  set ADMIN_USER=admin
  set ADMIN_PASS=
)

for /f "delims=0123456789" %%A in ("%DASHBOARD_PORT%") do (
  echo Invalid --port value. Must be numeric.
  exit /b 1
)
if %DASHBOARD_PORT% LSS 1024 (
  echo Invalid --port. Must be between 1024 and 65535.
  exit /b 1
)
if %DASHBOARD_PORT% GTR 65535 (
  echo Invalid --port. Must be between 1024 and 65535.
  exit /b 1
)

echo %GEMMA_MODEL% | findstr /C:":" >nul
if errorlevel 1 (
  echo Invalid --model value. Expected format like gemma4:e2b
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$t='%AGENT_TRIGGER%'; if($t -match '^[a-zA-Z0-9_-]{2,24}$'){exit 0}else{exit 1}" >nul 2>nul
if errorlevel 1 (
  echo Invalid --trigger value. Use 2-24 chars [a-zA-Z0-9_-]
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$c='%GEMMA_CONTEXT_SIZE%'; if($c -match '^[0-9]+$' -and [int]$c -ge 1024 -and [int]$c -le 131072){exit 0}else{exit 1}" >nul 2>nul
if errorlevel 1 (
  echo Invalid --context-size. Use integer between 1024 and 131072.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$t='%GEMMA_TEMPERATURE%'; [double]$v=0; if([double]::TryParse($t,[ref]$v) -and $v -ge 0 -and $v -le 2){exit 0}else{exit 1}" >nul 2>nul
if errorlevel 1 (
  echo Invalid --temperature. Use number between 0 and 2.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='%ADMIN_USER%'; if($u -match '^[a-zA-Z0-9_.-]{3,32}$'){exit 0}else{exit 1}" >nul 2>nul
if errorlevel 1 (
  echo Invalid admin username. Use 3-32 chars [a-zA-Z0-9_.-]
  exit /b 1
)

call :box Setup Summary
echo   Platform         : windows
echo   Dashboard port   : %DASHBOARD_PORT%
echo   Trigger          : %AGENT_TRIGGER%
echo   Gemma model      : %GEMMA_MODEL%
echo   Context size     : %GEMMA_CONTEXT_SIZE%
echo   Temperature      : %GEMMA_TEMPERATURE%
echo   Admin user       : %ADMIN_USER%

call :transition Running installation pipeline

call :tick Prerequisite checks
call :loading Prerequisite checks
where python >nul 2>nul || (echo Python 3.11+ is required & exit /b 1)

call :tick Python environment
call :loading Python environment
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat || (echo Failed to activate venv & exit /b 1)
python -m pip install --upgrade pip || (echo Failed to upgrade pip & exit /b 1)

call :tick Dependency install
call :loading Dependency install
pip install -r requirements.txt || (echo Failed to install Python deps & exit /b 1)

call :tick Ollama readiness
call :loading Ollama readiness
where ollama >nul 2>nul
if errorlevel 1 (
  echo Ollama not found. Attempting install via winget...
  where winget >nul 2>nul || (echo winget not found. Install Ollama manually: https://ollama.com/download/windows & exit /b 1)
  winget install Ollama.Ollama -e --accept-package-agreements --accept-source-agreements || (echo Ollama install failed. Install manually and rerun. & exit /b 1)
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo Starting Ollama in background...
  start "" /B ollama serve
  timeout /t 3 >nul
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo Ollama API not reachable on localhost:11434. Please start Ollama and rerun.
  exit /b 1
)

ollama pull %GEMMA_MODEL% || (echo Failed to pull model %GEMMA_MODEL% & exit /b 1)

call :tick Project directories
call :loading Project directories
if not exist app\minecraft_server\logs mkdir app\minecraft_server\logs
if not exist state mkdir state

call :tick Minecraft server jar
call :loading Minecraft server jar
if not exist app\minecraft_server\server.jar (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$m=Invoke-RestMethod 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'; $v=($m.versions|Where-Object {$_.id -eq $m.latest.release})[0]; $meta=Invoke-RestMethod $v.url; Invoke-WebRequest $meta.downloads.server.url -OutFile 'app/minecraft_server/server.jar'" || (echo Failed to download server.jar & exit /b 1)
)

call :tick Secure env generation
call :loading Secure env generation
if exist .env if "%FORCE_ENV%"=="0" (
  echo .env already exists. Keeping current values. Use --force-env to regenerate.
  goto runtime_config
)

set ARX_BIND_HOST=0.0.0.0
set ARX_BIND_PORT=%DASHBOARD_PORT%
set ARX_ADMIN_USER=%ADMIN_USER%
set ARX_ADMIN_PASS=%ADMIN_PASS%
set ARX_TRIGGER=%AGENT_TRIGGER%
set ARX_MODEL=%GEMMA_MODEL%
set ARX_CONTEXT_SIZE=%GEMMA_CONTEXT_SIZE%
set ARX_TEMPERATURE=%GEMMA_TEMPERATURE%
python scripts\generate_env.py --output .env || (echo Failed generating .env & exit /b 1)

:runtime_config
call :tick Runtime setup profile
call :loading Runtime setup profile
python -c "import json,os,pathlib;p=pathlib.Path('state/arx_config.json');p.parent.mkdir(parents=True,exist_ok=True);obj={'setup_completed':True,'agent_trigger':os.environ.get('ARX_TRIGGER','gemma'),'gemma_model':os.environ.get('ARX_MODEL','gemma4:e2b'),'gemma_context_size':int(os.environ.get('ARX_CONTEXT_SIZE','8192')),'gemma_temperature':float(os.environ.get('ARX_TEMPERATURE','0.2')),'gemma_max_reply_chars':220,'gemma_cooldown_sec':2.5};p.write_text(json.dumps(obj,indent=2),encoding='utf-8');print('Wrote state/arx_config.json')" || (echo Failed writing runtime config & exit /b 1)

call :tick Finalize installer
call :loading Finalize installer

call :box Install Complete
echo   Dashboard URL : http://localhost:%DASHBOARD_PORT%/
echo   Start command : call .venv\Scripts\activate.bat ^&^& uvicorn main:app --host 0.0.0.0 --port %DASHBOARD_PORT%
echo   Gemma trigger : %AGENT_TRIGGER%

if "%UI_ENABLED%"=="1" call :transition All done
exit /b 0

:banner
cls
echo.
echo  █████╗ ██████╗ ██╗  ██╗
echo ██╔══██╗██╔══██╗╚██╗██╔╝
echo ███████║██████╔╝ ╚███╔╝
echo ██╔══██║██╔══██╗ ██╔██╗
echo ██║  ██║██║  ██║██╔╝ ██╗
echo ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
echo.
echo +--------------------------------------------------------------+
echo ^| Agentic Runtime for eXecution ^| OpenClaw-style Setup      ^|
echo +--------------------------------------------------------------+
echo.
exit /b 0

:box
echo.
echo +--------------------------------------------------------------+
echo ^| %~1
echo +--------------------------------------------------------------+
exit /b 0

:introanim
if "%UI_ENABLED%"=="0" exit /b 0
echo [ARX] Initializing UI [#####.............................................]  10%%
powershell -NoProfile -Command "Start-Sleep -Milliseconds 70" >nul 2>nul
echo [ARX] Initializing UI [############......................................]  24%%
powershell -NoProfile -Command "Start-Sleep -Milliseconds 70" >nul 2>nul
echo [ARX] Initializing UI [###################...............................]  38%%
powershell -NoProfile -Command "Start-Sleep -Milliseconds 70" >nul 2>nul
echo [ARX] Initializing UI [##########################........................]  52%%
powershell -NoProfile -Command "Start-Sleep -Milliseconds 70" >nul 2>nul
echo [ARX] Initializing UI [#################################.................]  66%%
powershell -NoProfile -Command "Start-Sleep -Milliseconds 70" >nul 2>nul
echo [ARX] Initializing UI [########################################..........]  80%%
powershell -NoProfile -Command "Start-Sleep -Milliseconds 70" >nul 2>nul
echo [ARX] Initializing UI [##################################################] 100%%
exit /b 0

:transition
if "%UI_ENABLED%"=="0" (
  echo [ARX] %~1
  exit /b 0
)
setlocal EnableDelayedExpansion
set "msg=%~1"
for %%D in (. .. ...) do (
  echo [ARX] !msg!%%D
  powershell -NoProfile -Command "Start-Sleep -Milliseconds 110" >nul 2>nul
)
endlocal
exit /b 0

:tick
set /a STEP_CUR+=1
echo [%STEP_CUR%/%STEP_TOTAL%] %~1
exit /b 0

:loading
if "%UI_ENABLED%"=="0" exit /b 0
echo    ... %~1
powershell -NoProfile -Command "Start-Sleep -Milliseconds 120" >nul 2>nul
echo    [OK] %~1
exit /b 0
