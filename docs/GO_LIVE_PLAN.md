# ARX Go-Live Plan

Goal: Ship a production-grade one-command installer + guided setup + browser dashboard.

## Scope
- V1 official support: Linux + Windows (macOS best effort)
- Local-first Ollama + Gemma (`gemma4:e2b`)
- Vanilla Minecraft server baseline
- File-based local state (no external DB required)

## Release Strategy
- Canonical runtime repository: `https://github.com/Adichapati/ARX`
- Delivery modes:
  1. GitHub release artifacts
  2. Website-hosted installer endpoints (`arxmc.studio`)

## Stage 0 — Packaging Baseline

### Tasks
1. Keep repository governance files current:
   - `LICENSE`
   - `SECURITY.md`
   - `CONTRIBUTING.md`
   - `CHANGELOG.md`
2. Maintain semantic versioning policy.
3. Keep release notes templates under `.github/` current.

### Acceptance
- Fresh user can understand trust/support/contribution policy from repo root.
- Tagged release is reproducible.

## Stage 1 — Installer + Setup Hardening

### Tasks
1. Keep install phases explicit and idempotent.
2. Keep first-run setup prompts clear and validated.
3. Preserve non-interactive mode (`--yes`, env overrides).
4. Keep post-install summary and next-step commands accurate.

### Acceptance
- Running installer twice does not corrupt config/state.
- Setup succeeds without manual file edits.

## Stage 2 — Runtime Ops Completeness

### Tasks
1. Dashboard controls for start/stop/restart and command dispatch.
2. Config editor for key `server.properties` values.
3. Health panel (Ollama, tmux, java process, server ping).
4. Clear recovery guidance for common failures.

### Acceptance
- Core lifecycle can be run from dashboard and CLI.
- Common failures are diagnosable through UI/logs.

## Stage 3 — Assistant Safety and Reliability

### Tasks
1. Enforce command allowlist + denylist guardrails.
2. Enforce OP-only execution boundaries.
3. Require action/observation confirmation before success messaging.
4. Keep rate limits/cooldowns and robust failure messages.

### Acceptance
- Blocked commands never reach server execution channel.
- Non-OP users cannot execute privileged actions.

## Stage 4 — Distribution + Integrity

### Tasks
1. Keep canonical install commands current in README and website.
2. Maintain GitHub release pipeline and checksums.
3. Keep checksum verification documentation up to date.
4. Keep website install docs aligned with shipped artifacts.

### Acceptance
- One command installs from clean machine.
- Installer artifacts are versioned and verifiable.

## Stage 5 — QA Launch Gate

### Test Matrix
1. Clean VM install (Linux)
2. Clean VM install (Windows)
3. Re-run installer idempotency
4. Upgrade scenario (old -> new)
5. Assistant safety checks
6. Auth checks (lockout/session/route protection)

### Acceptance
- Launch-gate checks pass on supported platforms.
- README quickstart works exactly as written.

## Stage 6 — Post-V1 (Nice to Have)
- Windows further hardening
- macOS polish
- Optional remote status channel
- Multi-server profiles
- Plugin ecosystem improvements
