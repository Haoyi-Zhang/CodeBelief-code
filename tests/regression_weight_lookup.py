"""Portable finite checks; explicit CI step, separate from the retained census."""
import copy
import itertools
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import joint as j
from src.joint_benchmark import HOSTS, public_problem
from src.joint_replay import ReplayError, replay_certificate


def tiny_problems():
    for case in range(24):
        origins = tuple(j.Origin(x, "seed", (case + i) % 4) for i, x in enumerate("abcd"))
        facts = [j.Fact("xa", "x", ("a",)), j.Fact("xb", "x", ("b",)),
                 j.Fact("yb", "y", ("b",)), j.Fact("yc", "y", ("c",)),
                 j.Fact("same-x", "x", ("a",)), j.Fact("dominated-x", "x", ("a", "d"))]
        rules = [j.Rule("xy", ("x", "y"), "p"), j.Rule("xz", ("x",), "z"),
                 j.Rule("zx", ("z",), "x")]
        if case % 3:
            facts += [j.Fact("neg", "not:p", ("c",)), j.Fact("neg2", "not:p", ("d",))]
        if case % 4 == 0:
            rules.append(j.Rule("background", (), "y"))
        if case % 5 == 0:
            facts.append(j.Fact("background-x", "x", ()))
        if case % 2:
            facts.reverse()
            rules.reverse()
        targets = ("p", "not:p") if case % 2 else ("not:p", "p")
        yield j.Problem(f"tiny-{case}", origins, tuple(facts), tuple(rules), *targets)
    yield j.Problem("empty-background", (), (j.Fact("p", "p", ()), j.Fact("n", "not:p", ())), (), "p", "not:p")
    yield j.Problem("empty-absent", (), (), (), "p", "not:p")


def literal_reference(problem):
    """Literal exhaustive selections and rule satisfaction; no producer helpers."""
    ids = tuple(o.identifier for o in problem.origins)
    weights = {o.identifier: o.weight for o in problem.origins}
    reached = {}
    feasible = []
    for size in range(len(ids) + 1):
        for chosen in itertools.combinations(ids, size):
            chosen = frozenset(chosen)
            known = set(f.literal for f in problem.facts if all(x in chosen for x in f.origins))
            while True:
                consequences = set(r.head for r in problem.rules if all(x in known for x in r.body))
                if consequences <= known:
                    break
                known.update(consequences)
            for literal in known:
                reached.setdefault(literal, []).append(chosen)
            if all(x in known for x in (problem.positive, problem.negative)):
                feasible.append((sum(weights[x] for x in chosen), len(chosen), tuple(sorted(chosen))))
    minimal = {literal: {s for s in selections if not any(t < s for t in selections)}
               for literal, selections in reached.items()}
    return minimal, min(feasible) if feasible else None


def record(problem):
    frontiers, iterations = j.derive_antichains(problem)
    expected, optimum = literal_reference(problem)
    observed = {literal: set(proofs) for literal, proofs in frontiers.items() if proofs}
    assert observed == expected
    exact = j.solve_exact(problem)
    assert (exact is None) == (optimum is None)
    if exact is not None:
        assert (exact.cost, len(exact.selected), tuple(sorted(exact.selected))) == optimum
    caps = []
    for limit in (0, 1, 3, 10, 100_000, -1, True, 1.0):
        try:
            value, count = j.derive_antichains(problem, max_frontier_entries=limit)
            caps.append([limit, "ok", count, {x: [j.proof_to_dict(p) for p in v.values()] for x, v in value.items()}])
        except (ValueError, RuntimeError) as error:
            caps.append([limit, type(error).__name__, str(error)])
    return {"problem": j.problem_to_dict(problem), "iterations": iterations,
            "frontiers": {x: [j.proof_to_dict(p) for p in v.values()] for x, v in frontiers.items()},
            "exact": j.solution_to_dict(problem, exact, algorithm="exact-antichain"),
            "independent": j.solution_to_dict(problem, j.independent_sides(problem), algorithm="independent"),
            "caps": caps}


def public_records():
    records = []
    for host in sorted(HOSTS):
        for profile in ("unit", "history-heavy", "code-heavy"):
            for variant in ("direct", "chain", "choice", "no-bridge-control", "single-side-control"):
                problem = public_problem(host, variant, profile)
                oracle = j.brute_force_optimum(problem)
                document = {"schema": "joint-contradiction-certificate-v1",
                            "problem": j.problem_to_dict(problem),
                            "solution": j.solution_to_dict(problem, j.solve_exact(problem), algorithm="exact-antichain"),
                            "oracle_selected": sorted(oracle) if oracle is not None else None}
                frozen = json.loads((ROOT / "results/joint-certificates" / (problem.name + ".json")).read_text())
                assert document == frozen
                replay = replay_certificate(document, ROOT)
                records.append({"document": document, "replay": replay,
                                "independent": j.solution_to_dict(problem, j.independent_sides(problem), algorithm="independent")})
    return records


def snapshot():
    return {"tiny": [record(p) for p in tiny_problems()], "public": public_records()}


class WeightLookupTests(unittest.TestCase):
    def test_literal_frontiers_complete_records_caps_and_public_frozen(self):
        value = snapshot()
        self.assertEqual((len(value["tiny"]), len(value["public"])), (26, 45))

    def test_once_per_invocation_fresh_problems_and_public_validation(self):
        problem = next(tiny_problems())
        getter = j.Problem.origin_map.fget
        for function in (j.derive_antichains, j.solve_exact, j.independent_sides):
            calls = []
            def count(instance):
                calls.append(instance)
                return getter(instance)
            with patch.object(j.Problem, "origin_map", property(count)):
                function(problem)
                self.assertEqual(calls, [problem])
        self.assertEqual(j.support_cost(problem, ["a", "a", "b"]), 1)
        with self.assertRaisesRegex(ValueError, "support contains unknown origin"):
            j.support_cost(problem, ["unknown"])
        other = j.Problem("other", tuple(j.Origin(o.identifier, "seed", 9) for o in problem.origins),
                          problem.facts, problem.rules, problem.positive, problem.negative)
        self.assertEqual(j.support_cost(other, ["a", "b"]), 18)
        self.assertEqual(record(problem), record(problem))

    def test_replay_rejects_scientific_mutations(self):
        document = next(r["document"] for r in public_records() if r["document"]["solution"]["status"] == "certificate")
        for field in ("cost", "selected", "positive_proof", "oracle_selected"):
            bad = copy.deepcopy(document)
            if field == "cost":
                bad["solution"]["cost"] += 1
            elif field == "selected":
                bad["solution"]["selected"].pop()
            elif field == "positive_proof":
                bad["solution"][field]["step"] = "invented"
            else:
                bad[field] = []
            with self.assertRaises(ReplayError):
                replay_certificate(bad, ROOT)


if __name__ == "__main__":
    unittest.main()
