"""Separately implemented replay: does not import producer model or extractor.
This separation is software cross-checking, not independent scientific review.
"""
from itertools import combinations, product
import json
from pathlib import Path
import re

API = {"lock", "unlock", "touch", "noop"}

def observations(source: str) -> dict[str, int]:
    if len(source.encode()) > 262144:
        raise ValueError("source bound")
    # Preserve newlines while removing comments. Reject every unmatched text span.
    source = re.sub(r"/\*.*?\*/|//[^\n]*", lambda m: " "+"\n"*m.group().count("\n"), source, flags=re.S)
    decl = re.compile(r"\s*void\s+([A-Za-z_]\w*)\s*\(\s*void\s*\)\s*(;|\{([^{}]*)\})", re.ASCII)
    cursor, seen, result = 0, set(), {}
    while source[cursor:].strip():
        m = decl.match(source, cursor)
        if not m:
            raise ValueError("unsupported C declaration")
        cursor = m.end()
        name, kind, body = m.group(1, 2, 3)
        if kind == ";":
            if name not in API:
                raise ValueError("unknown prototype")
            continue
        if name in seen or name in API:
            raise ValueError("duplicate or reserved name")
        seen.add(name)
        if len(seen) > 128:
            raise ValueError("function bound")
        segments = body.split(";")
        if segments[-1].strip():
            raise ValueError("unterminated statement")
        held = False
        got_protected = got_unprotected = False
        for segment in segments[:-1]:
            call = re.fullmatch(r"\s*(lock|unlock|touch|noop)\s*\(\s*\)\s*", segment)
            if not call:
                raise ValueError("unsupported statement")
            op = call.group(1)
            if op == "lock":
                if held:
                    raise ValueError("nested lock")
                held = True
            elif op == "unlock":
                if not held:
                    raise ValueError("unmatched unlock")
                held = False
            elif op == "touch":
                if held: got_protected = True
                else: got_unprotected = True
        if held:
            raise ValueError("unclosed scope")
        if got_protected or got_unprotected:
            result[name] = int(got_protected) + 2*int(got_unprotected)
    return result


def truth(features: tuple[int, ...], selected: tuple[int, ...], a: int, b: int, mode: str) -> bool:
    """Direct integer counts, no bit-mask truth-table reuse."""
    if mode not in ("remined", "pinned"):
        raise ValueError("unknown mode")
    denominator = len(selected) if mode == "remined" else len(features)
    yes = sum(features[i] in (1, 3) for i in selected)
    no = sum(features[i] in (2, 3) for i in selected)
    return denominator > 0 and b*yes >= a*denominator and b*no >= a*denominator


def sat_model(clauses, atoms: int):
    """Brute-force classical Horn satisfaction, independent of forward chaining."""
    for assignment in product((False, True), repeat=atoms):
        if all(not all(assignment[i] for i in c.body) or
               (c.head is not None and assignment[c.head]) for c in clauses):
            return assignment
    return None


def check_derivation(clauses, trace, atoms):
    if type(atoms) is not int or not 0 <= atoms <= 16:
        raise ValueError("atom bound")
    for c in clauses:
        if (not isinstance(c.name, str) or not c.name or len(set(c.body)) != len(c.body)
                or any(type(x) is not int or not 0 <= x < atoms for x in c.body)
                or (c.head is not None and (type(c.head) is not int or not 0 <= c.head < atoms))):
            raise ValueError("invalid Horn clause")
    by_name = {c.name: c for c in clauses}
    if len(by_name) != len(clauses):
        raise ValueError("duplicate clause name")
    known, used = set(), set()
    for j, name in enumerate(trace):
        if name not in by_name or name in used:
            return False
        c = by_name[name]
        if any(i not in known for i in c.body):
            return False
        used.add(name)
        if c.head is None:
            return j == len(trace)-1
        if not 0 <= c.head < atoms or c.head in known:
            return False
        known.add(c.head)
    return False


def check_certificate(root: Path, certificate: dict) -> dict:
    if not isinstance(certificate, dict) or certificate.get("kind") != "population-selection":
        raise ValueError("certificate kind")
    p = Path(certificate["source"])
    if p.is_absolute() or ".." in p.parts or not p.parts or p.parts[0] != "inputs":
        raise ValueError("source must be contained in inputs")
    full = (root/p).resolve()
    if not full.is_relative_to((root/"inputs").resolve()):
        raise ValueError("source escapes input root")
    source = full.read_text(encoding="utf-8")
    census = observations(source)
    expected = certificate["census"]
    if not isinstance(expected, dict) or any(type(v) is not int or v not in (1,2,3) for v in expected.values()) or census != expected:
        raise ValueError("census or source features mismatch")
    ids = tuple(census)
    selected = certificate["selected"]
    if not isinstance(selected, list) or len(selected) != len(set(selected)) or any(i not in census for i in selected):
        raise ValueError("selection mismatch")
    t = certificate["threshold"]
    if (not isinstance(t,list) or len(t)!=2 or any(type(x) is not int for x in t)
        or not 0 < t[0] <= t[1] <= 1000):
        raise ValueError("threshold mismatch")
    if type(certificate["snapshot"]) is not int or certificate["snapshot"] < 0:
        raise ValueError("snapshot must be a nonnegative ordinal")
    # Snapshot/source binding is checked against the retained ordered input index.
    history = json.loads((root/"inputs/index.json").read_text())
    if not any(e["source"] == str(p) and e["snapshot"] == certificate["snapshot"] for e in history):
        raise ValueError("snapshot/source mismatch")
    features = tuple(census[i] for i in ids)
    choice = tuple(ids.index(i) for i in selected)
    mode = certificate["mode"]
    valid = truth(features, choice, *t, mode)
    if not valid:
        raise ValueError("selected source evidence does not replay")
    local = all(not truth(features, tuple(j for j in choice if j != i), *t, mode) for i in choice)
    minimal = None
    minimum_size = None
    if len(ids) <= 16:
        witnesses = [s for k in range(len(ids)+1) for s in combinations(range(len(ids)), k)
                     if truth(features, s, *t, mode)]
        minimum_size = min(map(len,witnesses))
        minimal = not any(set(s) < set(choice) for s in witnesses)
    claims = certificate.get("claims", {})
    supported = {"valid": valid, "one_minimal": local, "inclusion_minimal": minimal,
                 "minimum_cardinality": (len(choice) == minimum_size) if minimum_size is not None else None}
    if not isinstance(claims, dict) or any(k not in supported or type(v) is not bool or supported[k] is not v for k,v in claims.items()):
        raise ValueError("unsupported certificate claim")
    return {"valid":valid,"one_minimal":local,"inclusion_minimal":minimal,
            "selected_size":len(choice),"minimum_size":minimum_size,"mode":mode}


def check_horn_certificate(certificate: dict) -> dict:
    """Replay a fixed-formula derivation and every single-clause deletion model.

    Inclusion minimality follows from fixed-formula monotonicity, not a
    general inference from local deletion tests under arbitrary predicates.
    """
    from types import SimpleNamespace
    if not isinstance(certificate, dict):
        raise ValueError("Horn certificate must be an object")
    atoms = certificate["atoms"]
    raw = certificate["clauses"]
    if not isinstance(raw, list) or len(raw) > 128:
        raise ValueError("clause bound")
    clauses = tuple(SimpleNamespace(name=c["name"], body=tuple(c["body"]), head=c["head"]) for c in raw)
    if not check_derivation(clauses, certificate["trace"], atoms):
        raise ValueError("invalid unsatisfiability trace")
    assignments = certificate["deletion_models"]
    if not isinstance(assignments, list) or len(assignments) != len(clauses):
        raise ValueError("one deletion model per clause required")
    for dropped, assignment in enumerate(assignments):
        if (not isinstance(assignment, (list, tuple)) or len(assignment) != atoms
                or any(type(x) is not bool for x in assignment)):
            raise ValueError("invalid Boolean assignment")
        for i, c in enumerate(clauses):
            if i != dropped and all(assignment[j] for j in c.body):
                if c.head is None or not assignment[c.head]:
                    raise ValueError("deletion model does not satisfy remaining clauses")
    return {"unsatisfiable": True, "inclusion_minimal": True,
            "clauses": len(clauses), "atoms": atoms}
