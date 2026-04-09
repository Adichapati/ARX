# ARX Architecture Overview

## 1) Runtime Stack

- Backend: Python 3.11+, FastAPI, Uvicorn
- Frontend: server-rendered HTML + vanilla JS + WebSockets
- AI runtime: local Ollama (`gemma4:e2b` default)
- State: local filesystem (`state/*.json`, `.env`, server files)

ARX is designed to run locally with minimal external dependencies after setup.

---

## 2) Core Directory Layout

```text
ARX/
├── dashboard/
│   ├── app.py
│   ├── ui.py
│   ├── auth.py
│   └── services/
│       ├── server_service.py
│       ├── config_service.py
│       ├── op_assist_service.py
│       ├── player_service.py
│       ├── world_service.py
│       └── ...
├── scripts/
│   ├── arx_cli.py
│   ├── generate_env.py
│   └── start_dashboard.sh
├── app/minecraft_server/
│   ├── server.jar
│   ├── start.sh
│   └── logs/
├── state/
│   ├── arx_config.json
│   ├── known_players.json
│   └── whitelist_players.json
├── install.sh
├── install.ps1
└── main.py
```

---

## 3) Service Control Model

`arx` CLI orchestrates lifecycle control:

- Dashboard process
- Minecraft process
- Ollama process
- Optional Playit process

Typical flow:

1. `arx start` brings up required services.
2. Dashboard exposes operational APIs + websocket log streams.
3. `arx status` reflects current service availability.
4. `arx shutdown` performs full stop of managed services.

---

## 4) AI Command Path (safety-oriented)

High-level pipeline:

1. Chat/log events are parsed.
2. Request context is sent to local Gemma runtime via Ollama.
3. Proposed actions are validated in backend safeguards.
4. Only allowed commands are forwarded to server control channel.
5. Execution outcome is observed and surfaced back through logs/UI.

Safeguard themes:
- explicit validation before execution
- OP-oriented command boundaries
- rejection of unresolved/unsafe placeholders

---

## 5) Installer Model

### Linux/macOS

`install.sh` handles:
- prerequisite checks
- local virtual environment setup
- dependency install
- Ollama/model readiness
- runtime config generation
- global `arx` launcher setup

### Windows

`install.ps1` supports bootstrap mode:
- downloads runtime bundle when launched remotely
- extracts to install directory (default `%USERPROFILE%\ARX`)
- re-enters full installer from extracted runtime
- installs `arx.bat` launcher in WindowsApps path

---

## 6) State and Configuration

- `.env` stores runtime configuration and secrets.
- `state/arx_config.json` stores installer/runtime defaults.
- server runtime files remain under `app/minecraft_server/`.

This keeps ARX portable and easy to reason about during operations and troubleshooting.
