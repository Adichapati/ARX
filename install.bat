@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

echo [ARX 1/6] Checking Python...
where python >nul 2>nul || (echo Python 3.11+ is required & exit /b 1)

echo [ARX 2/6] Creating venv...
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip

echo [ARX 3/6] Installing dependencies...
pip install -r requirements.txt

echo [ARX 4/6] Preparing directories...
if not exist app\minecraft_server\logs mkdir app\minecraft_server\logs
if not exist state mkdir state

echo [ARX 5/6] Downloading latest server.jar via PowerShell...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$m=Invoke-RestMethod 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'; $v=($m.versions|Where-Object {$_.id -eq $m.latest.release})[0]; $meta=Invoke-RestMethod $v.url; Invoke-WebRequest $meta.downloads.server.url -OutFile 'app/minecraft_server/server.jar'"

echo [ARX 6/6] Writing starter .env if missing...
if not exist .env (
  > .env echo BIND_HOST=0.0.0.0
  >>.env echo BIND_PORT=18890
  >>.env echo AUTH_USERNAME=admin
  >>.env echo AUTH_PASSWORD_HASH=
  >>.env echo SESSION_SECRET=replace_me
  >>.env echo PUBLIC_READ_ENABLED=false
  >>.env echo PUBLIC_READ_TOKEN=replace_me
  >>.env echo MC_HOST=127.0.0.1
  >>.env echo MC_PORT=25565
  >>.env echo MC_TMUX_SESSION=mc_server_arx
  >>.env echo GEMMA_ENABLED=true
  >>.env echo GEMMA_OLLAMA_URL=http://localhost:11434/v1/chat/completions
  >>.env echo GEMMA_OLLAMA_MODEL=gemma4:e2b
  >>.env echo GEMMA_MAX_REPLY_CHARS=220
  >>.env echo GEMMA_COOLDOWN_SEC=2.5
  >>.env echo AGENT_TRIGGER=gemma
  >>.env echo GEMMA_CONTEXT_SIZE=8192
  >>.env echo GEMMA_TEMPERATURE=0.2
)

echo Install complete.
echo Run dashboard: call .venv\Scripts\activate.bat ^&^& uvicorn main:app --host 0.0.0.0 --port 18890
