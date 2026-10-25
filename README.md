# Learning-to-Retention Pipeline

A host-neutral **Agent Skill** that turns "I want to learn X" into an observable, phase-gated learning loop — retrieval, spacing, variation, interleaving, realistic tasks, and optional long-term retention. Any agent harness (Claude Code, OpenCode, Codex, …) can drive it through `SKILL.md`; the deterministic state machinery lives in `src/learning_retention/`.

**Zero third-party dependencies.** Python 3.10+ (verified on CPython 3.14). Works on Windows, Linux, and macOS.

## How it works (60 seconds)

1. `scripts/lrp.py init "<skill name>"` creates persistent, validated state for one learning target.
2. `SKILL.md` is the natural-language contract: the host agent reads state before every turn, runs decompose → cognitive → associative → autonomous → retention phases, and never hand-writes runtime JSON.
3. The state layer stays deterministic: validation at the persistence boundary, atomic writes, backups, cross-platform locking, and corruption recovery — see `CHANGELOG.md` for the guarantees.

## Quickstart

From the repository root:

```text
python -m unittest discover -s tests -p 'test_lrp_*.py'
python scripts/validate-state.py assets/progress-state.json
```

`pytest` also works: `python -m pytest tests/ -q` (88 tests).

## Use as an agent skill

Point your agent harness at this repository and load `SKILL.md`. The host agent:

- explicitly selects `learn` or `learn_retain` mode (never silently defaults),
- reads state through the CLI before each turn,
- writes Wiki/log entries only through the documented paths.

`docs/usage-examples.md` has reproducible walkthroughs for both modes.

## Use from the CLI

```text
python scripts/lrp.py init "Python data analysis"
python scripts/lrp.py load python-data-analysis
python scripts/validate-state.py path/to/progress-state.json
```

Every command prints a single JSON envelope: `{"ok": …, "data": …, "error": …, "meta": …}`.

- To initialize with context, pass `--context '{"goal":"…"}'` — embedded double quotes are shell-specific: bash/zsh/cmd pass them as shown; Windows PowerShell needs each inner quote escaped as `\"` (see `docs/usage-examples.md`).

- `LRP_DATA_DIR` overrides the runtime data location. Default: the platform user-data directory (`%LOCALAPPDATA%\learning-retention-pipeline` on Windows, `~/.local/share/learning-retention-pipeline` on Linux/macOS).
- `assets/` is a template area — runtime state lives entirely outside the repository.

## Layout

- `SKILL.md`: natural-language behavior and hard constraints.
- `src/learning_retention/`: deterministic state, scoring, scheduling, mode, Wiki, and gate logic.
- `scripts/lrp.py`: JSON CLI (`init`, `load`, `validate`).
- `scripts/validate-state.py`: standalone state validator.
- `assets/`: templates; `references/`: detailed phase and retention rules.
- `docs/usage-examples.md`: reproducible learn and learn-retain walkthroughs.

## Privacy

The default logging policy is `summary`. Users can explicitly choose `full` or `hash_only`. Do not submit confidential work or customer data. External files are referenced rather than copied by default.

## Release scope

v0.1.0 provides the deterministic core and host-neutral reminder templates. It does not depend on Hermes cron or another external notification service. The natural-language host must follow `SKILL.md`, read state before each turn, require explicit mode selection, and never write runtime JSON directly.

## License

[MIT](LICENSE) — free to use, modify, and redistribute while keeping the copyright notice.
