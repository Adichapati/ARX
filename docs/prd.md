# ARX Product Requirements (Current)

## Product

Name: ARX (Agentic Runtime for eXecution)

Category: local-first Minecraft operations platform with installer, dashboard, and CLI.

## Objective

Deliver a production-friendly, low-friction way to install and operate a Minecraft server with:

- one-command setup
- local AI assistance via Ollama + Gemma
- clear lifecycle controls in both dashboard and CLI
- practical safety boundaries for automated command pathways

## Core Principles

1. Local-first runtime
   - Keep AI/model operations local by default.
2. Fast onboarding
   - Minimize setup complexity for first-time users.
3. Operator control
   - Human-visible, explicit lifecycle controls (`arx` + dashboard).
4. Safety over hype
   - Validation and boundary checks for command execution.
5. Production clarity
   - Accurate docs, reproducible install, verifiable artifacts.

## Supported Platforms

- Official: Linux + Windows
- Best effort: macOS

## MVP Feature Set

1. Installer
   - Linux/macOS shell installer
   - Windows PowerShell installer with bootstrap support
   - Environment generation and sane defaults

2. Runtime orchestration
   - Start/stop/restart/status/shutdown controls
   - Dashboard + CLI parity for core operations

3. AI integration
   - Ollama endpoint integration
   - default model: `gemma4:e2b`
   - configurable context sizing (`arx ai set-context`)

4. Optional public access
   - Playit tunnel setup and status helpers

5. Release integrity
   - published checksum file and verification flow

## Non-goals (for current scope)

- Mandatory cloud services
- Plugin ecosystem abstraction layer
- Complex multi-node orchestration

## Success Criteria

- New users can install and reach dashboard successfully without manual code edits.
- Core lifecycle commands work reliably:
  - `arx start`
  - `arx status`
  - `arx shutdown`
- Local AI runtime initializes with `gemma4:e2b`.
- Users can verify installer artifacts with checksums.
- Docs are accurate, concise, and production-ready.
