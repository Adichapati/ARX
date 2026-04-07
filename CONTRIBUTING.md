# Contributing

## Development Rules
- Preserve ARX isolation policy (`docs/ISOLATION_POLICY.md`).
- Do not introduce Wilson fallback behavior in public runtime.
- Keep Gemma model local (`gemma4:e2b` via Ollama).

## Local setup
```bash
./install.sh
./scripts/start_dashboard.sh
```

## Basic checks
```bash
python3 -m compileall -q .
```
