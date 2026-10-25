from dataclasses import dataclass


@dataclass(frozen=True)
class DecompositionResult:
    valid: bool
    errors: list[str]


def validate_decomposition(subskills: list[dict]) -> DecompositionResult:
    errors = []
    if not 3 <= len(subskills) <= 5:
        errors.append("subskill_count")
    ids = {item.get("id") for item in subskills}
    if None in ids or len(ids) != len(subskills):
        errors.append("duplicate_or_missing_id")
    for item in subskills:
        if not item.get("acceptance_criteria"):
            errors.append(f"acceptance_criteria:{item.get('id')}")
        if any(dep not in ids for dep in item.get("dependencies", [])):
            errors.append(f"unknown_dependency:{item.get('id')}")
    visiting, visited = set(), set()
    graph = {item.get("id"): set(item.get("dependencies", [])) for item in subskills}
    def visit(node):
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        found = any(visit(dep) for dep in graph.get(node, ()))
        visiting.remove(node)
        visited.add(node)
        return found
    if any(visit(node) for node in graph):
        errors.append("dependency_cycle")
    return DecompositionResult(not errors, sorted(set(errors)))
