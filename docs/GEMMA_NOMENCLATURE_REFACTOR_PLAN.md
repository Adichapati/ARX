# Gemma Nomenclature Refactor Plan

Goal: remove all remaining Wilson naming from code/env/runtime UX with no Wilson compatibility layer in public release.

## Why
- Product branding is Gemma-first (`gemma4:e2b` via Ollama).
- Consistent naming reduces onboarding confusion.
- Public releases must be Gemma-only to avoid confusing users with internal Wilson naming.

## Scope
- Python config/env keys
- OP assistant service prompts and triggers
- UI copy
- Install scripts (`install.sh`, `install.bat`)
- Docs and examples

## Rename Map

Primary names (new):
- `GEMMA_ENABLED`
- `GEMMA_OLLAMA_URL`
- `GEMMA_OLLAMA_MODEL`
- `GEMMA_MAX_REPLY_CHARS`
- `GEMMA_COOLDOWN_SEC`

Legacy names:
- None for public release (Gemma-only config surface).

## Implementation Strategy

### Step 1 — Config Gemma-only layer
In `dashboard/config.py`:
- Use only `GEMMA_*` keys for assistant configuration.
- Remove any `WILSON_*` reads.
- Add explicit startup validation error if required `GEMMA_*` values are invalid.

Acceptance:
- App boots with Gemma-only naming and rejects unknown legacy key paths.

### Step 2 — Service + UI naming updates
In `dashboard/services/op_assist_service.py` and `dashboard/ui.py`:
- Rename variable imports to `GEMMA_*` constants.
- Replace text outputs like `say Wilson:` with `say Gemma:`.
- Replace system prompt identity from Wilson -> Gemma Assistant.
- Keep chat trigger term configurable (see Step 4).

Acceptance:
- In-game and dashboard text consistently use Gemma naming.

### Step 3 — Installer output updates (Gemma + Ollama mandatory)
In `install.sh` and `install.bat`:
- Emit `GEMMA_*` env vars in generated `.env`.
- Include OS-specific Ollama setup and model pull for `gemma4:e2b`.
- Fail setup with clear remediation if Ollama install/start/model pull fails.

Acceptance:
- Fresh install uses only `GEMMA_*` keys.
- Ollama + `gemma4:e2b` is installed or user gets explicit actionable error.

### Step 4 — Trigger word decoupling
Add configurable trigger in `.env`:
- `AGENT_TRIGGER=gemma`

In assistant loop:
- Detect trigger from config value instead of hardcoded `wilson`.

Acceptance:
- User can change trigger without code edits.

### Step 5 — UI-guided runtime setup and tuning
- Add first-run setup page in dashboard UI for Gemma/Ollama settings.
- Include local context tuning controls (e.g., context window/token limits, prompt profile, cooldown).
- Persist settings to local config safely and validate values.

Acceptance:
- User can complete and adjust Gemma setup from UI without manual file edits.

## Test Plan
- Unit: config loads with only `GEMMA_*`.
- Unit: startup fails fast when required Gemma config values are invalid.
- Unit: trigger matching uses `AGENT_TRIGGER`.
- Integration: installer performs OS-appropriate Ollama installation path.
- Integration: installer ensures `gemma4:e2b` is pulled.
- Smoke: install script generates valid `.env` and app starts.
- Smoke: in-game `gemma` trigger runs assistant path.
- UI smoke: first-run setup page can change context/tuning values and persist them.

## Rollout
- v0.1.0-alpha: Gemma-only naming and installer path.
- No Wilson fallback in public release.
