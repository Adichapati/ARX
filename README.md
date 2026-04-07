# ARX — Agentic Runtime for eXecution

```text
 ___  ________   __
 / _ \ | ___ \ \ / /
/ /_\ \| |_/ /\ V /
|  _  ||    / /   \
| | | || |\ \/ /^\ \
\_| |_/\_| \_\/   \/
```

Local-first, one-click deployable Minecraft server dashboard with an integrated Gemma assistant (`gemma4:e2b`) running via local Ollama.

## Isolation Guarantee (Important)
ARX development/testing is isolated from your existing dashboard/server:
- Separate project root: `/root/openclaw-dashboard-oneclick`
- Separate default dashboard port: `18890` (not `18789`)
- Separate tmux session default: `mc_server_arx`
- Separate installer/runtime scripts

## Supported Platforms (v0.1.0)
- Official: Linux + Windows
- Best effort: macOS

Note: native Windows runtime now supports installer/dashboard/server lifecycle. Interactive console passthrough (tmux-style send-keys) is still Linux-first and currently returns a clear unavailable message on Windows.

## Vision
OpenClaw-style onboarding:
- User copies one install command
- Runs setup wizard
- Opens dashboard in browser
- Manages server + local Gemma assistant safely

## One-Command Install


Release-pinned installer (recommended for production):

```bash
curl -fsSL https://raw.githubusercontent.com/ORG_OR_USER/REPO_NAME/vX.Y.Z/install.sh | bash
```

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
# or non-interactive:
./install.sh --yes --force-env --port 18890 --trigger gemma --model gemma4:e2b --context-size 12288 --temperature 0.15
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
2. Run full terminal end-to-end validation pass.
3. Iterate fixes from test results.
4. Tag and publish v0.1.0 release.


## Verification
- Release checksum workflow: `.github/workflows/release.yml`
- Local artifact/checksum generator: `scripts/generate_release_artifacts.sh`
- Verification guide: `docs/RELEASE_VERIFICATION.md`
