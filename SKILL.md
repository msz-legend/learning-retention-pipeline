---
name: learning-retention-pipeline
description: >-
  Learn a skill from zero through decomposition, retrieval practice, variation,
  real-task automation, and optional long-term retention. Use when a user says
  they want to learn, master, practice, retain, or resume a skill.
version: 0.1.0
---

# Learning-to-Retention Pipeline

Use this skill for one active skill instance at a time. Read the runtime state before every turn and route by `current_phase` and `learning_mode`. The Python runtime is authoritative for state validation, scoring, scheduling, mode changes, and Wiki writes; never edit runtime JSON directly.

## First session

Ask at most three questions per reply and collect, over successive turns: the target outcome, the real use scene, the learner's background, time budget, output preference, and an explicit mode choice. Explain both modes:

- **learn**: reach independent real-task use, then stop. No retention queue, reminder, retention test, or `retention_due` after completion.
- **learn_retain**: reach independent use, establish at least three held-out tasks and a baseline, then continue with the minimum effective dose.

There is no default mode. Build 3–5 observable subskills with dependencies and acceptance criteria. Run structural validation, show the decomposition, accept user edits, validate again, and wait for overall confirmation before practice.

## Practice contract

One practice turn assigns one task. The learner must output or produce evidence before feedback. Do not open with a summary, answer, or complete demonstration. Give no more than two key errors, record error patterns, and ask for a retry or transfer task. “I understand” and reading do not increase mastery.

- **cognitive**: brief demonstration only after the learner's first attempt; correct the most important gaps.
- **associative**: schedule retrieval with spacing, variation, and interleaving; dependency gates block downstream work.
- **autonomous**: use a realistic task with configurable time pressure, no-reference, explanation, or public-output conditions. Preserve the output evidence.
- **retention** (`learn_retain` only): check due work in-session, prioritize an untimed prompt when due, allow postponement without faking success, and use held-out tests.

Use the deterministic scoring contract: criteria ratio minus up to 0.20 for two critical errors; completion weights are 1.00 unprompted, 0.85 light prompt, 0.70 after demonstration, and 0.60 retry. Recent valid attempts use 0.5/0.3/0.2 weighting. Save structured evidence and append the Wiki; never rewrite Wiki history.

## Signals and recovery

Interpret “太难了” as smaller difficulty, “太简单了” as a variation, “没时间” as a shorter task or a postponement, “暂停” as saved state without phase loss, “继续” as a one-sentence resume summary plus one default task, and “我学到哪了” as a natural-language progress answer. A paused associative or retention session resumes with a low-barrier retrieval task. Do not re-ask onboarding questions.

Only explicit confirmation changes mode. Upgrade from completed `learn` requires three new held-out tasks and a new baseline. Downgrade from `learn_retain` preserves history but stops future retention scheduling and enters completed `learn`.

## Privacy

Default to `summary` logging. Offer `full` or `hash_only`; do not copy external files by default, and keep output references within the user data directory. Do not send sensitive work or customer data to the log.

## References

Load `references/phases.md` for phase scripts, `references/retention-matrix.md` for doses and intervals, `references/projects.md` for design lineage, and assets for task/state templates. Use the local CLI/runtime for deterministic operations and `scripts/validate-state.py` for validation.
