# ARX CLI/TUI Overhaul + Underground ASCII Branding Spec

Status: Draft (implementation-ready)
Owner: ARX
Scope: Terminal UX only (README + installer + CLI/TUI). Web dashboard layout stays clean.

---

## 1) Goals

1. Bring the Roy SAC-style underground block aesthetic into ARX branding.
2. Ship a modern animated TUI experience (clean, reactive, polished).
3. Keep full backward compatibility for existing `arx` commands.
4. Preserve cross-platform behavior (Linux + Windows official, macOS best effort).

---

## 2) Product Decisions

### 2.1 Where underground ASCII should appear

Use in terminal-only touchpoints:
- README hero banner
- Linux/macOS installer intro (`install.sh`)
- Windows installer intro (`install.ps1`)
- New `arx tui` full-screen mode
- Optional banner in classic `arx help` and `arx status`

Do NOT inject heavy ASCII into:
- Web dashboard UI pages
- API responses
- logs

### 2.2 Style packs

Ship 3 rendering-safe variants:
- `underground_dos` (CP437-inspired / legacy block look)
- `underground_unicode` (modern Unicode block fallback)
- `minimal_ascii` (plain safe fallback)

Runtime selects the best variant automatically, with user override.

### 2.3 New command surface

Add:
- `arx tui` (launch full-screen modern TUI)
- `arx style set <underground|minimal|off>`
- `arx style preview [name]`
- `arx style status`

Existing commands remain unchanged.

---

## 3) Architecture

## 3.1 New modules

Create:
- `scripts/ui/__init__.py`
- `scripts/ui/style_engine.py` (style resolution + fallback)
- `scripts/ui/ascii_assets.py` (ASCII art + animation frames)
- `scripts/ui/terminal_caps.py` (unicode/color/width detection)
- `scripts/arx_tui.py` (Textual app entrypoint)

Modify:
- `scripts/arx_cli.py` (new `tui` and `style` commands)
- `install.sh` (style-based installer banner)
- `install.ps1` (style-based installer banner)
- `requirements.txt` (add TUI libs)

Optional state file:
- `state/arx_ui.json` (persist user style choice)

---

## 3.2 Dependency plan

Add Python deps:
- `rich>=13.7`
- `textual>=0.70`

Reason:
- Rich: fast color + non-fullscreen rendering
- Textual: modern, animated, responsive TUI framework

Fallback behavior:
- if Textual import fails, `arx tui` prints install hint and exits with code 1
- classic `arx` commands continue normally

---

## 4) UX Design (Modern TUI)

## 4.1 Layout

Top bar:
- ARX logo (style pack)
- environment badges (OS, profile)
- clock + status pulse

Main grid:
- Service cards: Dashboard / Minecraft / Ollama / Playit
- each card shows state, pid/session, uptime, quick actions

Right rail:
- mini logs tail selector (dashboard/server/ollama/playit)
- alerts/errors panel

Bottom command palette:
- hotkeys (`s` start, `x` stop, `r` restart, `o` open, `l` logs, `d` doctor)
- `:` command mode for typed commands

## 4.2 Animation system

Subtle only (avoid noise):
- startup reveal animation (220-450ms)
- service state transitions (color + icon morph)
- pulse on active services
- spinner while command executes
- log pane smooth autoscroll

Respect reduced-motion:
- env `ARX_REDUCE_MOTION=true`
- config `ui.motion=false`

## 4.3 Theme system

Themes:
- `neon_underground` (default for new TUI)
- `classic_dark`
- `mono`

Include high-contrast color tokens for accessibility.

---

## 5) Roy SAC-inspired DELUSION integration

## 5.1 Branding concept

Use a branded text treatment inspired by old block scene aesthetics:
- headline text: `DELUSION` style option as preview motif
- production ARX identity remains `ARX`
- DELUSION-style sample shown in `arx style preview underground`

## 5.2 Asset handling

In `ascii_assets.py`, store:
- `ARX_UNDERGROUND_DOS`
- `ARX_UNDERGROUND_UNICODE`
- `ARX_MINIMAL`
- optional `DELUSION_SAMPLE_UNDERGROUND`

Keep line width <= 90 chars to avoid wrapping in 100-col terminals.

## 5.3 Windows rendering strategy

Because DOS-style differs between terminals:
- Detect console family and encoding
- if CP437/legacy-safe path unavailable, auto-fallback to unicode/minimal
- never break layout on unsupported glyphs

---

## 6) Config & persistence

Config precedence:
1. CLI flag (future): `--style`
2. env: `ARX_STYLE`
3. persisted state: `state/arx_ui.json`
4. default: `underground`

`state/arx_ui.json` schema:
```json
{
  "style": "underground",
  "theme": "neon_underground",
  "motion": true
}
```

---

## 7) Implementation phases

## Phase A — Foundation (no behavior break)
- add `ui/` modules
- add style detection + asset registry
- add `arx style ...` commands
- wire style banner in `cmd_help` and `cmd_status`

## Phase B — Installer branding refresh
- unify Linux/Windows intro banners with style packs
- keep current prompts/logic intact
- add graceful fallback for non-interactive mode

## Phase C — New full-screen TUI
- implement `scripts/arx_tui.py` with Textual
- service polling loop + actions bound to existing command handlers
- log panel + doctor summary panel
- `arx tui` command in parser

## Phase D — Polish
- animation tuning
- theme toggles
- reduced-motion mode
- docs/screenshots update

---

## 8) Testing plan

Automated:
- unit tests for style selection + fallback
- parser tests for new commands (`tui`, `style`)
- snapshot-like tests for banner width constraints

Manual matrix:
- Linux: bash/zsh + tmux
- Windows: PowerShell + Windows Terminal
- macOS: zsh + iTerm

Scenarios:
- narrow terminal (80 cols)
- unicode-disabled/limited env
- no Textual installed
- reduced motion enabled

---

## 9) Non-goals

- No web dashboard redesign in this phase
- No changes to backend API contract
- No replacement of existing classic CLI commands

---

## 10) Acceptance criteria

1. `arx style set underground` persists and is reflected in help/status banners.
2. `arx tui` launches a responsive full-screen interface with animated service cards.
3. Existing lifecycle commands still work exactly as before.
4. Installer banners show branded style without breaking unattended installs.
5. Unsupported terminals degrade to minimal style cleanly.

---

## 11) Rollout plan

- Release behind soft opt-in (`arx tui` command)
- Keep classic CLI default for lifecycle scripts/automation
- Collect feedback and then optionally make TUI discoverable in `arx help`

---

## 12) Suggested next implementation PR order

PR1: style engine + assets + `arx style` commands
PR2: installer banner refresh (sh + ps1)
PR3: `arx tui` MVP (status cards + actions)
PR4: animation/theme polish + docs
