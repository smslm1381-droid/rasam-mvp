---
name: verification-loop
description: Verify Rasam changes with selective Python checks and honest PASS, FAIL, SKIP, or unavailable results before reporting completion.
---

# Verification Loop — Codex / Windows adaptation

Derived from ECC commit `76aaa77df6adc5b889e689007bf99b9a4f74af34`.
Original reference: `UPSTREAM.md` (not a command checklist for this project).

Inspect the current diff and relevant test files. Use the project's .venv Python
when available; verify dependencies before running application tests.
For a small change run its targeted pytest file; for related modules run their
integration tests; broaden to the complete suite for architecture/high-risk work.
Examples in PowerShell, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/desktop -q --tb=short
.\.venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
git diff --stat
```

Check that the selected test directory exists. Report database/model-dependent
skips explicitly. Never count unavailable dependencies or skipped tests as passes.
Use lint/type/build checks only when configured and applicable; this repository
has no configured ruff/pyright/TypeScript gate. Do not install those tools or add
an arbitrary coverage gate. Documentation-only edits need diff/config validation,
not the whole application suite. Do not repeat unchanged successful checks.
Review affected behavior, regressions and unexpected diff changes. Keep secret
values out of outputs. Report commands, exit status, actual counts and limitations.
No Claude hooks, periodic timer, `/verify` command, or npm checks are installed.