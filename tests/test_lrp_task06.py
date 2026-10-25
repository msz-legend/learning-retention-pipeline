import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.scheduler import DependencyScheduler, SimpleIntervalScheduler
from learning_retention.tasks import task_fingerprint, unique_held_out_tasks


class Task06SchedulerTests(unittest.TestCase):
    def test_dependency_scheduler_blocks_transitive_unmastered_dependency(self):
        state = {"subskills": [
            {"id": "a", "dependencies": [], "mastery_level": 0.59},
            {"id": "b", "dependencies": ["a"], "mastery_level": 0.8},
            {"id": "c", "dependencies": ["b"], "mastery_level": 0.0},
        ]}
        task_ids = [task["subskill_id"] for task in DependencyScheduler().next_tasks(state)]
        self.assertEqual(task_ids, ["a"])

    def test_interval_scheduler_uses_five_step_spacing(self):
        scheduler = SimpleIntervalScheduler(today=date(2026, 1, 1))
        self.assertEqual(scheduler.due_date(0).isoformat(), "2026-01-02")
        self.assertEqual(scheduler.due_date(4).isoformat(), "2026-01-31")

    def test_held_out_tasks_are_deduplicated_by_normalized_fingerprint(self):
        tasks = [
            {"prompt": "Do X", "acceptance_criteria": ["A"], "variation": {"scene": "work"}},
            {"prompt": " do   x ", "acceptance_criteria": ["A"], "variation": {"scene": "work"}},
            {"prompt": "Do X", "acceptance_criteria": ["A"], "variation": {"scene": "exam"}},
        ]
        unique = unique_held_out_tasks(tasks)
        self.assertEqual(len(unique), 2)
        self.assertEqual(task_fingerprint(tasks[0]), task_fingerprint(tasks[1]))

    def test_interleaving_does_not_repeat_one_subskill_only(self):
        state = {"subskills": [
            {"id": "a", "dependencies": [], "mastery_level": 0.7},
            {"id": "b", "dependencies": [], "mastery_level": 0.7},
        ]}
        tasks = SimpleIntervalScheduler(today=date(2026, 1, 1)).next_tasks(state)
        self.assertGreaterEqual(len({task["subskill_id"] for task in tasks}), 2)


if __name__ == "__main__":
    unittest.main()
