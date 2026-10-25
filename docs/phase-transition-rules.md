# Phase transition rules

- `decompose -> cognitive`: 3–5 validated subskills, dependency graph valid, user confirmed mode and decomposition.
- `cognitive -> associative`: every dependency-free subskill has mastery >= 0.6.
- `associative -> autonomous`: all subskills have mastery >= 0.8 and at least one variation test passes.
- `autonomous -> completed`: `learn`, unseen real task passes; no retention queue or due date.
- `autonomous -> retention`: `learn_retain`, unseen real task passes and at least three held-out tasks establish a baseline.
- `retention -> associative`: only after a confirmed, gateable repair proposal for degradation.
- `completed -> retention`: only after explicit user upgrade, three new held-out tasks, and a new baseline.
- `retention -> completed`: only after explicit user downgrade; set mode to `learn` and stop retention scheduling.
