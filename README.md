# Joint minimal contradiction certificates for evolving code beliefs

This standalone artifact implements a finite optimization problem: select a
minimum-weight union of code, change, and explicit bridge origins supporting
positive-Horn derivations of a literal and its syntactic strong negation.
It includes exact antichain propagation, an exhaustive subset oracle,
independent-side selection, deletion baselines, and a separately implemented
certificate consumer.

## Setup and reproduction

The bounded runner requires Python 3.10+ on a Unix-like system with the
standard-library `resource` module. Scientific checks require no packages,
network, compiler, solver, GPU, credentials, or sibling paper directory.
Run commands from this repository root:

```sh
python3 reproduce.py --out ../contradiction-reproduction
```

Use an empty output directory. The runner executes one child at a time with
one available CPU core where affinity is supported, a 512 MiB address-space
limit, a 30/31-second CPU limit, and a 32-second wall timeout per child.
It runs the tests, selection-semantics pilot and seven population chunks,
ordinary-Horn checks, joint-certificate campaigns, independent consumers, and
report generation. All 85 deterministic files in `results/expected-files.json`
must be regenerated and match the retained evidence byte for byte.
Timing and logs are machine-dependent.

Resume an interrupted run with:

```sh
python3 reproduce.py --out ../contradiction-reproduction --resume
```

Resume requires retained measurements. A task is skipped only after checking
its source/input SHA-256 binding, all declared outputs, and dependencies;
historical records without that binding force recomputation.

Focused checks also work without Unix resource limits, including on Windows
(use `python` instead of `python3` where appropriate):

```sh
python3 -B -m unittest discover -s tests -v
python3 -B tests/regression_weight_lookup.py -v
python3 replay_joint.py --results results --report ../joint-replay.json
python3 verify.py --results results --report ../legacy-replay.json
python3 report.py --results results --out ../derived-tables
```

These focused commands do not apply the bounded runner's resource limits.
The scientific GitHub Actions workflow runs both the separate weight-lookup
regression and the complete bounded reproduction on Ubuntu 24.04.

## Inputs, results, and implementation

`inputs/index.json` identifies original finite source-text fixtures.
`inputs/public/manifest.json` identifies six tagged excerpts from cJSON
v1.7.17/v1.7.18, inih r58/r59, and mjson 1.2.6/1.2.7.
They are read as text, never compiled or executed. Their changes are real;
the surrounding belief rules and proof alternatives are controlled seeds,
not maintainer defect labels. Upstream notices are in `inputs/public/licenses/`.

`src/joint.py` implements the joint model and algorithms;
`src/joint_benchmark.py` defines the finite campaigns.
`src/joint_replay.py` and `replay_joint.py` validate source anchors, change
endpoints, explicit bridges, proof trees, union costs, and bounded oracle
witnesses without importing the producer.
The older model, experiment, replay, and `verify.py` paths remain relevant
to the re-mined versus pinned selection-semantics boundary.

Retained `results/` include 825 weighted oracle instances, 45 public-host
configurations (27 seeded positives and 18 negative controls), the conditional
factor-two and adverse-deletion families, frontier scaling, 32,790 selection
configurations, and 6,452 ordinary-Horn formulas.
Raw CSV/JSONL, all public certificates, measurements, and historical run logs
are retained. `report.py` derives tables and macros from those results.

Model details and the fixed campaign protocol are in `docs/`.
`proofs/` contains the mathematical arguments.
`claim_evidence_ledger.csv` maps claims to proofs and evidence;
`external_resources.csv` records resource provenance and access conditions.
Historical logs describe their original runs, not the current test census.

## Optional vector figures

```sh
python -m pip install -r requirements-figures.txt
python -B scripts/plot_figures.py
```

The renderer reads retained `joint-theory.csv` and `joint-scaling.csv`;
it does not rerun experiments. It writes vector PDFs to `figures/` and,
if present, copies them to the sibling paper's `figures/` directory.
Use `--out` and `--paper-dir` to select destinations.
Packaged Linux Libertine regular/italic fonts preserve the supplied ACM
figure typography; their source and SIL Open Font License are in `fonts/`.

## Conditions and licenses

Results concern the declared finite model, not complete C semantics, real
defect detection, developer usefulness, proof-assistant verification, or
independent human replication. Bridges are explicit assumptions; timings
are descriptive rather than cross-machine performance claims. Scientific
programs use deterministic conventional Python and make no external model calls.

Original code and fixtures use the MIT `LICENSE`; upstream excerpts retain
their own included notices. Publisher templates are not part of this repository.
