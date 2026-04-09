# ARX Security Policy

## Reporting a Vulnerability

Please report security issues privately before public disclosure.

Include:
- Affected version or commit
- Reproduction steps
- Observed impact
- Suggested mitigation (if known)

## Security-sensitive Areas

- Installer scripts (`install.sh`, `install.ps1`)
- Authentication/session handling
- Command validation and execution routing
- Runtime process control paths (`arx` CLI)
- Release artifact integrity verification

## Security Principles

- Local-first operation by default
- Explicit validation before command execution
- OP-oriented execution boundaries
- No claims of perfect security; defense in depth is continuously improved
