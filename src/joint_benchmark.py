"""Deterministic public-host, oracle, and theorem-family campaign."""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import time
from pathlib import Path

from .joint import (
    Fact, Origin, Problem, Rule, brute_force_optimum, greedy_delete,
    independent_sides, is_inclusion_minimal, make_deletion_gap,
    make_tight_two_approx, problem_to_dict, solution_to_dict, solve_exact,
    support_cost,
)

ROOT = Path(__file__).resolve().parents[1]


def dump_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def dump_jsonl(path: Path, values) -> None:
    path.write_text("".join(json.dumps(v, sort_keys=True) + "\n" for v in values))


HOSTS = {
    "cjson": {
        "project": "cJSON",
        "before_tag": "v1.7.17",
        "after_tag": "v1.7.18",
        "before_path": "inputs/public/cjson/v1.7.17/cJSON_SetValuestring.c",
        "after_path": "inputs/public/cjson/v1.7.18/cJSON_SetValuestring.c",
        "before_feature": "if (object->valuestring == NULL)",
        "after_feature": "if (object->valuestring == NULL || valuestring == NULL)",
        "before_context": "if (strlen(valuestring) <= strlen(object->valuestring))",
        "after_context": "if (strlen(valuestring) <= strlen(object->valuestring))",
        "shared_context": "CJSON_PUBLIC(char*) cJSON_SetValuestring(cJSON *object, const char *valuestring)",
        "policy": "policy:cjson:valuestring-null-guard",
    },
    "inih": {
        "project": "inih",
        "before_tag": "r58",
        "after_tag": "r59",
        "before_path": "inputs/public/inih/r58/ini_parse_stream_excerpt.c",
        "after_path": "inputs/public/inih/r59/ini_parse_stream_excerpt.c",
        "before_feature": "if (max_line >= INI_MAX_LINE)\n                break;",
        "after_feature": "char abyss[16];  /* Used to consume input when a line is too long. */",
        "before_context": "while (offset == max_line - 1 && line[offset - 1] != '\\n')",
        "after_context": "while (offset == max_line - 1 && line[offset - 1] != '\\n')",
        "shared_context": "int ini_parse_stream(ini_reader reader, void* stream, ini_handler handler,",
        "policy": "policy:inih:consume-overlong-line",
    },
    "mjson": {
        "project": "mjson",
        "before_tag": "1.2.6",
        "after_tag": "1.2.7",
        "before_path": "inputs/public/mjson/1.2.6/mjson_print_dbl.c",
        "after_path": "inputs/public/mjson/1.2.7/mjson_print_dbl.c",
        "before_feature": "for (i = 0, t = mul; d >= 1.0 && s + n < (int) sizeof(buf); i++)",
        "after_feature": "for (i = 0, t = mul; t >= 1.0 && s + n < (int) sizeof(buf); i++)",
        "before_context": "while (n > 0 && buf[s + n - 1] == '0') n--;  // Trim trailing zeros",
        "after_context": "while (n > 0 && buf[s + n - 1] == '0') n--;  // Trim trailing zeros",
        "shared_context": "int mjson_print_dbl(mjson_print_fn_t fn, void *fnd, double d, int width)",
        "policy": "policy:mjson:place-controlled-integer-loop",
    },
}


def _code(identifier: str, path: str, anchor: str, weight: int, *, host_key: str, host: dict, snapshot: str) -> Origin:
    metadata = {
        "project": host["project"],
        "host": host_key,
        "snapshot": snapshot,
        "file": path,
    }
    return Origin(identifier, "code", weight, path, anchor, tuple(sorted(metadata.items())))


def _change(host_key: str, host: dict, weight: int) -> Origin:
    """Create a change record with both ID references and embedded endpoint data."""
    meta = {
        "project": host["project"],
        "host": host_key,
        "before_origin": "before-feature",
        "after_origin": "after-feature",
        "before_snapshot": host["before_tag"],
        "after_snapshot": host["after_tag"],
        "before_file": host["before_path"],
        "after_file": host["after_path"],
        "before_anchor": host["before_feature"],
        "after_anchor": host["after_feature"],
    }
    return Origin("history-change", "change", weight, metadata=tuple(sorted(meta.items())))


def _bridge(host_key: str, host: dict, weight: int) -> Origin:
    meta = {
        "project": host["project"],
        "host": host_key,
        "before_origin": "before-feature",
        "after_origin": "after-feature",
        "before_snapshot": host["before_tag"],
        "after_snapshot": host["after_tag"],
        "assumption": "the referenced routine denotes one evolving entity across the two tagged snapshots",
    }
    return Origin("entity-bridge", "bridge", weight, metadata=tuple(sorted(meta.items())))


def public_problem(host_key: str, variant: str, profile: str) -> Problem:
    host = HOSTS[host_key]
    profiles = {
        "unit": {"code": 1, "change": 1, "bridge": 1},
        "history-heavy": {"code": 1, "change": 3, "bridge": 2},
        "code-heavy": {"code": 3, "change": 1, "bridge": 1},
    }
    if profile not in profiles:
        raise ValueError(profile)
    w = profiles[profile]
    origins = [
        _code("before-feature", host["before_path"], host["before_feature"], w["code"],
              host_key=host_key, host=host, snapshot=host["before_tag"]),
        _code("after-feature", host["after_path"], host["after_feature"], w["code"],
              host_key=host_key, host=host, snapshot=host["after_tag"]),
        _code("before-context", host["before_path"], host["before_context"], w["code"],
              host_key=host_key, host=host, snapshot=host["before_tag"]),
        _code("after-context", host["after_path"], host["after_context"], w["code"],
              host_key=host_key, host=host, snapshot=host["after_tag"]),
        _code("shared-code", host["after_path"], host["shared_context"], w["code"],
              host_key=host_key, host=host, snapshot=host["after_tag"]),
        _change(host_key, host, w["change"]),
        _bridge(host_key, host, w["bridge"]),
    ]
    p = host["policy"]
    np = "not:" + p
    bridge_literal = f"bridge:{host_key}"
    bridge_fact = Fact("entity-bridge-fact", bridge_literal, ("entity-bridge",))
    facts: list[Fact] = []
    rules: list[Rule] = []

    def direct_graph() -> tuple[list[Fact], list[Rule]]:
        local_facts = [
            bridge_fact,
            Fact("before-signal", f"signal:{host_key}:before", ("before-feature", "history-change")),
            Fact("after-signal", f"signal:{host_key}:after", ("after-feature", "history-change")),
        ]
        local_rules = [
            Rule("before-to-negative-policy", (f"signal:{host_key}:before", bridge_literal), np),
            Rule("after-to-positive-policy", (f"signal:{host_key}:after", bridge_literal), p),
        ]
        return local_facts, local_rules

    if variant == "direct":
        facts, rules = direct_graph()
    elif variant == "chain":
        facts = [
            bridge_fact,
            Fact("before-signal", f"signal:{host_key}:before", ("before-feature", "history-change")),
            Fact("after-signal", f"signal:{host_key}:after", ("after-feature", "history-change")),
        ]
        rules = [
            Rule("before-stage-1", (f"signal:{host_key}:before",), f"legacy:{host_key}"),
            Rule("before-stage-2", (f"legacy:{host_key}",), f"interpreted-old:{host_key}"),
            Rule("before-to-negative-policy", (f"interpreted-old:{host_key}", bridge_literal), np),
            Rule("after-stage-1", (f"signal:{host_key}:after",), f"current:{host_key}"),
            Rule("after-stage-2", (f"current:{host_key}",), f"interpreted-new:{host_key}"),
            Rule("after-to-positive-policy", (f"interpreted-new:{host_key}", bridge_literal), p),
        ]
    elif variant == "choice":
        # Every path is gated by the same explicit bridge.  Private paths use
        # four version-local code anchors in their union; the shared path uses
        # two code anchors plus the change record.  The profiles therefore
        # exercise union-aware weighting without allowing a private bypass.
        facts = [
            bridge_fact,
            Fact("positive-private", f"private-positive:{host_key}", ("after-feature", "after-context")),
            Fact("negative-private", f"private-negative:{host_key}", ("before-feature", "before-context")),
            Fact("positive-shared", f"shared-positive:{host_key}",
                 ("shared-code", "after-context", "history-change")),
            Fact("negative-shared", f"shared-negative:{host_key}",
                 ("shared-code", "after-context", "history-change")),
        ]
        rules = [
            Rule("positive-private-to-policy", (f"private-positive:{host_key}", bridge_literal), p),
            Rule("negative-private-to-policy", (f"private-negative:{host_key}", bridge_literal), np),
            Rule("positive-shared-to-policy", (f"shared-positive:{host_key}", bridge_literal), p),
            Rule("negative-shared-to-policy", (f"shared-negative:{host_key}", bridge_literal), np),
        ]
    elif variant == "no-bridge-control":
        # A true bridge ablation: keep the two snapshot facts, both target
        # rules, all origins, and every non-bridge fact unchanged; remove only
        # the fact that makes the bridge assumption available to the rules.
        facts, rules = direct_graph()
        facts = [fact for fact in facts if fact.name != bridge_fact.name]
    elif variant == "single-side-control":
        facts, rules = direct_graph()
        rules = [rule for rule in rules if rule.head != np]
    else:
        raise ValueError(variant)

    return Problem(
        f"public-{host_key}-{variant}-{profile}", tuple(origins), tuple(facts), tuple(rules), p, np,
        metadata=tuple(sorted({
            "host": host_key, "project": host["project"], "variant": variant,
            "profile": profile, "seeded": "true", "defect_label": "none",
        }.items())),
    )


def run_public(out: Path) -> dict:
    records = []
    timing_records = []
    certificates = out / "joint-certificates"
    certificates.mkdir(exist_ok=True)
    positive_variants = ("direct", "chain", "choice")
    controls = ("no-bridge-control", "single-side-control")
    for host in sorted(HOSTS):
        for profile in ("unit", "history-heavy", "code-heavy"):
            for variant in (*positive_variants, *controls):
                problem = public_problem(host, variant, profile)
                start = time.perf_counter_ns()
                exact = solve_exact(problem)
                elapsed = time.perf_counter_ns() - start
                approx = independent_sides(problem)
                oracle = brute_force_optimum(problem)
                if (exact is None) != (oracle is None):
                    raise AssertionError("public exact/oracle existence mismatch")
                if exact is not None:
                    if support_cost(problem, oracle) != exact.cost:
                        raise AssertionError("public exact/oracle cost mismatch")
                    if approx is None or approx.cost > 2 * exact.cost:
                        raise AssertionError("2-approx bound violated")
                expected = variant not in controls
                if (exact is not None) != expected:
                    raise AssertionError("negative control or seeded contradiction failed")
                cert = {
                    "schema": "joint-contradiction-certificate-v1",
                    "problem": problem_to_dict(problem),
                    "solution": solution_to_dict(problem, exact, algorithm="exact-antichain"),
                    "oracle_selected": sorted(oracle) if oracle is not None else None,
                }
                cert_name = problem.name + ".json"
                dump_json(certificates / cert_name, cert)
                records.append({
                    "case": problem.name,
                    "host": host,
                    "project": HOSTS[host]["project"],
                    "variant": variant,
                    "profile": profile,
                    "control": variant in controls,
                    "certificate": exact is not None,
                    "exact_cost": exact.cost if exact else None,
                    "approx_cost": approx.cost if approx else None,
                    "approx_ratio": (approx.cost / exact.cost) if exact else None,
                    "selected_origins": len(exact.selected) if exact else 0,
                    "selected_code_origins": (
                        sum(problem.origin_map[identifier].kind == "code" for identifier in exact.selected)
                        if exact else 0
                    ),
                    "uses_history": bool(exact and "history-change" in exact.selected),
                    "uses_bridge": bool(exact and "entity-bridge" in exact.selected),
                    "frontier_entries": exact.total_frontier_entries if exact else 0,
                    "iterations": exact.iterations if exact else 0,
                    "certificate_file": "joint-certificates/" + cert_name,
                })
                timing_records.append({"case": problem.name, "elapsed_ns": elapsed})
    dump_jsonl(out / "joint-public-cases.jsonl", records)
    dump_jsonl(out / "joint-public-timings.jsonl", timing_records)
    positives = [r for r in records if r["certificate"]]
    summary = {
        "projects": len(HOSTS),
        "tagged_snapshots": 2 * len(HOSTS),
        "cases": len(records),
        "seeded_contradiction_cases": len(positives),
        "negative_controls": len(records) - len(positives),
        "negative_control_false_positives": sum(r["certificate"] for r in records if r["control"]),
        "exact_oracle_discrepancies": 0,
        "approximation_bound_violations": 0,
        "median_exact_cost": statistics.median(r["exact_cost"] for r in positives),
        "maximum_approximation_ratio": max(r["approx_ratio"] for r in positives),
        "scope": "seeded source/history belief graphs anchored to public tagged C excerpts; no real-defect-rate claim",
    }
    dump_json(out / "joint-public-summary.json", summary)
    return summary


def random_problem(rng: random.Random, index: int, origin_count: int) -> Problem:
    origins = tuple(Origin(f"o{i}", "seed", rng.randint(0, 4)) for i in range(origin_count))
    facts = []
    rules = []
    for side, target in (("p", "p"), ("n", "not:p")):
        support_count = rng.randint(1, 4)
        for j in range(support_count):
            size = rng.randint(1, min(5, origin_count))
            support = tuple(sorted(rng.sample([o.identifier for o in origins], size)))
            base = f"{side}{j}:base"
            mid = f"{side}{j}:mid"
            facts.append(Fact(f"fact-{side}-{j}", base, support))
            if rng.random() < 0.6:
                rules.append(Rule(f"rule-{side}-{j}-a", (base,), mid))
                rules.append(Rule(f"rule-{side}-{j}-b", (mid,), target))
            else:
                rules.append(Rule(f"rule-{side}-{j}", (base,), target))
    # Roughly one in seven is a negative control.
    if index % 7 == 0:
        rules = [r for r in rules if r.head != "not:p"]
    return Problem(f"oracle-{origin_count}-{index}", origins, tuple(facts), tuple(rules), "p", "not:p")


def run_oracle(out: Path, cases_per_size: int = 75) -> dict:
    rng = random.Random(20260918)
    records = []
    instances = []
    timing_records = []
    discrepancy = bound_failures = 0
    for n in range(4, 15):
        for index in range(cases_per_size):
            problem = random_problem(rng, index, n)
            start = time.perf_counter_ns()
            exact = solve_exact(problem)
            exact_ns = time.perf_counter_ns() - start
            oracle = brute_force_optimum(problem, limit=16)
            approx = independent_sides(problem)
            agrees = (exact is None) == (oracle is None)
            if agrees and exact is not None:
                agrees = exact.cost == support_cost(problem, oracle)
            if not agrees:
                discrepancy += 1
            if exact is not None and (approx is None or approx.cost > 2 * exact.cost):
                bound_failures += 1
            records.append({
                "origins": n,
                "index": index,
                "certificate": exact is not None,
                "exact_cost": exact.cost if exact else None,
                "oracle_cost": support_cost(problem, oracle) if oracle else None,
                "approx_cost": approx.cost if approx else None,
                "frontier_entries": exact.total_frontier_entries if exact else 0,
                "agrees": agrees,
            })
            instances.append({
                "origins": n,
                "index": index,
                "problem": problem_to_dict(problem),
                "oracle_selected": sorted(oracle) if oracle is not None else None,
            })
            timing_records.append({"origins": n, "index": index, "exact_ns": exact_ns})
    dump_jsonl(out / "joint-oracle-cases.jsonl", records)
    dump_jsonl(out / "joint-oracle-instances.jsonl", instances)
    dump_jsonl(out / "joint-oracle-timings.jsonl", timing_records)
    summary = {
        "seed": 20260918,
        "cases": len(records),
        "origin_range": [4, 14],
        "weighted": True,
        "exact_oracle_discrepancies": discrepancy,
        "approximation_bound_violations": bound_failures,
        "certificate_cases": sum(r["certificate"] for r in records),
        "maximum_frontier_entries": max(r["frontier_entries"] for r in records),
        "instance_recovery": "full serialized problems retained in joint-oracle-instances.jsonl; seed and generator are also recorded",
    }
    if discrepancy or bound_failures:
        raise AssertionError(summary)
    dump_json(out / "joint-oracle-summary.json", summary)
    return summary


def run_theory(out: Path) -> dict:
    rows = []
    for k in (2, 3, 4, 8, 16, 32, 64, 128):
        problem = make_tight_two_approx(k)
        exact = solve_exact(problem)
        approx = independent_sides(problem)
        assert exact is not None and approx is not None
        expected_opt = k + 1
        expected_approx = 2 * k
        if (exact.cost, approx.cost) != (expected_opt, expected_approx):
            raise AssertionError("tight family formula failure")
        rows.append({
            "family": "two-approx-tight", "parameter": k,
            "optimum": exact.cost, "baseline": approx.cost,
            "ratio": approx.cost / exact.cost,
            "inclusion_minimal": "",
        })
    for n in (2, 3, 4, 8, 16, 32, 64, 128):
        problem, order = make_deletion_gap(n)
        exact = solve_exact(problem)
        deleted = greedy_delete(problem, order)
        assert exact is not None and deleted is not None
        if exact.cost != 1 or support_cost(problem, deleted) != n or not is_inclusion_minimal(problem, deleted):
            raise AssertionError("deletion gap formula failure")
        rows.append({
            "family": "deletion-gap", "parameter": n,
            "optimum": exact.cost, "baseline": support_cost(problem, deleted),
            "ratio": support_cost(problem, deleted) / exact.cost,
            "inclusion_minimal": True,
        })
    with (out / "joint-theory.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "two_approx_cases": 8,
        "largest_two_approx_parameter": 128,
        "largest_observed_two_approx_ratio": max(r["ratio"] for r in rows if r["family"] == "two-approx-tight"),
        "deletion_gap_cases": 8,
        "largest_deletion_ratio": max(r["ratio"] for r in rows if r["family"] == "deletion-gap"),
        "all_formula_checks_passed": True,
    }
    dump_json(out / "joint-theory-summary.json", summary)
    return summary


def run_scaling(out: Path) -> dict:
    rows = []
    timing_rows = []
    # Antichain width is controlled by alternative supports; origin count alone
    # is not used as a proxy for difficulty.
    for alternatives in (2, 4, 8, 16, 32, 64, 128, 256):
        origins = []
        facts = []
        rules = []
        for side, target in (("p", "p"), ("n", "not:p")):
            for j in range(alternatives):
                a, b = f"{side}{j}a", f"{side}{j}b"
                origins.extend([Origin(a, "seed", 1), Origin(b, "seed", 1)])
                literal = f"{side}{j}:base"
                facts.append(Fact(f"fact-{side}-{j}", literal, (a, b)))
                rules.append(Rule(f"rule-{side}-{j}", (literal,), target))
        problem = Problem(f"scale-{alternatives}", tuple(origins), tuple(facts), tuple(rules), "p", "not:p")
        samples = []
        solution = None
        for _ in range(5):
            start = time.perf_counter_ns(); solution = solve_exact(problem); samples.append(time.perf_counter_ns() - start)
        assert solution is not None
        rows.append({
            "alternatives_per_side": alternatives,
            "origins": len(origins),
            "frontier_positive": solution.positive_frontier,
            "frontier_negative": solution.negative_frontier,
            "candidate_pairs": solution.positive_frontier * solution.negative_frontier,
            "minimum_cost": solution.cost,
        })
        timing_rows.append({"alternatives_per_side": alternatives, "median_ns": int(statistics.median(samples))})
    with (out / "joint-scaling.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (out / "joint-scaling-timings.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(timing_rows[0])); writer.writeheader(); writer.writerows(timing_rows)
    summary = {
        "rows": len(rows),
        "largest_alternatives_per_side": rows[-1]["alternatives_per_side"],
        "largest_candidate_pairs": rows[-1]["candidate_pairs"],
        "timing_note": "single-process Python perf_counter_ns; descriptive, not cross-machine performance",
    }
    dump_json(out / "joint-scaling-summary.json", summary)
    return summary


def write_table(out: Path, public: dict, oracle: dict, theory: dict, scaling: dict) -> None:
    text = r"""\begin{tabular}{lrr}
\toprule
Evidence block & Cases / scale & Result \\
\midrule
Public tagged-source configurations & %d & %d certificates, %d controls \\
Weighted small-instance oracle & %d & 0 discrepancies \\
Tight independent-side family & $k\leq %d$ & max ratio %.3f \\
Adverse deletion family & $n\leq 128$ & max ratio %.0f \\
Frontier scaling & %d pairs & descriptive timing only \\
\bottomrule
\end{tabular}
""" % (
        public["cases"], public["seeded_contradiction_cases"], public["negative_controls"],
        oracle["cases"], theory["largest_two_approx_parameter"], theory["largest_observed_two_approx_ratio"],
        theory["largest_deletion_ratio"], scaling["largest_candidate_pairs"],
    )
    (out / "joint-results-table.tex").write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--part", choices=("all", "public", "oracle", "theory", "scaling"), default="all")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    summaries = {}
    if args.part in {"all", "public"}: summaries["public"] = run_public(args.out)
    if args.part in {"all", "oracle"}: summaries["oracle"] = run_oracle(args.out)
    if args.part in {"all", "theory"}: summaries["theory"] = run_theory(args.out)
    if args.part in {"all", "scaling"}: summaries["scaling"] = run_scaling(args.out)
    if args.part == "all":
        summaries["status"] = "joint-campaign-passed"
        dump_json(args.out / "joint-summary.json", summaries)
    print(json.dumps(summaries, sort_keys=True))


if __name__ == "__main__":
    main()
