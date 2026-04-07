# GitHub Backlog (v0.1.0)

Use this file to create GitHub issues in order. Suggested labels in brackets.

## Milestone: v0.1.0-alpha

### Epic A — Foundation

1. [repo][docs] Add LICENSE, SECURITY, CONTRIBUTING, CHANGELOG
- Acceptance: all root docs present and linked from README.

2. [ci] Add CI workflow: python lint/compile + smoke import
- Acceptance: PRs run checks automatically.

3. [docs] Add issue/PR templates
- Acceptance: templates appear in new issue/PR UI.

### Epic B — Installer UX

4. [installer] Make install.sh idempotent
- Acceptance: second run is no-op or safe update.

5. [installer] Add interactive setup wizard prompts
- Acceptance: prompts collect and validate all required settings, including trigger word and local model context/tuning defaults.

6. [installer] Add non-interactive mode (--yes + env overrides)
- Acceptance: automated install works in CI-like shell.

7. [installer] Improve dependency install/check messages
- Acceptance: clear remediation shown on failure.

8. [installer][os] Implement OS-specific Ollama setup paths (Linux/macOS/Windows)
- Acceptance: installer selects correct OS flow and verifies `gemma4:e2b` availability before completion.

### Epic C — Dashboard Runtime

9. [dashboard] Add health panel (Ollama/tmux/java/server ping)
- Acceptance: health values update live.

9a. [dashboard] Add first-run Gemma setup/tuning UI
- Acceptance: user can configure context size and related local inference parameters from UI.
10. [dashboard] Add server.properties edit panel
- Acceptance: selected properties can be edited safely and persisted.

11. [dashboard] Add OP/whitelist management UI
- Acceptance: OP/WL operations complete with validation.

12. [dashboard] Improve websocket reconnect + log buffering
- Acceptance: stable reconnect behavior under restart/network blips.

### Epic D — Gemma Assistant Safety

13. [gemma-assistant][safety] Implement command allowlist templates
- Acceptance: only allowed command families execute.

14. [gemma-assistant][safety] Add placeholder rejection + normalization guards
- Acceptance: unresolved placeholders are refused.

15. [gemma-assistant][safety] Action-observation confirmation before success response
- Acceptance: no false success messages.

16. [gemma-assistant][safety] Add rate limiting/cooldown and anti-spam
- Acceptance: repeated triggers are throttled.

17. [gemma-assistant] Ollama/model unavailable strict handling
- Acceptance: clear local-health error, guided remediation, and no Wilson compatibility behavior.

### Epic E — Distribution

18. [release] Add release workflow with checksums
- Acceptance: tagged release publishes artifacts + sha256.

19. [docs] Replace installer domain placeholder when domain is live
- Acceptance: canonical copy command is production URL.

20. [docs] Add install verification section
- Acceptance: users can verify integrity before execution.

### Epic F — Launch QA

21. [qa] Fresh Ubuntu VM one-liner install test
- Acceptance: install + first login completed without manual patching.

22. [qa] Reinstall and upgrade tests
- Acceptance: no config corruption across reinstall/upgrade.

23. [qa][security] Auth and lockout test suite
- Acceptance: unauthorized requests blocked; lockout enforced.

24. [qa][safety] Gemma Assistant command safety regression suite
- Acceptance: blocked commands never execute.

25. [release] Publish v0.1.0-alpha release notes + known issues
- Acceptance: release notes include limitations and recovery steps.

---

## Suggested labels
- `installer`
- `dashboard`
- `gemma-assistant`
- `safety`
- `security`
- `qa`
- `docs`
- `release`
- `ci`
- `good first issue`
