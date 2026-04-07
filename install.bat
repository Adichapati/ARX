@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

set YES_MODE=0
set FORCE_ENV=0
set DASHBOARD_PORT=
set AGENT_TRIGGER=
set GEMMA_MODEL=

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
echo Unknown flag: %~1
exit /b 1

:args_done
if "%DASHBOARD_PORT%"=="" set DASHBOARD_PORT=18890
if "%AGENT_TRIGGER%"=="" set AGENT_TRIGGER=gemma
if "%GEMMA_MODEL%"=="" set GEMMA_MODEL=gemma4:e2b

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

echo [ARX 1/8] Checking Python...
where python >nul 2>nul || (echo Python 3.11+ is required & exit /b 1)

echo [ARX 2/8] Creating venv...
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip

echo [ARX 3/8] Installing dependencies...
pip install -r requirements.txt || (echo Failed to install Python deps & exit /b 1)

echo [ARX 4/8] Ensuring Ollama + model...
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

echo [ARX 5/8] Preparing directories...
if not exist app\minecraft_server\logs mkdir app\minecraft_server\logs
if not exist state mkdir state

echo [ARX 6/8] Downloading latest server.jar if missing...
if not exist app\minecraft_server\server.jar (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$m=Invoke-RestMethod 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'; $v=($m.versions|Where-Object {$_.id -eq $m.latest.release})[0]; $meta=Invoke-RestMethod $v.url; Invoke-WebRequest $meta.downloads.server.url -OutFile 'app/minecraft_server/server.jar'"
)

echo [ARX 7/8] Writing .env if needed...
if exist .env if "%FORCE_ENV%"=="0" (
  echo .env already exists. Keeping current values. Use --force-env to regenerate.
  goto finish
)

if "%YES_MODE%"=="0" (
  set /p ADMIN_USER=Admin username [admin]: 
  if "%ADMIN_USER%"=="" set ADMIN_USER=admin
) else (
  set ADMIN_USER=admin
)

if "%YES_MODE%"=="0" (
  set /p ADMIN_PASS=Admin password (leave blank for auto-generated): 
) else (
  set ADMIN_PASS=
)

if "%ADMIN_PASS%"=="" set ADMIN_PASS=AutoGenPleaseChange
set ARX_TMP_PY=%TEMP%\arx_env_gen_%RANDOM%%RANDOM%.py
(
  echo import base64, hashlib, secrets, pathlib, os
  echo def hash_pw(p):
  echo ^    iters = 120000
  echo ^    salt = secrets.token_bytes(16)
  echo ^    out = hashlib.pbkdf2_hmac('sha256', p.encode(), salt, iters)
  echo ^    return f"pbkdf2_sha256${iters}${base64.b64encode(salt).decode()}${base64.b64encode(out).decode()}"
  echo root = pathlib.Path('.').resolve()
  echo admin_user = os.environ.get('ADMIN_USER', 'admin')
  echo admin_pass = os.environ.get('ADMIN_PASS', '') or secrets.token_urlsafe(10)
  echo session = secrets.token_urlsafe(32)
  echo public = secrets.token_urlsafe(24)
  echo content = f"""BIND_HOST=0.0.0.0
  echo BIND_PORT={os.environ.get('DASHBOARD_PORT','18890')}
  echo AUTH_USERNAME={admin_user}
  echo AUTH_PASSWORD_HASH={hash_pw(admin_pass)}
  echo SESSION_SECRET={session}
  echo PUBLIC_READ_ENABLED=false
  echo PUBLIC_READ_TOKEN={public}
  echo MC_HOST=127.0.0.1
  echo MC_PORT=25565
  echo MC_TMUX_SESSION=mc_server_arx
  echo GEMMA_ENABLED=true
  echo GEMMA_OLLAMA_URL=http://localhost:11434/v1/chat/completions
  echo GEMMA_OLLAMA_MODEL={os.environ.get('GEMMA_MODEL','gemma4:e2b')}
  echo GEMMA_MAX_REPLY_CHARS=220
  echo GEMMA_COOLDOWN_SEC=2.5
  echo AGENT_TRIGGER={os.environ.get('AGENT_TRIGGER','gemma')}
  echo GEMMA_CONTEXT_SIZE=8192
  echo GEMMA_TEMPERATURE=0.2
  echo """
  echo (root / '.env').write_text(content, encoding='utf-8')
  echo print('Generated .env')
  echo print(f'Admin username: {admin_user}')
  echo print(f'Temporary admin password: {admin_pass}')
  echo print('Change credentials after first login.')
) > "%ARX_TMP_PY%"

python "%ARX_TMP_PY%" || (echo Failed generating .env & del "%ARX_TMP_PY%" & exit /b 1)
del "%ARX_TMP_PY%" >nul 2>nul

:finish
echo [ARX 8/8] Install complete.
echo Run dashboard: call .venv\Scripts\activate.bat ^&^& uvicorn main:app --host 0.0.0.0 --port %DASHBOARD_PORT%
