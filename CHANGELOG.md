# Changelog

## 0.1.0

- Added the host-neutral Learning-to-Retention Agent Skill.
- Added persistent state with validation, atomic writes, backup recovery, and diagnostic-only failure handling.
- Added explicit `learn` and `learn_retain` mode policy, upgrade and downgrade auditing.
- Added retrieval, spacing, variation, interleaving, dependency gating, retention scheduling, and held-out strategy gates.
- Added append-only Wiki logs, privacy policy templates, CLI validation, fixtures, and end-to-end acceptance evidence.
- External notification delivery remains outside the core release boundary.

## Unreleased (review fixes)

- Hardened `state_id` handling at the persistence boundary: every state-derived path is validated (`STATE_ID_INVALID`), preventing path traversal via `load`/`save`, and deferring schema-level validation so template placeholders stay verifiable.
- Made `safe_skill_id` produce unique stable ids for non-ASCII skill names (hash fallback) and disambiguate Windows device names; `init_state` now rejects different skill names that sanitize to the same id (`SKILL_ID_COLLISION`) instead of silently overwriting state.
- Hardened schema validation: malformed `subskills`, `mastery_level`, `learning_mode`, and `retention_due` values are reported as `STATE_INVALID` field errors instead of raising `TypeError`.
- Fixed `retention` gate crash when `best_retention_score` is `None` (the default from `init_state`) and made `schedule`/`postpone_due` tolerate malformed due dates.
- `load` now repairs a corrupt primary file from a validated backup (best-effort) so recovery events are recorded once instead of on every load.
- Transient Windows share locks on reads (PermissionError) no longer trigger backup recovery by mistake: load retries briefly then re-raises storage errors as-is, so a valid-but-busy primary is never rolled back to the older backup and no spurious recovery event is written; accident-shaped OSError and evidence-shaped JSONDecodeError are now classified separately.
- Concurrent writes are now serialized with an independent `.progress-state.lock` file (`msvcrt` region locks on Windows, `fcntl.flock` on POSIX); `save`/`init_state` take a timeout (`STATE_LOCK_TIMEOUT`) and the `init_state` collision check shares the write lock to remove the TOCTOU race.
- `wiki_log_path` is stored as a portable POSIX-relative path (`data_dir/skills/<state_id>/wiki-log.jsonl`), `StateStore.migrate` relativizes legacy absolute paths best-effort across Windows/Linux/macOS, and `StateStore.wiki_log_path(state)` is the single resolution entry point for hosts.
- Removed duplicated gate threshold logic (`ProposalGate.decide` now delegates to `validate_proposal`); `can_enter_associative` no longer passes with empty subskills; CLI reports `IO_ERROR` for OS failures; platform-native default data dir on Windows; added `.gitignore`.
- Added MIT `LICENSE` and a newcomer-facing README quickstart (verified commands, CLI envelope examples, host integration, data-dir and dependency notes); fixed parent-directory-style example paths in README and `docs/usage-examples.md` to repository-root-relative form.