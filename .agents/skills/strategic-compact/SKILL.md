---
name: strategic-compact
description: Preserve Rasam task context at a completed milestone when context pressure warrants a handoff or native Codex compaction.
---

# Strategic Compact — Codex adaptation

Derived from ECC commit `76aaa77df6adc5b889e689007bf99b9a4f74af34`.
Original reference: `UPSTREAM.md` (load only for provenance, not execution).

Use native Codex compaction; this skill cannot invoke compaction automatically.
At a completed milestone, if context pressure warrants it, write concise factual
state to the existing PLAN.md: current task/progress, architecture decisions,
modified files, dependencies, unresolved issues, actual test results, next steps.
Do not duplicate the roadmap or store secrets. Separate assumptions from facts.
Avoid repeated compaction and preserve context while an implementation is active.
The user can use `/compact` where their Codex surface supports it; otherwise
native automatic compaction or a new chat reading PLAN.md is sufficient.
Never install Claude PreToolUse hooks, transcript parsers, or extra optimizers.
Do not alter native context thresholds or claim measured token savings.