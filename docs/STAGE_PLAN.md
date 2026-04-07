# Build Stages & Review Gates

1. Core scaffold + auth + FastAPI + tmux/log services
   - Review: import/compile + route smoke
2. Gemma Assistant AI operator loop (Ollama + safety regex + action-observation)
   - Review: static checks + integration simulation against log parsing
3. One-click installer and operational scripts
   - Review: shell syntax + dry-run verification
4. Final QA
   - Review: compileall, app import, endpoint smoke tests
