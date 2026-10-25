# Learning-to-Retention Pipeline v0.1.0

A host-neutral Agent Skill for learning a skill through observable output, retrieval, variation, interleaving, realistic tasks, and optional retention.

## Layout

- `SKILL.md`: natural-language behavior and hard constraints.
- `src/learning_retention/`: deterministic state, scoring, scheduling, mode, Wiki, and gate logic.
- `scripts/lrp.py`: JSON CLI (`init`, `load`, `validate`).
- `scripts/validate-state.py`: standalone state validator.
- `assets/`: templates; `references/`: detailed phase and retention rules.
- `docs/usage-examples.md`: reproducible learn and learn-retain walkthroughs.

## Local verification

From the repository root:

```text
python -m unittest discover -s tests -p 'test_lrp_*.py'
python learning-retention-pipeline/scripts/validate-state.py learning-retention-pipeline/assets/progress-state.json
```

For runtime data, set `LRP_DATA_DIR`. Otherwise the runtime uses the platform user-data default. The skill package's state asset is a template and is not mutated.

## Privacy

The default logging policy is `summary`. Users can explicitly choose `full` or `hash_only`. Do not submit confidential work or customer data. External files are referenced rather than copied by default.

## Release scope

v0.1.0 provides the deterministic core and host-neutral reminder templates. It does not depend on Hermes cron or another external notification service. The natural-language host must follow `SKILL.md`, read state before each turn, require explicit mode selection, and never write runtime JSON directly.
