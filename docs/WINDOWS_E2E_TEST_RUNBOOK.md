# Windows End-to-End Test Runbook (ARX)

Use this runbook for a full Windows validation pass.

## 0) Prerequisites

- Windows 10/11
- PowerShell (Admin for dependency installs when needed)
- Internet access for first install/model pull

Notes:
- Installer provisions Python environment inside ARX runtime.
- Installer attempts Java and Ollama readiness automatically.

---

## 1) Clean test install (recommended)

PowerShell bootstrap command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://arxmc.studio/install.ps1 | iex"
```

Optional custom install location:

```powershell
$env:ARX_INSTALL_DIR = "D:\ARX"
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://arxmc.studio/install.ps1 | iex"
```

Expected default install path:

```text
%USERPROFILE%\ARX
```

---

## 2) Verify installer output

Expected artifacts in ARX root:

- `.venv\`
- `.env`
- `app\minecraft_server\server.jar`
- `state\arx_config.json`
- `scripts\arx_cli.py`

Expected launcher path:

```text
%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\arx.bat
```

---

## 3) Lifecycle validation

In a new PowerShell terminal:

```powershell
arx start
arx status
arx open
```

Expected:
- Dashboard reachable (default `http://localhost:18890/`)
- Minecraft service running
- Ollama service reachable

Shutdown path:

```powershell
arx shutdown
arx status
```

Expected after shutdown:
- Dashboard down
- Minecraft down
- Ollama down

---

## 4) Functional checklist

1. Login works with configured admin credentials.
2. Start/Stop/Restart actions behave correctly.
3. Runtime health/status panel updates correctly.
4. Config save/reload operations persist.
5. Player/OP management actions persist.
6. Log stream reconnects cleanly after refresh.
7. AI context update works:

```powershell
arx ai set-context 4096
arx restart
```

---

## 5) AI safety checks

From Minecraft chat (as OP), validate:

- Disallowed command requests are rejected.
- Placeholder-style target values are rejected.
- Non-OP users are guide/chat-only (no command execution).
- Successful execution messaging follows observed server feedback.

---

## 6) Troubleshooting quick fixes

If `arx` is not found:

- Restart terminal.
- Verify launcher exists at `%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\arx.bat`.

If Ollama model missing:

```powershell
ollama pull gemma4:e2b
```

If service state appears stuck:

```powershell
arx shutdown
arx start
```

If stopping server fails due to permissions:
- Run terminal as Administrator and retry.

---

## 7) Release source references

- Runtime repo: `https://github.com/Adichapati/ARX`
- Website artifacts: `https://arxmc.studio/`
- Release fallback: `https://github.com/Adichapati/ARX/releases`
