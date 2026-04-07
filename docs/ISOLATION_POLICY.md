# ARX Isolation Policy

This project must never affect the existing dashboard/server stack.

Rules:
1. Use only `/root/openclaw-dashboard-oneclick` for ARX development.
2. Do not bind ARX to existing production dashboard port (`18789`).
3. Default ARX dashboard port is `18890`.
4. Use dedicated tmux session (`mc_server_arx`) for ARX-managed server.
5. Any test automation must target ARX paths/ports only.
6. Do not modify files under `/root/openclaw-dashboard` during ARX development.

Verification before running ARX tests:
- Confirm ARX binds to port `18890`.
- Confirm no commands target `mcserver` session used by existing stack.
- Confirm ARX `.env` is local to ARX root.
