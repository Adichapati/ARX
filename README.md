# ARX — Agentic Runtime for eXecution

```text
 ___  ________   __
 / _ \ | ___ \ \ / /
/ /_\ \| |_/ /\ V /
|  _  ||    / /   | | | || |\ \/ /^\ \_| |_/\_| \_\/   \/
```

Local-first, one-click deployable Minecraft server dashboard with an integrated Gemma assistant (`gemma4:e2b`) running via local Ollama.

## Isolation Guarantee (Important)
ARX development/testing is isolated from your existing dashboard/server:
- Separate project root: `/root/openclaw-dashboard-oneclick`
- Separate default dashboard port: `18890` (not `18789`)
- Separate tmux session default: `mc_server_arx`
- Separate installer/runtime scripts

## Vision
OpenClaw-style onboarding:
- User copies one install command
- Runs setup wizard
- Opens dashboard in browser
- Manages server + local Gemma assistant safely

## One-Command Install (Placeholders for now)

Website-hosted installer (future domain):

```bash
curl -fsSL https://INSTALLER_DOMAIN_PLACEHOLDER/install.sh | bash
```

GitHub-direct fallback (until domain is live):

```bash
curl -fsSL https://raw.githubusercontent.com/ORG_OR_USER/REPO_NAME/main/install.sh | bash
```

## Local Dev / Manual Install

```bash
cd /root/openclaw-dashboard-oneclick
./install.sh
./scripts/start_dashboard.sh
```

Open:
- Private dashboard: `http://<host>:18890/`

## Tech Stack
- Python 3.11+
- FastAPI + Uvicorn
- Vanilla JS + WebSockets
- Ollama local endpoint (`/v1/chat/completions`)
- Gemma model: `gemma4:e2b`
- File-based state (`state/*.json`, `latest.log`, `server.properties`)

## Planning & Launch Docs
- PRD: `docs/prd.md`
- Architecture: `docs/architecture.md`
- Go-live plan: `docs/GO_LIVE_PLAN.md`
- Stage plan: `docs/STAGE_PLAN.md`
- v0.1.0 checklist: `docs/RELEASE_CHECKLIST_v0.1.0.md`
- GitHub issue backlog: `docs/GITHUB_BACKLOG_v0.1.0.md`
- Gemma naming refactor plan: `docs/GEMMA_NOMENCLATURE_REFACTOR_PLAN.md`

## What’s Next
1. Replace installer domain placeholder with real domain.
2. Add release pipeline + checksums.
3. Harden installer wizard + idempotency + OS-specific Ollama setup verification.
4. Add first-run Gemma setup UI for context-size and local inference tuning.
5. Finalize Gemma assistant safety regression tests.
6. Publish v0.1.0 release.
