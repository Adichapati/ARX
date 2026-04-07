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

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $ok = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3; exit 0 } catch { exit 1 }"
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

python - <<PY
import base64, hashlib, secrets, pathlib, os

def hash_pw(p: str) -> str:
    iters = 120000
    salt = secrets.token_bytes(16)
    out = hashlib.pbkdf2_hmac('sha256', p.encode(), salt, iters)
    return f"pbkdf2_sha256${iters}${base64.b64encode(salt).decode()}${base64.b64encode(out).decode()}"

root = pathlib.Path('.').resolve()
admin_user = os.environ.get('ADMIN_USER', 'admin')
admin_pass = os.environ.get('ADMIN_PASS', '') or secrets.token_urlsafe(10)
session = secrets.token_urlsafe(32)
public = secrets.token_urlsafe(24)
content = f"""BIND_HOST=0.0.0.0
BIND_PORT={os.environ.get('DASHBOARD_PORT','18890')}
AUTH_USERNAME={admin_user}
AUTH_PASSWORD_HASH={hash_pw(admin_pass)}
SESSION_SECRET={session}
PUBLIC_READ_ENABLED=false
PUBLIC_READ_TOKEN={public}
MC_HOST=127.0.0.1
MC_PORT=25565
MC_TMUX_SESSION=mc_server_arx
GEMMA_ENABLED=true
GEMMA_OLLAMA_URL=http://localhost:11434/v1/chat/completions
GEMMA_OLLAMA_MODEL={os.environ.get('GEMMA_MODEL','gemma4:e2b')}
GEMMA_MAX_REPLY_CHARS=220
GEMMA_COOLDOWN_SEC=2.5
AGENT_TRIGGER={os.environ.get('AGENT_TRIGGER','gemma')}
GEMMA_CONTEXT_SIZE=8192
GEMMA_TEMPERATURE=0.2
"""
(root / '.env').write_text(content, encoding='utf-8')
print('Generated .env')
print(f'Admin username: {admin_user}')
print(f'Temporary admin password: {admin_pass}')
print('Change credentials after first login.')
PY

:finish
echo [ARX 8/8] Install complete.
echo Run dashboard: call .venv\Scripts\activate.bat ^&^& uvicorn main:app --host 0.0.0.0 --port %DASHBOARD_PORT%
