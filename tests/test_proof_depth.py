import copy
import json
import unittest

from src.joint import Fact, Origin, Problem, Rule, problem_to_dict, proof_to_dict, solve_exact
from src.joint_replay import ReplayError, replay_proof


class ProofDepthTests(unittest.TestCase):
    def _chain(self, length):
        facts = (Fact("start", "x0", ("a",)), Fact("negative", "not:p", ("b",)))
        rules = tuple(
            Rule(f"r{i:04d}", (f"x{i}",), "p" if i == length - 1 else f"x{i+1}")
            for i in range(length)
        )
        return Problem(
            "finite-chain", (Origin("a", "seed"), Origin("b", "seed")),
            facts, rules, "p", "not:p"
        )

    def test_two_thousand_step_proof_serializes_and_replays(self):
        problem = self._chain(2000)
        solution = solve_exact(problem)
        self.assertIsNotNone(solution)
        proof = solution.positive_proof
        self.assertEqual((proof.depth, proof.nodes), (2001, 2001))
        encoded = json.loads(json.dumps(proof_to_dict(proof)))
        self.assertEqual(encoded["format"], "proof-dag")
        self.assertEqual(len(encoded["nodes"]), 2001)
        definition = problem_to_dict(problem)
        facts = {x["name"]: x for x in definition["facts"]}
        rules = {x["name"]: x for x in definition["rules"]}
        self.assertEqual(replay_proof(encoded, facts, rules), ("p", frozenset({"a"})))

    def test_flat_replay_rejects_cycles_and_invalid_indices(self):
        problem = self._chain(129)
        proof = proof_to_dict(solve_exact(problem).positive_proof)
        definition = problem_to_dict(problem)
        facts = {x["name"]: x for x in definition["facts"]}
        rules = {x["name"]: x for x in definition["rules"]}
        for child in (proof["root"], -1, len(proof["nodes"]), True):
            bad = copy.deepcopy(proof)
            bad["nodes"][bad["root"]]["premises"] = [child]
            with self.subTest(child=child), self.assertRaises(ReplayError):
                replay_proof(bad, facts, rules)

    def test_shallow_proof_keeps_nested_encoding(self):
        problem = self._chain(3)
        proof = proof_to_dict(solve_exact(problem).positive_proof)
        self.assertNotIn("format", proof)
        definition = problem_to_dict(problem)
        self.assertEqual(
            replay_proof(json.loads(json.dumps(proof)),
                         {x["name"]: x for x in definition["facts"]},
                         {x["name"]: x for x in definition["rules"]}),
            ("p", frozenset({"a"}))
        )


if __name__ == "__main__":
    unittest.main()
