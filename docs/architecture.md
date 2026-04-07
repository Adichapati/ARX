# System Architecture

## 1. Tech Stack Overview
* **Backend:** Python 3.11+, FastAPI, Uvicorn.
* **Frontend:** Server-rendered HTML, Vanilla JS, CSS, WebSockets (No build step).
* **AI Engine:** Local Ollama (Gemma 4 E2B).
* **State Management:** File system (`.json` state files, `server.properties`, `latest.log`).
* **Environment:** `.env` loaded via `python-dotenv`.

## 2. Directory Structure (Proposed)
```text
/project_root
├── /dashboard
│   ├── app.py                  # FastAPI routes & WebSocket loops
│   ├── ui.py                   # HTML template definitions
│   └── /services
│       ├── server_service.py   # tmux session mgmt & send-keys execution
│       ├── config_service.py   # server.properties & EULA management
│       ├── log_service.py      # latest.log byte-offset diffing
│       └── op_assist_service.py# Gemma 4 LLM API calls & safety routing
├── /app
│   └── /minecraft_server       # Self-contained server directory
│       ├── server.jar          # Vanilla software
│       └── /logs               # Contains latest.log
├── /state
│   ├── known_players.json
│   └── op_assist_state.json    # Sliding context window backups
├── .env
├── requirements.txt
└── install.sh / install.bat
```

## 3.1. The AI Action Loop
1. LogService detects a chat event in latest.log: `<Steve> Gemma Assistant, give me a sword`.
2. LogService pushes string to `op_assist_service.py`.
3. `op_assist_service.py` checks `known_players.json` -> Steve is an OP.
4. Payload formatted with JSON tools and sent to `http://localhost:11434` (Gemma 4 E2B).
5. Gemma responds with structured JSON: `{\"function\":\"execute_command\",\"command\":\"/give Steve diamond_sword 1\"}`.
6. Python parses JSON, checks Regex blocklist -> PASS.
7. ServerService injects command: `tmux send-keys -t mc_server \"/give Steve diamond_sword 1\" C-m`.
8. LogService detects result: `[Server] Gave Diamond Sword to Steve`.
9. Result fed back to Gemma to close the action-observation loop.

## 3.2. The Web UI Log Feed
1. Browser opens `/ws` connection.
2. FastAPI WebSocket loop requests `LogService.diff_from(offset)` every ~2 seconds.
3. LogService reads raw bytes from `latest.log`.
4. Sanitized text chunks sent over WebSocket to client.
5. Vanilla JS appends text directly to `<pre id=\"console-window\">` and auto-scrolls to bottom.
