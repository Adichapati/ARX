# Contributing to ARX

Thanks for helping improve ARX.

## Ground Rules

- Keep changes local-first and production-oriented.
- Do not add cloud-only dependencies for core runtime paths.
- Preserve Gemma-first runtime behavior (`gemma4:e2b` via Ollama).
- Keep security-sensitive paths explicit and reviewable (installer, auth, command execution).

## Local Development

```bash
git clone https://github.com/Adichapati/ARX.git
cd ARX
./install.sh
```

If already installed:

```bash
source .venv/bin/activate
```

Start dashboard manually:

```bash
uvicorn main:app --host 0.0.0.0 --port 18890
```

## Run Tests

```bash
source .venv/bin/activate
pytest -q
```

## Lint / sanity checks

```bash
python3 -m compileall -q .
```

## Pull Request Expectations

- Clear title and summary
- Repro + verification steps
- Backward-compatibility notes (if behavior changes)
- Docs updates when commands/install flow change

## Security

Do not open public issues for vulnerabilities.
Report privately per `SECURITY.md`.
