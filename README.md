```text
 █████╗ ██████╗ ██╗  ██╗
██╔══██╗██╔══██╗╚██╗██╔╝
███████║██████╔╝ ╚███╔╝ 
██╔══██║██╔══██╗ ██╔██╗ 
██║  ██║██║  ██║██╔╝ ██╗
╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
```

# ARX — Agentic Runtime for eXecution

ARX is a local-first Minecraft operations platform with a production-minded installer, browser dashboard, and global `arx` CLI.

It is built for operators who want fast setup, clear controls, and local AI assistance (Ollama + Gemma) without cloud lock-in.

---

## Why ARX

- Fast setup with guided installer UX
- Local AI workflow powered by `gemma4:e2b`
- Browser dashboard + terminal CLI lifecycle controls
- Optional Playit tunnel for public joins
- Release integrity verification with SHA-256 checksums
- Safer command pathways with explicit validation and OP-gated execution boundaries

---

## Platform Support

- Linux: official
- Windows: official
- macOS: best effort

---

## Install

### Linux / macOS (recommended stable path)

```bash
git clone https://github.com/Adichapati/ARX.git
cd ARX
./install.sh
```

Non-interactive example:

```bash
./install.sh --yes --force-env --port 18890 --trigger gemma --model gemma4:e2b --temperature 0.2 --mc-version 1.20.4
```

### Windows

PowerShell bootstrap installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://arxmc.studio/install.ps1 | iex"
```

By default, Windows bootstrap installs ARX into:

```text
%USERPROFILE%\ARX
```

You can override location with:

```powershell
$env:ARX_INSTALL_DIR = "D:\ARX"
```

---

## First Run

After install, use:

```bash
arx start
arx status
arx open
```

Default dashboard URL:

```text
http://localhost:18890/
```

---

## CLI Quick Reference

```bash
arx help
arx start
arx start dashboard
arx start server
arx start ollama
arx stop
arx shutdown
arx restart
arx status
arx doctor
arx logs dashboard --lines 120
arx ai set-context 4096
arx tunnel setup
arx tunnel status
arx tunnel open
arx tunnel stop
arx style status
arx style set underground
arx style preview underground
arx tui
python3 scripts/arx_tui.py --once   # debug single snapshot (no full-screen)
arx version
```

Notes:
- `arx stop` keeps Ollama running.
- `arx shutdown` stops dashboard + server + Ollama (+ Playit if running).

---

## Security and Safety Model

ARX is local-first by default. Key safeguards include:

- Local model runtime via Ollama
- Controlled command execution pathways
- OP-oriented execution boundaries
- Input/command validation guards
- Checksum verification for installer artifacts

See: `SECURITY.md`

---

## Release Verification

Use checksums before production installs:

- Guide: `docs/RELEASE_VERIFICATION.md`
- Live checksum file: `https://arxmc.studio/checksums.txt`

---

## Project Structure (high-level)

```text
ARX/
├── dashboard/              # FastAPI dashboard app + services
├── scripts/                # arx CLI + installer helpers
├── app/minecraft_server/   # Server runtime directory
├── state/                  # Local runtime state
├── install.sh              # Linux/macOS installer
├── install.ps1             # Windows installer (bootstrap-aware)
└── main.py                 # FastAPI entrypoint
```

---

## Contributing

Please read `CONTRIBUTING.md` before opening PRs.

---

## License

See `LICENSE`.
