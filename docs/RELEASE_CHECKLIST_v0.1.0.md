# v0.1.0 Release Checklist

Owner: Sprake + Gemma Assistant
Target: First public alpha release of Gemma-Powered Minecraft Ops Dashboard

## Phase 0 — Repo and Release Hygiene

- [ ] Add `LICENSE` (MIT recommended)
- [ ] Add `SECURITY.md`
- [ ] Add `CONTRIBUTING.md`
- [ ] Add `CHANGELOG.md` with `v0.1.0` section
- [ ] Add issue templates (`bug`, `feature`, `installer failure`)
- [ ] Add PR template

Exit criteria:
- Repo root documents legal, security reporting, and contribution flow.

## Phase 1 — Installer Reliability

- [x] Make `install.sh` idempotent (safe to run twice)
- [x] Add `--yes` non-interactive mode
- [x] Add setup prompts: agent name, admin creds, RAM, port, MOTD, max players, difficulty, OP list, trigger word, local model context size/tuning defaults
- [x] Validate all user inputs before writing `.env`
- [x] Emit clear post-install summary with next commands
- [x] Implement OS-specific Ollama install flows (Linux/macOS/Windows paths) and verify service availability before completing setup
- [x] Improve failure messages + remediation steps

Exit criteria:
- Clean machine install works with one command.
- Re-running installer does not break existing setup.

## Phase 2 — Runtime and Dashboard Completeness

- [ ] Add runtime health card (Ollama/tmux/java/server ping)
- [ ] Add first-run setup/tuning UI for Gemma context size and related local inference settings
- [ ] Add editable key `server.properties` controls in dashboard
- [ ] Add OP/whitelist management panel
- [ ] Add better unauth/error state UX in frontend
- [ ] Ensure websocket reconnect and buffer limits are stable

Exit criteria:
- User can fully operate server lifecycle and key settings from browser.

## Phase 3 — Gemma Assistant Safety Gate

- [ ] Implement strict command allowlist templates for OP actions
- [ ] Keep regex denylist as second safety layer
- [ ] Reject unresolved placeholders (`<player>`, `{player}` etc.)
- [ ] Require OP identity match before any command execution
- [ ] Confirm command result from `latest.log` before success acknowledgement
- [ ] Add cooldown/rate limits and anti-spam
- [ ] Add strict local-model health handling when Ollama/model unavailable (clear errors and guided recovery, no Wilson fallback semantics)

Exit criteria:
- Blocked commands never reach `tmux send-keys`.
- Gemma Assistant does not claim success without observable evidence.

## Phase 4 — Distribution and Trust

- [ ] Replace placeholder installer domain in README once domain exists
- [ ] Add GitHub release workflow (tag -> build -> release artifacts)
- [ ] Publish checksums (`sha256`) for installer/release assets
- [ ] Pin install script to versioned release artifacts (not mutable main)
- [ ] Add verification instructions in README

Exit criteria:
- One-liner install points to verifiable versioned artifacts.

## Phase 5 — QA Launch Gate

- [ ] Fresh Ubuntu VM install test
- [ ] Reinstall/idempotency test
- [ ] Upgrade test (`v0.0.x` -> `v0.1.0`)
- [ ] Auth test: lockout/session route protection
- [ ] Gemma Assistant safety regression suite
- [ ] Dashboard smoke test: start/stop/restart/send command/live logs
- [ ] Installer dry-run log capture and review

Exit criteria:
- All gate tests pass with documented steps.

## Phase 6 — Release Execution

- [ ] Tag release: `v0.1.0`
- [ ] Publish release notes with known limitations
- [ ] Mark platform support explicitly (Linux + Windows official, macOS best effort)
- [ ] Announce install command + quickstart docs
- [ ] Open `v0.1.1` tracking milestone

Exit criteria:
- Public users can install, run, and recover using docs only.
