# Extra Notes / Clarifications (Working Draft)

These notes align implementation with the PRD + architecture and reduce ambiguity for one-click deployment.

## Deployment assumptions
- Target OS for V1 one-click: Linux first (Ubuntu/Debian), Windows script as best-effort parity.
- App is self-contained under project root, with managed Minecraft server folder at `app/minecraft_server/`.
- No external DB; all mutable state in `state/*.json`.

## Security baseline (MVP)
- Session middleware secret must be generated during install.
- Login must use hashed passwords (PBKDF2-SHA256), never plaintext in `.env`.
- Public read-only URL (if enabled) should be tokenized and optional.
- Gemma Assistant command output must pass regex denylist before `tmux send-keys`.

## Gemma Assistant/Ollama requirements
- Default endpoint: `http://localhost:11434/v1/chat/completions`
- Default model: `gemma4:e2b`
- Fallback behavior when Ollama/model unavailable: Gemma Assistant returns chat-only status message; no command execution.

## Installer scope for Phase 1
- `install.sh` should:
  - verify Python 3.11+
  - create `.venv`
  - install `requirements.txt`
  - install/check `tmux`, `java`, `curl`, `unzip`
  - install/check Ollama and pull `gemma4:e2b`
  - download official vanilla `server.jar`
  - write `.env` with secure defaults + generated secrets
- Optional: emit and install systemd service file (`openclaw-dashboard.service`).

## Suggested initial milestones
1. Scaffold app + services + state files.
2. Implement server lifecycle control and log diff feed.
3. Implement auth + websocket ticketing + dashboard shell.
4. Implement Gemma Assistant (ops routing, tool JSON, safety denylist, action-observation loop).
5. Build one-click installer and docs.
6. Smoke test on clean machine.
