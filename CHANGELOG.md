# Changelog

All notable changes to ARX are documented here.

## [1.0.0-beta] - 2026-04-09

### Added
- Production-oriented installer distribution via `arxmc.studio` endpoints.
- Windows bootstrap installer path with runtime bundle hydration.
- Public checksum verification flow for installer artifacts.

### Changed
- ARX branding finalized across runtime, docs, and installer UX.
- Linux installer hardening:
  - sudo preflight
  - non-interactive dependency installation
  - apt lock timeout handling
- Windows installer hardening:
  - admin-aware winget behavior
  - timeout-safe package installation wrapper
  - live winget output streaming and UAC wait hints
- Documentation and release guidance aligned for production launch.

### Security
- Preserved command validation safeguards and OP-oriented execution boundaries.

## [0.1.0-alpha]

### Added
- Initial local-first installer and runtime setup.
- Gemma-focused Ollama integration (`gemma4:e2b`).
- Dashboard + CLI lifecycle control foundation.
