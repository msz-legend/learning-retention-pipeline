# Mode policy

## Choice
The first session must explicitly explain and obtain `learn` or `learn_retain`; no default is allowed.

## `learn`
Learn through autonomous real-task evidence, then enter `completed`. Do not create `retention_due`, retention queue, retention reminders, or retention tests. A user can explicitly request an upgrade.

## `learn_retain`
Learn through autonomous evidence, establish at least three held-out tasks and a baseline, then enter `retention`. Schedule the minimum effective dose and retention tests.

## Changes
Only explicit user confirmation can upgrade or downgrade. Upgrade creates new held-out tasks and a fresh baseline before changing the mode. Downgrade stops future scheduling, preserves all historical Wiki and scores, records the event, and enters `completed`.
