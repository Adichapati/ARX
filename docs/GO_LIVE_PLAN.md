# Gemma Minecraft Ops Dashboard — Go-Live Plan

> Goal: Ship an OpenClaw-style one-command installer + guided setup + browser dashboard, while keeping deployment isolated from existing environments.

## Scope
- V1 official support: Linux + Windows (macOS best effort)
- Local-first Ollama + Gemma (`gemma4:e2b`)
- Vanilla Minecraft server only
- File-based state (no DB)

## Release Strategy
- Repository: separate from current setup (`openclaw-dashboard-oneclick`)
- Delivery modes:
  1. Direct GitHub install command (immediate)
  2. Website-hosted installer URL (after domain is ready)

## Stage 0 — Packaging Baseline (Must Have)

### Tasks
1. Add project metadata and governance files:
   - `LICENSE`
   - `SECURITY.md`
   - `CONTRIBUTING.md`
   - `CHANGELOG.md`
2. Add semantic versioning policy (`v0.1.0`, `v0.2.0`, etc.)
3. Add release notes template under `.github/`

### Acceptance Criteria
- Fresh user can understand trust, support, and contribution policy from repo root.
- First tagged release is reproducible.

## Stage 1 — Installer + Setup Wizard Hardening (Must Have)

### Tasks
1. Convert install flow into explicit phases with idempotency checks.
2. Add interactive first-run setup prompts:
   - Agent name
   - Admin username/password
   - RAM limits (Xms/Xmx)
   - Port + MOTD + max players + difficulty
   - OP seed list
3. Add non-interactive mode (`--yes`, env overrides) for automation.
4. Add post-install summary with exact next commands.

### Acceptance Criteria
- Running installer twice does not corrupt config/state.
- User can complete setup without editing files manually.
- `.env` and startup scripts are fully generated and valid.

## Stage 2 — Dashboard + Runtime Ops Completeness (Must Have)

### Tasks
1. Finalize dashboard controls for start/stop/restart and command send.
2. Add server config editor for key `server.properties` values.
3. Add status/health panel (Ollama, tmux session, java process, server ping).
4. Improve empty/error states and recovery guidance.

### Acceptance Criteria
- User can operate server lifecycle from browser only.
- User can diagnose common failures directly from dashboard.

## Stage 3 — Gemma Assistant Safety and Reliability (Must Have)

### Tasks
1. Move from permissive generation to command allowlist templates.
2. Keep regex denylist as second-layer guardrail.
3. Enforce OP-only execution with explicit identity checks.
4. Add action-observation confirmation before success messages.
5. Add rate limits/cooldowns and robust failure-handling messages (without any Wilson compatibility path).

### Acceptance Criteria
- Blocked commands never reach `tmux send-keys`.
- Successful command announcements only happen after log confirmation or explicit fallback text.
- Non-OP users never execute tool commands.

## Stage 4 — OpenClaw-Style Distribution (Must Have for public launch)

### Tasks
1. Provide canonical install command in README:
   - Placeholder now: `https://INSTALLER_DOMAIN_PLACEHOLDER/install.sh`
2. Add GitHub release artifact pipeline (tag -> release -> checksums).
3. Add integrity verification in installer (`sha256`).
4. Prepare website copy section with OS-specific install commands.

### Acceptance Criteria
- One command installs from clean machine.
- Installer points to versioned release artifact, not mutable main branch.
- Checksum verification documented and functional.

## Stage 5 — QA and Launch Gate (Must Have)

### Test Matrix
1. Clean VM install (Ubuntu) from one-liner.
2. Re-run installer (idempotency).
3. Upgrade scenario (old -> new version).
4. Gemma Assistant safety suite:
   - `/stop`, `/deop`, placeholder commands, malformed JSON.
5. Auth suite:
   - lockout, session timeout, unauthenticated route denial.

### Acceptance Criteria
- All launch-gate checks pass on documented platform.
- README quickstart works exactly as written.

## Stage 6 — Nice-to-Haves (Post V1)
- Windows parity installer hardening
- macOS support
- Optional remote status tunnel
- Multi-server profiles
- Plugin ecosystem support

## Immediate Next Actions
1. Finalize README for current placeholder domain + GitHub-first install path.
2. Add governance/release docs.
3. Implement interactive setup wizard prompts in installer, including OS-specific Ollama install and model pull checks.
4. Build safety regression test script for Gemma Assistant command routing.
5. Add first-run dashboard setup UI to tune local model context size and related inference settings.
