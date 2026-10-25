from copy import deepcopy


class PhaseTransitionError(ValueError):
    pass


def can_enter_cognitive(state: dict) -> bool:
    return bool(state.get("learning_mode") in {"learn", "learn_retain"} and state.get("decomposition_confirmed") and _valid_subskills(state.get("subskills", [])))


def can_enter_associative(state: dict) -> bool:
    subskills = state.get("subskills", [])
    return bool(subskills) and all(item.get("mastery_level", 0.0) >= 0.6 for item in subskills if not item.get("dependencies"))


def can_enter_autonomous(state: dict) -> bool:
    return bool(state.get("variation_test_passed") and state.get("subskills") and all(item.get("mastery_level", 0.0) >= 0.8 for item in state["subskills"]))


def _valid_subskills(subskills: list[dict]) -> bool:
    if not 3 <= len(subskills) <= 5:
        return False
    ids = {item.get("id") for item in subskills}
    return len(ids) == len(subskills) and None not in ids and all(item.get("acceptance_criteria") for item in subskills)
