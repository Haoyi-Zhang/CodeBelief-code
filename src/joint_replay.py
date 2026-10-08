"""Independent dictionary-level replay for joint contradiction certificates.

This module deliberately does not import ``src.joint`` or the producer.  It
checks retained source anchors, endpoint/bridge contracts, proof trees, fixed
Horn closure, and exact optimality for the bounded public cases by enumerating
origin subsets.
"""
from __future__ import annotations

from itertools import combinations
import json
from pathlib import Path, PurePosixPath
from typing import Iterable


class ReplayError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def _validate_literal(literal: object) -> str:
    require(type(literal) is str and literal and not any(ch.isspace() for ch in literal),
            "invalid literal")
    require(literal != "not:" and not literal.startswith("not:not:"),
            "literal uses noncanonical repeated not: encoding")
    return literal


def _negate(literal: object) -> str:
    literal = _validate_literal(literal)
    if literal.startswith("not:"):
        opposite = literal[4:]
        _validate_literal(opposite)
        return opposite
    return "not:" + literal


def _relative_parts(relative: object) -> tuple[str, ...]:
    require(type(relative) is str and relative, "malformed source path")
    require("\\" not in relative, "source paths must use canonical POSIX separators")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute(), "absolute source path is forbidden")
    require(relative == pure.as_posix(), "source path is not canonical")
    require(all(part not in {"", ".", ".."} for part in pure.parts),
            "source path contains a forbidden component")
    require(not (pure.parts and pure.parts[0].endswith(":")),
            "drive-qualified source path is forbidden")
    return pure.parts


def _safe_path(root: Path, relative: object) -> Path:
    parts = _relative_parts(relative)
    resolved_root = root.resolve()
    path = resolved_root.joinpath(*parts).resolve()
    require(path.is_relative_to(resolved_root), "source path escapes artifact root")
    require(path.is_file(), f"missing retained source: {relative}")
    return path


def _anchor(root: Path, path: object, anchor: object) -> None:
    require(type(anchor) is str and anchor, "malformed source anchor")
    text = _safe_path(root, path).read_text()
    require(text.count(anchor) == 1, f"source anchor must occur exactly once: {path}")


def _metadata(origin: dict) -> dict:
    metadata = origin.get("metadata", {})
    require(type(metadata) is dict, "origin metadata must be an object")
    require(all(type(key) is str and key for key in metadata), "invalid metadata key")
    return metadata


def _required_strings(mapping: dict, keys: tuple[str, ...], context: str) -> None:
    for key in keys:
        require(type(mapping.get(key)) is str and mapping[key], f"missing {context} field: {key}")


def _snapshot_bindings(root: Path) -> dict[str, tuple[str, str, str]]:
    """Bind public code records to the retained manifest, not their own labels.

    This bounded source consumer uses the packaged public excerpts. The manifest
    is trusted input provenance; checking it does not authenticate upstream tags.
    """
    manifest = json.loads((root / "inputs/public/manifest.json").read_text(encoding="utf-8"))
    require(type(manifest) is dict and type(manifest.get("projects")) is list,
            "public snapshot manifest is malformed")
    bindings = {}
    for project in manifest["projects"]:
        require(type(project) is dict, "manifest project must be an object")
        _required_strings(project, ("project",), "manifest project")
        require(type(project.get("snapshots")) is list, "manifest snapshots missing")
        for snapshot in project["snapshots"]:
            require(type(snapshot) is dict, "manifest snapshot must be an object")
            _required_strings(snapshot, ("path", "tag"), "manifest snapshot")
            parts = _relative_parts(snapshot["path"])
            require(len(parts) >= 5 and parts[:2] == ("inputs", "public")
                    and parts[3] == snapshot["tag"], "manifest snapshot/path mismatch")
            require(snapshot["path"] not in bindings, "duplicate manifest source path")
            bindings[snapshot["path"]] = (project["project"], parts[2], snapshot["tag"])
    return bindings


def validate_problem(problem: dict, root: Path) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    require(type(problem.get("name")) is str and problem["name"], "problem identity missing")
    positive = _validate_literal(problem.get("positive"))
    negative = _validate_literal(problem.get("negative"))
    require(negative == _negate(positive), "target pair mismatch")

    origin_records = problem.get("origins")
    require(type(origin_records) is list, "origin table missing")
    origins: dict[str, dict] = {}
    bindings = None
    for origin in origin_records:
        require(type(origin) is dict, "origin record must be an object")
        identifier = origin.get("id")
        require(type(identifier) is str and identifier and identifier not in origins,
                "duplicate/malformed origin")
        require(type(origin.get("weight")) is int and origin["weight"] >= 0,
                "invalid origin weight")
        kind = origin.get("kind")
        require(kind in {"code", "change", "bridge", "seed", "context"},
                "invalid origin kind")
        metadata = _metadata(origin)
        if kind == "code":
            path = origin.get("path")
            anchor = origin.get("anchor")
            _anchor(root, path, anchor)
            _required_strings(metadata, ("project", "host", "snapshot", "file"), "code metadata")
            require(metadata["file"] == path, "code metadata file/path mismatch")
            if bindings is None:
                bindings = _snapshot_bindings(root)
            require(path in bindings, "code file is not a retained public snapshot")
            require((metadata["project"], metadata["host"], metadata["snapshot"]) == bindings[path],
                    "code project/host/snapshot does not match retained manifest")
        else:
            require(origin.get("path") is None and origin.get("anchor") is None,
                    "non-code origin carries a source path/anchor")
        origins[identifier] = origin

    # Validate cross-record contracts only after the full origin table exists.
    for identifier, origin in origins.items():
        kind = origin["kind"]
        metadata = _metadata(origin)
        if kind == "change":
            keys = (
                "project", "host", "before_origin", "after_origin",
                "before_snapshot", "after_snapshot", "before_file", "after_file",
                "before_anchor", "after_anchor",
            )
            _required_strings(metadata, keys, "change metadata")
            before_id, after_id = metadata["before_origin"], metadata["after_origin"]
            require(before_id != after_id, "change endpoints reuse one origin id")
            require(before_id in origins and after_id in origins, "change endpoint id is unknown")
            before, after = origins[before_id], origins[after_id]
            require(before["kind"] == after["kind"] == "code", "change endpoints must be code origins")
            before_meta, after_meta = _metadata(before), _metadata(after)
            require(metadata["before_snapshot"] != metadata["after_snapshot"],
                    "change endpoints use the same snapshot")
            require(metadata["before_file"] != metadata["after_file"],
                    "change endpoints use the same retained file")
            require(metadata["before_anchor"] != metadata["after_anchor"],
                    "change endpoints use identical anchors")
            require(metadata["project"] == before_meta["project"] == after_meta["project"],
                    "change project does not match endpoint records")
            require(metadata["host"] == before_meta["host"] == after_meta["host"],
                    "change host does not match endpoint records")
            require(metadata["before_snapshot"] == before_meta["snapshot"] and
                    metadata["after_snapshot"] == after_meta["snapshot"],
                    "change snapshot does not match endpoint id")
            require(metadata["before_file"] == before["path"] and
                    metadata["after_file"] == after["path"],
                    "change file does not match endpoint id")
            require(metadata["before_anchor"] == before["anchor"] and
                    metadata["after_anchor"] == after["anchor"],
                    "change anchor does not match endpoint id")
        elif kind == "bridge":
            keys = (
                "project", "host", "before_origin", "after_origin",
                "before_snapshot", "after_snapshot", "assumption",
            )
            _required_strings(metadata, keys, "bridge metadata")
            before_id, after_id = metadata["before_origin"], metadata["after_origin"]
            require(before_id != after_id, "bridge endpoints reuse one origin id")
            require(before_id in origins and after_id in origins, "bridge endpoint id is unknown")
            before, after = origins[before_id], origins[after_id]
            require(before["kind"] == after["kind"] == "code", "bridge endpoints must be code origins")
            before_meta, after_meta = _metadata(before), _metadata(after)
            require(metadata["before_snapshot"] != metadata["after_snapshot"],
                    "bridge endpoints use the same snapshot")
            require(metadata["project"] == before_meta["project"] == after_meta["project"],
                    "bridge project does not match endpoint records")
            require(metadata["host"] == before_meta["host"] == after_meta["host"],
                    "bridge host does not match endpoint records")
            require(metadata["before_snapshot"] == before_meta["snapshot"] and
                    metadata["after_snapshot"] == after_meta["snapshot"],
                    "bridge snapshot does not match endpoint id")

    fact_records = problem.get("facts")
    require(type(fact_records) is list, "fact table missing")
    facts: dict[str, dict] = {}
    for fact in fact_records:
        require(type(fact) is dict, "fact record must be an object")
        name = fact.get("name")
        require(type(name) is str and name and name not in facts, "duplicate/malformed fact")
        ids = fact.get("origins")
        require(type(ids) is list and len(ids) == len(set(ids)) and set(ids) <= origins.keys(),
                "invalid fact origins")
        _validate_literal(fact.get("literal"))
        facts[name] = fact

    rule_records = problem.get("rules")
    require(type(rule_records) is list, "rule table missing")
    rules: dict[str, dict] = {}
    for rule in rule_records:
        require(type(rule) is dict, "rule record must be an object")
        name = rule.get("name")
        require(type(name) is str and name and name not in rules and name not in facts,
                "duplicate/malformed rule")
        body = rule.get("body")
        require(type(body) is list and len(body) == len(set(body)), "invalid rule body")
        for literal in body:
            _validate_literal(literal)
        head = _validate_literal(rule.get("head"))
        require(head not in body, "directly tautological rule is excluded")
        rules[name] = rule
    return origins, facts, rules


def _replay_step(node: dict, replayed: list[tuple[str, frozenset[str]]],
                 facts: dict[str, dict], rules: dict[str, dict]) -> tuple[str, frozenset[str]]:
    require(type(node) is dict, "proof node must be an object")
    step = node.get("step")
    literal = _validate_literal(node.get("literal"))
    support_list = node.get("support")
    premises = node.get("premises")
    require(type(support_list) is list and type(premises) is list, "malformed proof node")
    require(support_list == sorted(support_list), "proof support is not canonically ordered")
    support = frozenset(support_list)
    require(len(support) == len(support_list), "duplicate support entry")
    if step in facts:
        fact = facts[step]
        require(not premises, "fact node has premises")
        require(literal == fact["literal"], "fact literal mismatch")
        require(support == frozenset(fact["origins"]), "fact support mismatch")
    elif step in rules:
        rule = rules[step]
        require(literal == rule["head"], "rule head mismatch")
        require(len(premises) == len(rule["body"]), "rule arity mismatch")
        require([x[0] for x in replayed] == rule["body"], "rule premise order/literals mismatch")
        union = frozenset().union(*(x[1] for x in replayed)) if replayed else frozenset()
        require(support == union, "rule support union mismatch")
    else:
        raise ReplayError(f"unknown proof step: {step}")
    return literal, support


def replay_proof(node: dict, facts: dict[str, dict], rules: dict[str, dict]) -> tuple[str, frozenset[str]]:
    """Replay nested trees or flat proof DAGs by iterative postorder."""
    require(type(node) is dict, "proof must be an object")
    flat = node.get("format") == "proof-dag"
    if flat:
        table = node.get("nodes")
        root = node.get("root")
        require(type(table) is list and table, "proof DAG has no nodes")
        require(type(root) is int and 0 <= root < len(table), "invalid proof root")

        def record(key):
            require(type(key) is int and 0 <= key < len(table), "invalid premise index")
            value = table[key]
            require(type(value) is dict, "proof node must be an object")
            return value

        def identity(key):
            return key
    else:
        root = node

        def record(key):
            require(type(key) is dict, "proof node must be an object")
            return key

        def identity(key):
            return id(key)

    values: dict[int, tuple[str, frozenset[str]]] = {}
    active: set[int] = set()
    pending = [(root, False)]
    while pending:
        key, expanded = pending.pop()
        current = record(key)
        idx = identity(key)
        if idx in values:
            continue
        premises = current.get("premises")
        require(type(premises) is list, "proof premises must be a list")
        if expanded:
            values[idx] = _replay_step(
                current, [values[identity(child)] for child in premises], facts, rules
            )
            active.remove(idx)
            continue
        require(idx not in active, "cyclic proof")
        active.add(idx)
        pending.append((key, True))
        pending.extend((child, False) for child in reversed(premises))
    if flat:
        require(len(values) == len(table), "proof DAG contains unreachable nodes")
    return values[identity(root)]


def closure(problem: dict, selected: Iterable[str]) -> frozenset[str]:
    selected = frozenset(selected)
    known = {
        fact["literal"] for fact in problem["facts"]
        if set(fact["origins"]) <= selected
    }
    while True:
        add = {
            rule["head"] for rule in problem["rules"]
            if set(rule["body"]) <= known
        } - known
        if not add:
            return frozenset(known)
        known |= add


def contradictory(problem: dict, selected: Iterable[str]) -> bool:
    known = closure(problem, selected)
    return problem["positive"] in known and problem["negative"] in known


def cost(origins: dict[str, dict], selected: Iterable[str]) -> int:
    ids = frozenset(selected)
    require(ids <= origins.keys(), "selection contains unknown origin")
    return sum(origins[x]["weight"] for x in ids)


def exact_oracle(problem: dict, origins: dict[str, dict], limit: int = 16) -> tuple[int, frozenset[str]] | None:
    ids = tuple(sorted(origins))
    require(len(ids) <= limit, "independent oracle bound exceeded")
    best: tuple[tuple[int, int, tuple[str, ...]], frozenset[str]] | None = None
    for size in range(len(ids) + 1):
        for subset in combinations(ids, size):
            if contradictory(problem, subset):
                key = (cost(origins, subset), len(subset), subset)
                if best is None or key < best[0]:
                    best = (key, frozenset(subset))
    return None if best is None else (best[0][0], best[1])


def replay_certificate(document: dict, root: Path) -> dict:
    require(document.get("schema") == "joint-contradiction-certificate-v1", "certificate schema mismatch")
    problem = document.get("problem")
    solution = document.get("solution")
    require(type(problem) is dict and type(solution) is dict, "certificate sections missing")
    origins, facts, rules = validate_problem(problem, root)
    oracle = exact_oracle(problem, origins)
    status = solution.get("status")
    reported_oracle = document.get("oracle_selected")
    if status == "no-contradiction-certificate":
        require(oracle is None, "producer reported no certificate but oracle found one")
        require(reported_oracle is None, "negative document carries an oracle witness")
        return {"case": problem["name"], "status": status, "oracle": "none"}

    require(status == "certificate", "unknown solution status")
    selected_list = solution.get("selected")
    require(type(selected_list) is list and selected_list == sorted(selected_list),
            "selection is not a canonical list")
    require(len(selected_list) == len(set(selected_list)), "selection contains duplicates")
    selected = frozenset(selected_list)
    require(selected <= origins.keys(), "unknown selected origin")
    p_lit, p_support = replay_proof(solution.get("positive_proof"), facts, rules)
    n_lit, n_support = replay_proof(solution.get("negative_proof"), facts, rules)
    require(p_lit == problem["positive"] and n_lit == problem["negative"],
            "proof conclusions mismatch")
    require(selected == p_support | n_support, "selection is not proof-support union")
    require(contradictory(problem, selected), "selected origins do not replay contradiction")
    reported_cost = solution.get("cost")
    require(type(reported_cost) is int and reported_cost == cost(origins, selected),
            "reported cost mismatch")
    require(oracle is not None and oracle[0] == reported_cost,
            "certificate is not globally minimum")

    require(type(reported_oracle) is list and reported_oracle == sorted(reported_oracle),
            "producer oracle witness is not a canonical list")
    require(len(reported_oracle) == len(set(reported_oracle)),
            "producer oracle witness contains duplicates")
    oracle_witness = frozenset(reported_oracle)
    require(oracle_witness <= origins.keys(), "producer oracle witness contains an unknown origin")
    require(contradictory(problem, oracle_witness), "producer oracle witness is infeasible")
    require(cost(origins, oracle_witness) == oracle[0],
            "producer oracle witness is not minimum-cost")

    return {
        "case": problem["name"],
        "status": status,
        "cost": reported_cost,
        "selected_origins": len(selected),
        "oracle_cost": oracle[0],
        "oracle_witness_origins": len(oracle_witness),
    }
