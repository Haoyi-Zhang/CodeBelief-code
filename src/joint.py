"""Joint minimum contradiction certificates for finite positive Horn provenance.

The module is intentionally dependency-free.  Strong negation is represented by
literal names beginning with ``not:``; it is not negation-as-failure.  Rules are
fixed analyzer semantics.  Selectable, non-negative-cost origins identify code
spans, version-change records, and explicit bridge assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence


def _validate_literal(literal: str) -> None:
    """Validate the canonical single-prefix strong-negation encoding."""
    if type(literal) is not str or not literal or any(ch.isspace() for ch in literal):
        raise ValueError("literals must be nonempty whitespace-free strings")
    if literal == "not:" or literal.startswith("not:not:"):
        raise ValueError("literals use at most one leading not: prefix")


@dataclass(frozen=True, order=True)
class Origin:
    identifier: str
    kind: str
    weight: int = 1
    path: str | None = None
    anchor: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.identifier or any(ch.isspace() for ch in self.identifier):
            raise ValueError("origin identifiers must be nonempty and whitespace-free")
        if self.kind not in {"code", "change", "bridge", "seed", "context"}:
            raise ValueError(f"unsupported origin kind: {self.kind}")
        if type(self.weight) is not int or self.weight < 0:
            raise ValueError("origin weight must be a non-negative integer")
        if (self.path is None) != (self.anchor is None):
            raise ValueError("path and anchor must be supplied together")
        if self.anchor == "":
            raise ValueError("empty source anchor")
        keys = [key for key, _ in self.metadata]
        if len(keys) != len(set(keys)) or any(not key for key in keys):
            raise ValueError("origin metadata keys must be unique and nonempty")

    @property
    def meta(self) -> dict[str, str]:
        return dict(self.metadata)


@dataclass(frozen=True, order=True)
class Fact:
    name: str
    literal: str
    origins: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("facts require names")
        _validate_literal(self.literal)
        if len(set(self.origins)) != len(self.origins):
            raise ValueError("duplicate origin in fact")


@dataclass(frozen=True, order=True)
class Rule:
    name: str
    body: tuple[str, ...]
    head: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("rules require names")
        _validate_literal(self.head)
        for literal in self.body:
            _validate_literal(literal)
        if len(set(self.body)) != len(self.body):
            raise ValueError("duplicate body literal")
        if self.head in self.body:
            # Cycles are allowed globally, but a direct tautology adds no support.
            raise ValueError("directly tautological rules are excluded")


@dataclass(frozen=True)
class Problem:
    name: str
    origins: tuple[Origin, ...]
    facts: tuple[Fact, ...]
    rules: tuple[Rule, ...]
    positive: str
    negative: str
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("problem requires an identity")
        _validate_literal(self.positive)
        _validate_literal(self.negative)
        if self.negative != negate(self.positive):
            raise ValueError("targets must be a strong-negation pair")
        origin_ids = [o.identifier for o in self.origins]
        if len(set(origin_ids)) != len(origin_ids):
            raise ValueError("duplicate origin identifier")
        fact_names = [f.name for f in self.facts]
        rule_names = [r.name for r in self.rules]
        if len(set(fact_names)) != len(fact_names):
            raise ValueError("duplicate fact name")
        if len(set(rule_names)) != len(rule_names):
            raise ValueError("duplicate rule name")
        if set(fact_names) & set(rule_names):
            raise ValueError("fact and rule names must be disjoint")
        metadata_keys = [key for key, _ in self.metadata]
        if len(metadata_keys) != len(set(metadata_keys)) or any(not key for key in metadata_keys):
            raise ValueError("problem metadata keys must be unique and nonempty")
        known = set(origin_ids)
        for fact in self.facts:
            if not set(fact.origins) <= known:
                raise ValueError(f"unknown origin in fact {fact.name}")

    @property
    def origin_map(self) -> dict[str, Origin]:
        return {o.identifier: o for o in self.origins}

    @property
    def meta(self) -> dict[str, str]:
        return dict(self.metadata)


@dataclass(frozen=True)
class Proof:
    literal: str
    support: frozenset[str]
    step: str
    premises: tuple["Proof", ...] = ()

    @property
    def depth(self) -> int:
        return 1 + max((p.depth for p in self.premises), default=0)

    @property
    def nodes(self) -> int:
        return 1 + sum(p.nodes for p in self.premises)


@dataclass(frozen=True)
class Solution:
    problem: str
    selected: frozenset[str]
    cost: int
    positive_proof: Proof
    negative_proof: Proof
    positive_frontier: int
    negative_frontier: int
    total_frontier_entries: int
    iterations: int


def negate(literal: str) -> str:
    """Return the canonical syntactic strong opposite of ``literal``.

    Exactly one leading ``not:`` prefix is permitted.  Consequently the
    operation is an involution, including when the ordered target pair is
    supplied in the reverse orientation.
    """
    _validate_literal(literal)
    if literal.startswith("not:"):
        opposite = literal[4:]
        _validate_literal(opposite)
        return opposite
    return "not:" + literal


def support_cost(problem: Problem, support: Iterable[str]) -> int:
    return _support_cost(problem.origin_map, support)


def _support_cost(weights: Mapping[str, Origin], support: Iterable[str]) -> int:
    ids = frozenset(support)
    if not ids <= weights.keys():
        raise ValueError("support contains unknown origin")
    return sum(weights[x].weight for x in ids)


def _proof_key(weights: Mapping[str, Origin], proof: Proof) -> tuple[int, int, tuple[str, ...], str]:
    return (_support_cost(weights, proof.support), len(proof.support), tuple(sorted(proof.support)), proof.step)


def _insert_antichain(weights: Mapping[str, Origin], frontier: dict[frozenset[str], Proof], proof: Proof) -> bool:
    """Insert a support if no existing support is a subset; remove strict supersets."""
    if proof.support in frontier:
        if _proof_key(weights, proof) < _proof_key(weights, frontier[proof.support]):
            frontier[proof.support] = proof
        return False
    if any(existing <= proof.support for existing in frontier):
        return False
    supersets = [existing for existing in frontier if proof.support < existing]
    for existing in supersets:
        del frontier[existing]
    frontier[proof.support] = proof
    return True


def derive_antichains(problem: Problem, *, max_frontier_entries: int = 100_000) -> tuple[dict[str, dict[frozenset[str], Proof]], int]:
    """Compute all inclusion-minimal origin supports for every derivable literal.

    This is exact for the finite positive-Horn language.  The worst case is
    exponential in the number of selectable origins, so a defensive frontier
    cap turns pathological inputs into an explicit error rather than resource
    exhaustion.
    """
    return _derive_antichains(problem, MappingProxyType(problem.origin_map), max_frontier_entries)


def _derive_antichains(problem: Problem, weights: Mapping[str, Origin], max_frontier_entries: int):
    if type(max_frontier_entries) is not int or max_frontier_entries < 0:
        raise ValueError("max_frontier_entries must be a non-negative integer")
    frontiers: dict[str, dict[frozenset[str], Proof]] = {}
    for fact in sorted(problem.facts):
        proof = Proof(fact.literal, frozenset(fact.origins), fact.name)
        if _insert_antichain(weights, frontiers.setdefault(fact.literal, {}), proof):
            if sum(len(v) for v in frontiers.values()) > max_frontier_entries:
                raise RuntimeError("provenance frontier cap exceeded during fact initialization")
    iterations = 0
    while True:
        iterations += 1
        changed = False
        for rule in sorted(problem.rules):
            if any(literal not in frontiers for literal in rule.body):
                continue
            premise_options: list[list[Proof]] = []
            for literal in rule.body:
                premise_options.append(sorted(frontiers[literal].values(), key=lambda p: _proof_key(weights, p)))
            combinations_iter = product(*premise_options) if premise_options else [()]
            target = frontiers.setdefault(rule.head, {})
            for premises in combinations_iter:
                support = frozenset().union(*(p.support for p in premises)) if premises else frozenset()
                proof = Proof(rule.head, support, rule.name, tuple(premises))
                if _insert_antichain(weights, target, proof):
                    changed = True
                    if sum(len(v) for v in frontiers.values()) > max_frontier_entries:
                        raise RuntimeError("provenance frontier cap exceeded")
        if not changed:
            return frontiers, iterations


def solve_exact(problem: Problem, *, max_frontier_entries: int = 100_000) -> Solution | None:
    weights = MappingProxyType(problem.origin_map)
    frontiers, iterations = _derive_antichains(problem, weights, max_frontier_entries)
    if problem.positive not in frontiers or problem.negative not in frontiers:
        return None
    pos = sorted(frontiers[problem.positive].values(), key=lambda p: _proof_key(weights, p))
    neg = sorted(frontiers[problem.negative].values(), key=lambda p: _proof_key(weights, p))
    best: tuple[tuple[int, int, tuple[str, ...], str, str], Proof, Proof, frozenset[str]] | None = None
    for p, n in product(pos, neg):
        union = p.support | n.support
        key = (_support_cost(weights, union), len(union), tuple(sorted(union)), p.step, n.step)
        if best is None or key < best[0]:
            best = (key, p, n, union)
    assert best is not None
    total = sum(len(v) for v in frontiers.values())
    return Solution(problem.name, best[3], best[0][0], best[1], best[2], len(pos), len(neg), total, iterations)


def independent_sides(problem: Problem) -> Solution | None:
    """Choose exact one-side minima; their union obeys the tight factor-two cost bound."""
    weights = MappingProxyType(problem.origin_map)
    frontiers, iterations = _derive_antichains(problem, weights, 100_000)
    if problem.positive not in frontiers or problem.negative not in frontiers:
        return None
    p = min(frontiers[problem.positive].values(), key=lambda x: _proof_key(weights, x))
    n = min(frontiers[problem.negative].values(), key=lambda x: _proof_key(weights, x))
    union = p.support | n.support
    return Solution(problem.name, union, _support_cost(weights, union), p, n,
                    len(frontiers[problem.positive]), len(frontiers[problem.negative]),
                    sum(len(v) for v in frontiers.values()), iterations)


def closure(problem: Problem, selected: Iterable[str]) -> frozenset[str]:
    selected_set = frozenset(selected)
    known_ids = set(problem.origin_map)
    if not selected_set <= known_ids:
        raise ValueError("selection contains unknown origin")
    known = {fact.literal for fact in problem.facts if set(fact.origins) <= selected_set}
    while True:
        added = {rule.head for rule in problem.rules if set(rule.body) <= known}
        new = added - known
        if not new:
            return frozenset(known)
        known |= new


def contradictory(problem: Problem, selected: Iterable[str]) -> bool:
    known = closure(problem, selected)
    return problem.positive in known and problem.negative in known


def brute_force_optimum(problem: Problem, *, limit: int = 20) -> frozenset[str] | None:
    """Enumerate every origin subset with an independent bit-mask Horn evaluator.

    The production solver propagates antichains of provenance sets.  This oracle
    deliberately uses a different representation: each origin selection and each
    derived-literal set is an integer mask.  It still visits all ``2**n`` origin
    subsets because zero-weight origins make cardinality-based early stopping
    unsound for the weighted objective.
    """
    ids = tuple(sorted(problem.origin_map))
    if len(ids) > limit:
        raise ValueError(f"brute-force oracle limited to {limit} origins")

    origin_index = {identifier: i for i, identifier in enumerate(ids)}
    weights = tuple(problem.origin_map[identifier].weight for identifier in ids)
    literals = sorted(
        {problem.positive, problem.negative}
        | {fact.literal for fact in problem.facts}
        | {rule.head for rule in problem.rules}
        | {literal for rule in problem.rules for literal in rule.body}
    )
    literal_bit = {literal: 1 << i for i, literal in enumerate(literals)}
    facts = tuple(
        (literal_bit[fact.literal], sum(1 << origin_index[o] for o in fact.origins))
        for fact in problem.facts
    )
    rules = tuple(
        (sum(literal_bit[literal] for literal in rule.body), literal_bit[rule.head])
        for rule in problem.rules
    )
    target_bits = literal_bit[problem.positive] | literal_bit[problem.negative]

    subset_count = 1 << len(ids)
    costs = [0] * subset_count
    best: tuple[int, int, tuple[str, ...]] | None = None
    best_mask: int | None = None
    full_origin_mask = subset_count - 1

    for selected_mask in range(subset_count):
        if selected_mask:
            least = selected_mask & -selected_mask
            index = least.bit_length() - 1
            costs[selected_mask] = costs[selected_mask ^ least] + weights[index]
        if best is not None and costs[selected_mask] > best[0]:
            # The selection cannot beat the best weighted cost; no closure is needed.
            continue

        known = 0
        missing_mask = full_origin_mask ^ selected_mask
        for literal, support in facts:
            if support & missing_mask == 0:
                known |= literal
        while True:
            previous = known
            for body, head in rules:
                if body & known == body:
                    known |= head
            if known == previous:
                break
        if known & target_bits != target_bits:
            continue

        selected_ids = tuple(ids[i] for i in range(len(ids)) if selected_mask & (1 << i))
        key = (costs[selected_mask], selected_mask.bit_count(), selected_ids)
        if best is None or key < best:
            best, best_mask = key, selected_mask

    if best_mask is None:
        return None
    return frozenset(ids[i] for i in range(len(ids)) if best_mask & (1 << i))


def greedy_delete(problem: Problem, order: Sequence[str] | None = None) -> frozenset[str] | None:
    ids = tuple(order) if order is not None else tuple(sorted(problem.origin_map))
    if set(ids) != set(problem.origin_map) or len(ids) != len(set(ids)):
        raise ValueError("deletion order must contain every origin exactly once")
    current = set(ids)
    if not contradictory(problem, current):
        return None
    for origin in ids:
        candidate = current - {origin}
        if contradictory(problem, candidate):
            current = candidate
    return frozenset(current)


def is_inclusion_minimal(problem: Problem, selected: Iterable[str]) -> bool:
    chosen = frozenset(selected)
    return contradictory(problem, chosen) and all(not contradictory(problem, chosen - {x}) for x in chosen)


def proof_to_dict(proof: Proof) -> dict:
    return {
        "literal": proof.literal,
        "support": sorted(proof.support),
        "step": proof.step,
        "premises": [proof_to_dict(p) for p in proof.premises],
    }


def problem_to_dict(problem: Problem) -> dict:
    return {
        "name": problem.name,
        "positive": problem.positive,
        "negative": problem.negative,
        "metadata": dict(problem.metadata),
        "origins": [
            {
                "id": o.identifier,
                "kind": o.kind,
                "weight": o.weight,
                "path": o.path,
                "anchor": o.anchor,
                "metadata": dict(o.metadata),
            }
            for o in problem.origins
        ],
        "facts": [
            {"name": f.name, "literal": f.literal, "origins": list(f.origins)}
            for f in problem.facts
        ],
        "rules": [
            {"name": r.name, "body": list(r.body), "head": r.head}
            for r in problem.rules
        ],
    }


def solution_to_dict(problem: Problem, solution: Solution | None, *, algorithm: str) -> dict:
    if solution is None:
        return {"algorithm": algorithm, "status": "no-contradiction-certificate"}
    return {
        "algorithm": algorithm,
        "status": "certificate",
        "selected": sorted(solution.selected),
        "cost": solution.cost,
        "positive_proof": proof_to_dict(solution.positive_proof),
        "negative_proof": proof_to_dict(solution.negative_proof),
        "metrics": {
            "positive_frontier": solution.positive_frontier,
            "negative_frontier": solution.negative_frontier,
            "total_frontier_entries": solution.total_frontier_entries,
            "iterations": solution.iterations,
            "positive_depth": solution.positive_proof.depth,
            "negative_depth": solution.negative_proof.depth,
        },
    }


def make_tight_two_approx(k: int) -> Problem:
    """Family with independent-side/OPT ratio 2k/(k+1), tending to two."""
    if type(k) is not int or k < 2:
        raise ValueError("k must be an integer at least two")
    origins = []
    for prefix, count in (("a", k), ("b", k), ("s", k + 1)):
        origins.extend(Origin(f"{prefix}{i}", "seed", 1) for i in range(count))
    facts = (
        Fact("pos-private", "p-private", tuple(f"a{i}" for i in range(k))),
        Fact("neg-private", "n-private", tuple(f"b{i}" for i in range(k))),
        Fact("pos-shared", "p-shared", tuple(f"s{i}" for i in range(k + 1))),
        Fact("neg-shared", "n-shared", tuple(f"s{i}" for i in range(k + 1))),
    )
    rules = (
        Rule("pp-to-p", ("p-private",), "p"),
        Rule("ps-to-p", ("p-shared",), "p"),
        Rule("np-to-not-p", ("n-private",), "not:p"),
        Rule("ns-to-not-p", ("n-shared",), "not:p"),
    )
    return Problem(f"tight-2approx-k{k}", tuple(origins), facts, rules, "p", "not:p")


def make_deletion_gap(n: int) -> tuple[Problem, tuple[str, ...]]:
    """Monotone family where an adverse deletion order returns n vs optimum 1."""
    if type(n) is not int or n < 2:
        raise ValueError("n must be an integer at least two")
    origins = tuple([Origin("y", "seed", 1)] + [Origin(f"x{i}", "seed", 1) for i in range(n)])
    facts = (
        Fact("shortcut-positive", "p-short", ("y",)),
        Fact("shortcut-negative", "n-short", ("y",)),
        Fact("long-positive", "p-long", tuple(f"x{i}" for i in range(n))),
        Fact("long-negative", "n-long", tuple(f"x{i}" for i in range(n))),
    )
    rules = (
        Rule("short-p", ("p-short",), "p"), Rule("short-n", ("n-short",), "not:p"),
        Rule("long-p", ("p-long",), "p"), Rule("long-n", ("n-long",), "not:p"),
    )
    # y is tested first, so it is deleted while the long conjunction remains.
    order = ("y",) + tuple(f"x{i}" for i in range(n))
    return Problem(f"deletion-gap-n{n}", origins, facts, rules, "p", "not:p"), order
