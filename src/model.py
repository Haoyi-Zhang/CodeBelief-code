"""Exact finite model. No external dependencies, code execution, or probabilities."""
from dataclasses import dataclass
from itertools import combinations, product
from typing import Callable, Iterable

@dataclass(frozen=True)
class Threshold:
    numerator: int
    denominator: int
    def __post_init__(self):
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise ValueError("integer threshold required")
        if not 0 < self.numerator <= self.denominator <= 1000:
            raise ValueError("require 0 < numerator <= denominator <= 1000")
    def passes(self, support: int, population: int) -> bool:
        return population > 0 and support*self.denominator >= self.numerator*population


def valid(features: tuple[int, ...], chosen: Iterable[int], threshold: Threshold,
          mode: str = "remined") -> bool:
    ids = tuple(chosen)
    if len(set(ids)) != len(ids) or any(type(i) is not int or not 0 <= i < len(features) for i in ids):
        raise ValueError("invalid selection")
    if any(type(f) is not int or f not in (1, 2, 3) for f in features):
        raise ValueError("features must be nonempty subsets of two support types")
    if mode not in ("remined", "pinned"):
        raise ValueError("unknown replay mode")
    denominator = len(ids) if mode == "remined" else len(features)
    return all(threshold.passes(sum(bool(features[i] & bit) for i in ids), denominator)
               for bit in (1, 2))


def closed_form_minimum(features: tuple[int, ...], threshold: Threshold,
                        mode: str = "remined") -> tuple[int, ...] | None:
    """Two-support fragment only. Not a general belief-language algorithm.

    Re-mining collapses to a shared singleton or (at threshold <= 1/2) an
    opposite pair. A pinned population is an elementary two-cover problem.
    """
    # Use the public predicate to validate the finite input domain.
    valid(features, (), threshold, mode)
    shared = tuple(i for i, value in enumerate(features) if value == 3)
    positive = tuple(i for i, value in enumerate(features) if value == 1)
    negative = tuple(i for i, value in enumerate(features) if value == 2)
    if mode == "remined":
        if shared:
            return shared[:1]
        if (2 * threshold.numerator <= threshold.denominator
                and positive and negative):
            return tuple(sorted((positive[0], negative[0])))
        return None
    n = len(features)
    if not valid(features, range(n), threshold, mode):
        return None
    k = (threshold.numerator * n + threshold.denominator - 1) // threshold.denominator
    take_shared = min(k, len(shared))
    result = shared[:take_shared] + positive[:k-take_shared] + negative[:k-take_shared]
    return tuple(sorted(result))


def shrink(items: Iterable[int], predicate: Callable[[tuple[int, ...]], bool],
           repeat: bool = False) -> tuple[int, ...]:
    """Single deletion pass or repeat-to-1-minimal; NOT global minimization."""
    result = tuple(items)
    if not predicate(result):
        raise ValueError("starting set must satisfy predicate")
    while True:
        changed = False
        for x in tuple(result):
            candidate = tuple(y for y in result if y != x)
            if predicate(candidate):
                result = candidate
                changed = True
        if not repeat or not changed:
            return result


def exact_minimum(items: Iterable[int], predicate: Callable[[tuple[int, ...]], bool]) -> tuple[int, ...] | None:
    items = tuple(items)
    if len(items) > 16:
        raise ValueError("exact subset enumeration limited to 16 items")
    for k in range(len(items)+1):
        for subset in combinations(items, k):
            if predicate(subset):
                return subset
    return None


def one_minimal(items: tuple[int, ...], predicate: Callable[[tuple[int, ...]], bool]) -> bool:
    return predicate(items) and all(not predicate(tuple(y for y in items if y != x)) for x in items)


def inclusion_minimal(items: tuple[int, ...], predicate: Callable[[tuple[int, ...]], bool]) -> bool:
    if len(items) > 16:
        raise ValueError("exact subset enumeration limited to 16 items")
    return predicate(items) and not any(predicate(c) for k in range(len(items)) for c in combinations(items, k))


@dataclass(frozen=True)
class Clause:
    name: str
    body: tuple[int, ...]
    head: int | None  # None is false, not a signed atom.


def validate_clauses(clauses: tuple[Clause, ...], atoms: int) -> None:
    if type(atoms) is not int or not 0 <= atoms <= 16:
        raise ValueError("atom bound exceeded")
    if len({c.name for c in clauses}) != len(clauses):
        raise ValueError("duplicate clause names")
    for c in clauses:
        if len(set(c.body)) != len(c.body) or any(type(a) is not int or not 0 <= a < atoms for a in c.body):
            raise ValueError("invalid body")
        if c.head is not None and (type(c.head) is not int or not 0 <= c.head < atoms):
            raise ValueError("invalid head")


def horn_close(clauses: tuple[Clause, ...], atoms: int) -> tuple[bool, tuple[str, ...], tuple[int, ...]]:
    """Return (unsatisfiable, derivation, least positive closure).
    Negative units are body=(p,), head=None. Negative antecedents are not in this fragment.
    """
    validate_clauses(clauses, atoms)
    known: set[int] = set()
    trace: list[str] = []
    while True:
        changed = False
        for c in clauses:
            if all(a in known for a in c.body):
                if c.head is None:
                    return True, tuple(trace+[c.name]), tuple(sorted(known))
                if c.head not in known:
                    known.add(c.head)
                    trace.append(c.name)
                    changed = True
        if not changed:
            return False, tuple(trace), tuple(sorted(known))


def horn_universe(atoms: int) -> tuple[Clause, ...]:
    clauses = []
    for k in range(atoms+1):
        for b in combinations(range(atoms), k):
            for h in (*range(atoms), None):
                if h not in b:
                    clauses.append(Clause(f"c{len(clauses):02}", b, h))
    return tuple(clauses)
