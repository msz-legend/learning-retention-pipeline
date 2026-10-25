# LRP v0.1.0 specification lock

## Scope
Learning-to-Retention Pipeline is a natural-language Agent Skill with a small deterministic Python runtime. v0.1.0 supports multiple saved skill instances but one active instance per user; external notification delivery is out of scope.

## Locked invariants

| ID | Constraint | Implementation check |
|---|---|---|
| C-01 | Use spacing, retrieval, variation, and interleaving; do not use fluency as mastery | `Scheduler` emits all four learning signals |
| C-02 | Cognitive, associative, autonomous phases use distinct practice organization | phase router and scheduler tests |
| C-03 | Dependencies gate downstream tasks | dependency scheduler test |
| C-04 | Strategy changes require held-out validation; Wiki is append-only | gate tests |
| C-05 | Learner output precedes feedback | interaction contract and feedback tests |
| C-06 | Retention is opt-in and mode-gated | mode policy tests |
| G-01..G-09 | decomposition, feedback, retention, persistence, bounded document size, natural-language flows | E2E report |

## Runtime decisions
- `assets/progress-state.json` is a template; runtime state lives under `LRP_DATA_DIR` or the platform user-data default.
- State writes are validated, temporary-file based, and retain `.bak`; failed recovery enters diagnostic-only mode.
- Default privacy policy is `summary`; supported values are `summary`, `full`, `hash_only`.
- `skill_type` remains the primary type; `skill_types` is a non-empty compatible array.
- `completed` requires `learning_mode=learn`; downgrading from retain changes mode and phase together.
- A proposal is gateable only with at least three held-out tasks and a candidate mean at least `0.01` above baseline.
