# Joint minimal contradiction certificates for evolving code beliefs

This repository is the standalone artifact for *Joint Minimal Contradiction Certificates for Evolving Code Beliefs*. It implements and checks a bounded problem: select a minimum-weight union of code, change, and explicit bridge origins that supports positive-Horn derivations of a literal and its syntactic strong negation.

The repository is complete for that declared finite model. It is not a production C analyzer, defect benchmark, theorem prover, or independently replicated study.

## Reproduce from a clean extraction

Requirements: Linux or another Unix-like system with Python 3.10+ and the standard-library `resource` module. No package installation, network, C compiler, SAT/SMT solver, GPU, model API, credentials, sibling paper directory, or hidden cache is used.

```sh
python3 reproduce.py --out ../contradiction-reproduction
```

The output directory must be empty. The runner uses one worker and one available CPU core. Each child receives a 512 MiB address-space limit, a 30/31-second CPU limit, and a 32-second wall limit. It executes:

1. 62 unit-test methods;
2. the original selection-semantics pilot and seven exact population chunks;
3. 6,452 ordinary-Horn Boolean-oracle checks;
4. the re-mined/pinned formula families and independent replay;
5. 45 public-source certificate configurations;
6. 825 weighted small-instance exact/oracle comparisons;
7. the conditional factor-two and adverse deletion families;
8. controlled frontier scaling;
9. the producer-independent source/certificate consumer; and
10. deterministic report generation.

On a full successful run, every file named by `results/expected-files.json` is regenerated and compared byte for byte with the retained evidence. There are 85 deterministic files. Measurements and logs are not expected to be byte-identical.

Interrupted runs can resume only from a valid retained measurement file. A recorded zero exit code is not enough: before skipping a task, the runner revalidates every declared output byte-for-byte against retained evidence and also validates declared dependencies:

```sh
python3 reproduce.py --out ../contradiction-reproduction --resume
```

Focused checks:

```sh
python3 replay_joint.py --results results --report ../joint-replay.json
python3 verify.py --results results --report ../legacy-replay.json
python3 report.py --results results --out ../derived-tables
python3 -m unittest discover -s tests -v
```

The focused commands are useful for inspection; the full runner is the authoritative resource-bounded reproduction path.

## Model and algorithms

`src/joint.py` defines origins, base facts, fixed positive-Horn rules, exact antichain propagation, independent-side selection, exhaustive bit-mask optimization, deletion, proof trees, and certificate serialization. Strong negation is encoded as literal names beginning with `not:` and is not negation-as-failure.

The producer maintains every inclusion-minimal proof support. It then examines the Cartesian product of the two opposed target frontiers and chooses a minimum-cost union with deterministic tie breaking. The brute-force oracle uses a different representation: origin selections and derived literal sets are integer masks. It visits every subset within the declared 20-origin guard and computes fixed Horn closure independently of the antichain implementation.

`src/joint_benchmark.py` constructs the public-host, oracle, formula-family, and scaling campaigns. `src/joint_replay.py` and the top-level `replay_joint.py` are a separately implemented consumer path. The consumer requires canonical relative POSIX paths; binds every anchor to its declared project, snapshot, and file; checks distinct change endpoints and identifier/embedded-record agreement; validates bridge scope; replays proof trees, closure, union, and cost; and checks canonical, known, feasible, optimum `oracle_selected` witnesses for bounded positive cases. The entry point records at runtime whether `src.joint` is present in `sys.modules`; the retained run reports false.

The older `src/model.py`, `src/experiment.py`, `src/replay.py`, and `verify.py` preserve the moving-threshold selection-semantics boundary and ordinary-Horn finite checks. They remain scientifically relevant because they demonstrate that deleting observations while re-inferring a rule changes the predicate.

## Retained evidence

| Evidence block | Retained result |
|---|---|
| Weighted oracle | 825 cases over 4--14 origins; 704 certificates; 0 exact/oracle discrepancies; 0 approximation-bound violations |
| Tagged public hosts | 45 configurations; 27 seeded positives; 18 negative controls; 0 control false positives; 6 tagged snapshots from 3 projects |
| Conditional factor-two family | after exact one-side minima are available, parameter through 128; largest ratio 256/129 = 1.984496... |
| Adverse deletion family | parameter through 128; ratio 128; every output inclusion-minimal |
| Scaling family | 256 alternatives per side; 1,024 origins; 65,536 candidate support pairs |
| Moving-predicate census | 32,790 configurations and 3,359,220 subset judgments |
| Ordinary-Horn census | 6,452 formulas; 0 Boolean-oracle discrepancies |
| Tests | 62 methods, including true bridge ablation, Cartesian-product frontier comparison, path/snapshot/endpoint/identifier checks, oracle-witness checks, and resume corruption recovery |

`results/joint-oracle-instances.jsonl` retains each generated weighted problem (origins, weights, facts, rules, and target) in addition to `joint-oracle-cases.jsonl` metrics. `joint-public-cases.jsonl`, `joint-theory.csv`, and `joint-scaling.csv` contain the other case-level data. `joint-certificates/` contains all 45 public case documents. `results/joint-replay.json` records that the producer module was not imported and that external independent review is false.

## Public source inputs and licenses

`inputs/public/manifest.json` identifies exact excerpts from:

* cJSON v1.7.17 and v1.7.18 (MIT);
* inih r58 and r59 (BSD-3-Clause); and
* mjson 1.2.6 and 1.2.7 (MIT).

The matching license notices are retained under `inputs/public/licenses/`. The excerpts are immutable text hosts for source-anchor and change-endpoint replay. Their syntactic changes are real; the belief rules, opposing targets, and alternative proof structures around them are controlled seeds. No maintainer label or causal defect claim is inferred.

## Proofs and evidence ledgers

`proofs/joint.md` gives complete ordinary mathematical arguments for termination, soundness, the fixed-point subset-representative lemma, completeness, exact joint optimization, NP-completeness, the conditional tight factor-two cost bound after exact one-side minima are available, and the unbounded deletion gap. `proofs/selection.md` preserves the re-mined/pinned boundary. `proofs/horn.md` and `proofs/scope.md` state the auxiliary finite-Horn and interpretation boundaries.

`claim_evidence_ledger.csv` maps every material manuscript claim to its proof, checker, raw result, figure/table, maturity, and boundary. `external_resources.csv` records public inputs, licenses, scholarly sources used for scope, and official-rule access holds.

## Interpretation limits

A successful reproduction establishes that the packaged deterministic computations regenerate and agree with their declared finite oracles. It does not establish complete C semantics, real defects, warning precision/recall, developer usefulness, semantic identity across versions, calibrated uncertainty, proof-assistant verification, or independent human replication. Source anchors establish retained textual identity; bridges remain explicit assumptions. Timing files are descriptive and are not a cross-machine performance claim.

The executable experiments use deterministic conventional Python and make no external model calls.

Original artifact code and original fixtures are released under `LICENSE`. Publisher template files are not part of this standalone repository. Upstream excerpts retain their included license notices.
