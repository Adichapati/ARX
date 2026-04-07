# Windows E2E Test Runbook (ARX)

Use this to run a full end-to-end validation on Windows.

## 0) Prerequisites
- Windows 10/11
- PowerShell (Admin for winget installs)
- Python 3.11+
- Git
- Java 21+ (installer attempts to handle dependencies)

## 1) Get the code

If repo is published:
```powershell
git clone https://github.com/ORG_OR_USER/REPO_NAME.git
cd REPO_NAME
```

If you already downloaded source, just `cd` into project root.

## 2) Run installer (Windows path)

Preferred (PowerShell, best visuals + interactive option lists):
```powershell
.\install.ps1
```

Or via batch wrapper:
```powershell
.\install.bat
```

Non-interactive (recommended for repeatable test):
```powershell
.\install.ps1 -Yes -ForceEnv -Port 18890 -Trigger gemma -Model gemma4:e2b -ContextSize 12288 -Temperature 0.15
```

Expected outcomes:
- `.venv` created
- Ollama installed/running
- `gemma4:e2b` pulled
- `app\minecraft_server\server.jar` present
- `.env` generated

## 3) Start dashboard
```powershell
.\.venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 18890
```

Open in browser:
- http://localhost:18890

## 4) Test checklist (functional)
1. Login works
2. Start/Stop/Restart works
3. Runtime health shows statuses
4. First-run Gemma setup saves
5. Server properties save/reload works
6. OP/whitelist panel add/remove works (persist + API path)
7. Console send command works on Linux/tmux runtime; on native Windows this currently returns a clear "console passthrough unavailable" message
8. WebSocket logs stream and reconnect cleanly after refresh/network blip

## 5) Gemma safety checks
In Minecraft chat (as OP), trigger using `gemma` and verify:
- Placeholder command requests are rejected
- Blocked commands are refused
- Non-allowlisted commands are refused
- Targeted commands require own username
- Success-style response only after log observation

## 6) Troubleshooting
- Ollama missing model:
  ```powershell
  ollama pull gemma4:e2b
  ```
- Ollama not running:
  ```powershell
  ollama serve
  ```
- Recreate env:
  ```powershell
  .\install.bat --yes --force-env
  ```

## 7) GitHub installer path (no domain)
Use GitHub path until domain is available:
- Repo: `https://github.com/Adichapati/openclaw-dashboard-oneclick`
- Main fallback install.sh path:
  `https://raw.githubusercontent.com/Adichapati/openclaw-dashboard-oneclick/main/install.sh`
- Pinned tag format (recommended once tagged):
  `https://raw.githubusercontent.com/Adichapati/openclaw-dashboard-oneclick/vX.Y.Z/install.sh`

For Windows, clone the repo and run `install.bat` from the checkout.
