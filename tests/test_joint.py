import copy
import itertools
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from src.joint import (
    Fact, Origin, Problem, Rule, brute_force_optimum, closure, contradictory,
    derive_antichains, greedy_delete, independent_sides, is_inclusion_minimal,
    make_deletion_gap, make_tight_two_approx, negate, problem_to_dict,
    solution_to_dict, solve_exact, support_cost,
)
from src.joint_benchmark import HOSTS, public_problem, random_problem
from src.joint_replay import ReplayError, replay_certificate

ROOT = Path(__file__).resolve().parents[1]


def independent_closure(problem: Problem, selected: frozenset[str]) -> frozenset[str]:
    """Small test-only closure that does not call the producer closure routine."""
    known = {fact.literal for fact in problem.facts if set(fact.origins) <= selected}
    while True:
        changed = False
        for rule in problem.rules:
            if all(literal in known for literal in rule.body) and rule.head not in known:
                known.add(rule.head)
                changed = True
        if not changed:
            return frozenset(known)


def independent_minimal_supports(problem: Problem, literal: str) -> set[frozenset[str]]:
    ids = tuple(sorted(problem.origin_map))
    derivable = []
    for size in range(len(ids) + 1):
        for subset in itertools.combinations(ids, size):
            chosen = frozenset(subset)
            if literal in independent_closure(problem, chosen):
                derivable.append(chosen)
    return {candidate for candidate in derivable
            if not any(other < candidate for other in derivable)}


class JointModelTests(unittest.TestCase):
    def test_strong_negation_is_involution(self):
        for literal in ("p", "policy:x", "not:q"):
            self.assertEqual(negate(negate(literal)), literal)

    def test_reverse_target_pair_is_accepted(self):
        problem = Problem(
            "reverse",
            (Origin("a", "seed"), Origin("b", "seed")),
            (Fact("fa", "not:p", ("a",)), Fact("fb", "p", ("b",))),
            (),
            "not:p",
            "p",
        )
        answer = solve_exact(problem)
        self.assertIsNotNone(answer)
        self.assertEqual(answer.selected, frozenset({"a", "b"}))

    def test_repeated_not_encoding_is_rejected(self):
        with self.assertRaises(ValueError):
            negate("not:not:p")
        with self.assertRaises(ValueError):
            Fact("bad", "not:not:p", ())
        with self.assertRaises(ValueError):
            Problem("bad", (), (), (), "not:not:p", "not:p")

    def test_empty_origin_background_certificate(self):
        problem = Problem(
            "background",
            (),
            (Fact("fp", "p", ()), Fact("fn", "not:p", ())),
            (),
            "p",
            "not:p",
        )
        answer = solve_exact(problem)
        self.assertIsNotNone(answer)
        self.assertEqual(answer.selected, frozenset())
        self.assertEqual(answer.cost, 0)
        self.assertEqual(brute_force_optimum(problem), frozenset())

    def test_fact_only_contradiction(self):
        problem = Problem("basic", (Origin("a", "seed"), Origin("b", "seed")),
                          (Fact("fa", "p", ("a",)), Fact("fb", "not:p", ("b",))), (), "p", "not:p")
        answer = solve_exact(problem)
        self.assertEqual(answer.cost, 2)
        self.assertEqual(answer.selected, frozenset({"a", "b"}))

    def test_shared_origin_is_counted_once(self):
        problem = Problem("shared", (Origin("s", "seed", 3),),
                          (Fact("fa", "p", ("s",)), Fact("fb", "not:p", ("s",))), (), "p", "not:p")
        self.assertEqual(solve_exact(problem).cost, 3)

    def test_weighted_minimum_not_cardinality_minimum(self):
        origins = (Origin("heavy", "seed", 9), Origin("x", "seed", 1), Origin("y", "seed", 1))
        facts = (Fact("p1", "p", ("heavy",)), Fact("n1", "not:p", ("heavy",)),
                 Fact("p2", "p", ("x", "y")), Fact("n2", "not:p", ("x", "y")))
        problem = Problem("weights", origins, facts, (), "p", "not:p")
        self.assertEqual(solve_exact(problem).selected, frozenset({"x", "y"}))

    def test_rule_chain(self):
        problem = Problem("chain", (Origin("a", "seed"), Origin("b", "seed")),
            (Fact("fa", "a", ("a",)), Fact("fb", "b", ("b",))),
            (Rule("a1", ("a",), "a2"), Rule("a2", ("a2",), "p"), Rule("b1", ("b",), "not:p")), "p", "not:p")
        answer = solve_exact(problem)
        self.assertEqual(answer.positive_proof.depth, 3)
        self.assertTrue(contradictory(problem, answer.selected))

    def test_unproductive_cycle_terminates(self):
        problem = Problem("cycle", (Origin("a", "seed"),), (Fact("f", "a", ("a",)),),
            (Rule("ab", ("a",), "b"), Rule("ba", ("b",), "a")), "p", "not:p")
        frontiers, iterations = derive_antichains(problem)
        self.assertIn("b", frontiers)
        self.assertLess(iterations, 5)
        self.assertIsNone(solve_exact(problem))

    def test_frontier_cap_covers_fact_initialization(self):
        problem = Problem(
            "cap-facts",
            (Origin("a", "seed"), Origin("b", "seed")),
            (Fact("fa", "p", ("a",)), Fact("fb", "not:p", ("b",))),
            (),
            "p",
            "not:p",
        )
        with self.assertRaisesRegex(RuntimeError, "fact initialization"):
            derive_antichains(problem, max_frontier_entries=1)

    def test_true_cartesian_product_matches_independent_subset_oracle(self):
        origins = tuple(Origin(x, "seed") for x in ("a", "b", "c", "d", "e", "n"))
        facts = (
            Fact("xa", "x", ("a",)), Fact("xd", "x", ("d",)),
            Fact("yb", "y", ("b",)), Fact("yd", "y", ("d",)),
            Fact("zc", "z", ("c",)), Fact("ze", "z", ("e",)),
            Fact("neg", "not:p", ("n",)),
        )
        rules = (Rule("xyz", ("x", "y", "z"), "p"),)
        problem = Problem("cartesian", origins, facts, rules, "p", "not:p")
        frontiers, _ = derive_antichains(problem)
        observed = set(frontiers["p"])
        expected = independent_minimal_supports(problem, "p")
        self.assertEqual(observed, expected)
        self.assertEqual(observed, {
            frozenset({"c", "d"}), frozenset({"d", "e"}),
            frozenset({"a", "b", "c"}), frozenset({"a", "b", "e"}),
        })

    def test_oracle_agrees_on_random_weighted_instances(self):
        rng = random.Random(991)
        for n in range(4, 10):
            for i in range(12):
                problem = random_problem(rng, i, n)
                exact = solve_exact(problem)
                oracle = brute_force_optimum(problem)
                self.assertEqual(exact is None, oracle is None)
                if exact is not None:
                    self.assertEqual(exact.cost, support_cost(problem, oracle))

    def test_independent_side_bound(self):
        for k in (2, 3, 8, 32):
            problem = make_tight_two_approx(k)
            exact = solve_exact(problem)
            approx = independent_sides(problem)
            self.assertLessEqual(approx.cost, 2 * exact.cost)

    def test_two_approximation_family_is_tight(self):
        problem = make_tight_two_approx(64)
        exact = solve_exact(problem)
        approx = independent_sides(problem)
        self.assertEqual((exact.cost, approx.cost), (65, 128))
        self.assertGreater(approx.cost / exact.cost, 1.96)

    def test_deletion_returns_inclusion_minimal_but_not_minimum(self):
        problem, order = make_deletion_gap(20)
        chosen = greedy_delete(problem, order)
        self.assertTrue(is_inclusion_minimal(problem, chosen))
        self.assertEqual(support_cost(problem, chosen), 20)
        self.assertEqual(solve_exact(problem).cost, 1)

    def test_closure_rejects_unknown_origin(self):
        problem = make_tight_two_approx(2)
        with self.assertRaises(ValueError):
            closure(problem, {"unknown"})

    def test_problem_rejects_nonopposite_targets(self):
        with self.assertRaises(ValueError):
            Problem("bad", (), (), (), "p", "q")


class PublicHostTests(unittest.TestCase):
    def test_all_declared_anchors_exist_once(self):
        for host in HOSTS.values():
            for which in ("before", "after"):
                text = (ROOT / host[f"{which}_path"]).read_text()
                self.assertEqual(text.count(host[f"{which}_feature"]), 1)
                self.assertEqual(text.count(host[f"{which}_context"]), 1)
            self.assertEqual((ROOT / host["after_path"]).read_text().count(host["shared_context"]), 1)

    def test_positive_public_cases_have_certificates_and_use_bridge(self):
        for host in HOSTS:
            for profile in ("unit", "history-heavy", "code-heavy"):
                for variant in ("direct", "chain", "choice"):
                    answer = solve_exact(public_problem(host, variant, profile))
                    self.assertIsNotNone(answer)
                    self.assertIn("entity-bridge", answer.positive_proof.support)
                    self.assertIn("entity-bridge", answer.negative_proof.support)

    def test_bridge_ablation_changes_only_bridge_fact(self):
        for host in HOSTS:
            for profile in ("unit", "history-heavy", "code-heavy"):
                positive = public_problem(host, "direct", profile)
                ablated = public_problem(host, "no-bridge-control", profile)
                self.assertEqual(positive.origins, ablated.origins)
                self.assertEqual(positive.rules, ablated.rules)
                self.assertEqual(
                    {fact for fact in positive.facts if fact.name != "entity-bridge-fact"},
                    set(ablated.facts),
                )
                self.assertEqual(len(positive.facts), len(ablated.facts) + 1)
                self.assertIsNotNone(solve_exact(positive))
                self.assertIsNone(solve_exact(ablated))

    def test_negative_controls_have_no_certificate(self):
        for host in HOSTS:
            for profile in ("unit", "history-heavy", "code-heavy"):
                for variant in ("no-bridge-control", "single-side-control"):
                    self.assertIsNone(solve_exact(public_problem(host, variant, profile)))

    def test_choice_exercises_union_awareness_for_all_profiles(self):
        expected = {
            "unit": (4, 5),
            "history-heavy": (6, 6),
            "code-heavy": (8, 13),
        }
        for host in HOSTS:
            for profile, pair in expected.items():
                problem = public_problem(host, "choice", profile)
                exact, independent = solve_exact(problem), independent_sides(problem)
                self.assertEqual((exact.cost, independent.cost), pair)
                self.assertIn("entity-bridge", exact.selected)

    def test_history_heavy_choice_avoids_expensive_history(self):
        for host in HOSTS:
            answer = solve_exact(public_problem(host, "choice", "history-heavy"))
            self.assertNotIn("history-change", answer.selected)
            self.assertIn("entity-bridge", answer.selected)
            code_origins = {o.identifier for o in public_problem(host, "choice", "history-heavy").origins if o.kind == "code"}
            self.assertEqual(len(answer.selected & code_origins), 4)

    def _document(self, *, host="cjson", variant="choice", profile="unit", independent=False):
        problem = public_problem(host, variant, profile)
        solution = independent_sides(problem) if independent else solve_exact(problem)
        return {
            "schema": "joint-contradiction-certificate-v1",
            "problem": problem_to_dict(problem),
            "solution": solution_to_dict(problem, solution, algorithm="independent" if independent else "exact-antichain"),
            "oracle_selected": sorted(brute_force_optimum(problem)) if brute_force_optimum(problem) is not None else None,
        }

    @staticmethod
    def _origin(document, kind):
        return next(origin for origin in document["problem"]["origins"] if origin["kind"] == kind)

    def test_independent_replay_accepts_valid_certificate(self):
        result = replay_certificate(self._document(), ROOT)
        self.assertEqual(result["status"], "certificate")
        self.assertEqual(result["cost"], 4)

    def test_replay_accepts_reverse_background_targets_and_empty_origins(self):
        problem = Problem(
            "reverse-background", (),
            (Fact("fneg", "not:p", ()), Fact("fpos", "p", ())), (),
            "not:p", "p",
        )
        solution = solve_exact(problem)
        document = {
            "schema": "joint-contradiction-certificate-v1",
            "problem": problem_to_dict(problem),
            "solution": solution_to_dict(problem, solution, algorithm="exact-antichain"),
            "oracle_selected": [],
        }
        result = replay_certificate(document, ROOT)
        self.assertEqual(result["cost"], 0)
        self.assertEqual(result["selected_origins"], 0)

    def test_replay_rejects_repeated_not_encoding(self):
        document = self._document()
        document["problem"]["positive"] = "not:not:p"
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_absent_anchor(self):
        document = self._document()
        document["problem"]["origins"][0]["anchor"] = "not in source"
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_duplicated_anchor(self):
        document = self._document()
        code = next(origin for origin in document["problem"]["origins"] if origin["kind"] == "code")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "inputs", root / "inputs")
            target = root / code["path"]
            target.write_text(target.read_text() + "\n" + code["anchor"] + "\n")
            with self.assertRaises(ReplayError):
                replay_certificate(document, root)

    def test_replay_rejects_parent_path_escape(self):
        document = self._document()
        document["problem"]["origins"][0]["path"] = "../outside.c"
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_root_contained_absolute_path(self):
        document = self._document()
        code = next(origin for origin in document["problem"]["origins"] if origin["kind"] == "code")
        code["path"] = str((ROOT / code["path"]).resolve())
        code["metadata"]["file"] = code["path"]
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_change_same_snapshot(self):
        document = self._document()
        change = self._origin(document, "change")
        change["metadata"]["after_snapshot"] = change["metadata"]["before_snapshot"]
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_change_same_file_different_anchor(self):
        document = self._document()
        change = self._origin(document, "change")
        change["metadata"]["after_file"] = change["metadata"]["before_file"]
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_change_id_embedded_record_mismatch(self):
        document = self._document()
        change = self._origin(document, "change")
        change["metadata"]["before_anchor"] = change["metadata"]["after_anchor"]
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_bridge_endpoint_id_mismatch(self):
        document = self._document()
        bridge = self._origin(document, "bridge")
        bridge["metadata"]["after_origin"] = bridge["metadata"]["before_origin"]
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_cost_tampering(self):
        document = self._document()
        document["solution"]["cost"] += 1
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_proof_literal_tampering(self):
        document = self._document()
        document["solution"]["positive_proof"]["literal"] = "wrong"
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_removed_multi_premise(self):
        document = self._document()
        document["solution"]["positive_proof"]["premises"].pop()
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_unknown_selected_origin(self):
        document = self._document()
        document["solution"]["selected"].append("unknown")
        document["solution"]["selected"].sort()
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_duplicate_selected_origin(self):
        document = self._document()
        document["solution"]["selected"].append(document["solution"]["selected"][0])
        document["solution"]["selected"].sort()
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_higher_cost_valid_certificate(self):
        document = self._document(independent=True)
        self.assertEqual(document["solution"]["cost"], 5)
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_false_positive_bridge_control(self):
        positive = self._document(variant="direct")
        control_problem = public_problem("cjson", "no-bridge-control", "unit")
        positive["problem"] = problem_to_dict(control_problem)
        positive["oracle_selected"] = None
        with self.assertRaises(ReplayError):
            replay_certificate(positive, ROOT)

    def test_replay_rejects_duplicate_oracle_witness_entry(self):
        document = self._document()
        document["oracle_selected"].append(document["oracle_selected"][0])
        document["oracle_selected"].sort()
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_unknown_oracle_witness_origin(self):
        document = self._document()
        document["oracle_selected"] = ["unknown"]
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_infeasible_oracle_witness(self):
        document = self._document()
        document["oracle_selected"] = []
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_rejects_nonoptimal_oracle_witness(self):
        document = self._document()
        problem = public_problem("cjson", "choice", "unit")
        document["oracle_selected"] = sorted(independent_sides(problem).selected)
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)

    def test_replay_accepts_negative_control(self):
        problem = public_problem("mjson", "no-bridge-control", "unit")
        document = {
            "schema": "joint-contradiction-certificate-v1",
            "problem": problem_to_dict(problem),
            "solution": solution_to_dict(problem, None, algorithm="exact-antichain"),
            "oracle_selected": None,
        }
        result = replay_certificate(document, ROOT)
        self.assertEqual(result["oracle"], "none")

    def test_negative_control_rejects_oracle_witness(self):
        problem = public_problem("mjson", "no-bridge-control", "unit")
        document = {
            "schema": "joint-contradiction-certificate-v1",
            "problem": problem_to_dict(problem),
            "solution": solution_to_dict(problem, None, algorithm="exact-antichain"),
            "oracle_selected": [],
        }
        with self.assertRaises(ReplayError):
            replay_certificate(document, ROOT)


if __name__ == "__main__":
    unittest.main()
