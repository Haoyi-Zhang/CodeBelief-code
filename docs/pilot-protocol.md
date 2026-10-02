# Pilot and campaign protocol

## Pre-lock pilot

The initial candidate minimized a contradiction while recomputing support thresholds after each observation deletion. Before scaling, the pilot used an exact three-observation case, a negative control, exhaustive subset search, and an independently coded replay predicate. The pilot found:

1. a full set that was one-deletion minimal although a valid singleton existed;
2. a parameterized unbounded local/global gap; and
3. a global closed form showing that the entire two-support optimization fragment reduces to a shared singleton, an opposite pair at threshold at most one half, or no witness.

Item 3 falsified the intended substantial optimization contribution. The project pivoted before scientific lock rather than treating more permutations as practical breadth.

## Locked main campaign

### Hypotheses

* H1: antichain propagation and exhaustive bit-mask optimization agree on every generated bounded instance.
* H2: independent minimum proofs never exceed twice the exact joint-union cost.
* H3: removing an explicit bridge or one complete target side yields no certificate.
* H4: declared weight profiles can change the selected union while preserving exactness.
* H5: constructive families realize the proved conditional tight factor-two limit and unbounded deletion gap.
* H6: a separately implemented consumer accepts every valid retained certificate and rejects specified mutations.

### Fixed inputs and parameters

* random seed: 20260918;
* origin counts: every integer 4--14;
* cases per origin count: 75;
* origin weights: uniformly generated integers 0--4 by the fixed generator;
* public projects/tags: cJSON v1.7.17/v1.7.18, inih r58/r59, mjson 1.2.6/1.2.7;
* public variants: direct, chain, choice, no-bridge control, single-side control;
* public profiles: unit, history-heavy, code-heavy;
* theorem-family parameters: 2, 3, 4, 8, 16, 32, 64, 128;
* scaling alternatives per side: 2, 4, 8, 16, 32, 64, 128, 256.

No parameter was tuned against a held-out test set. The campaigns are deterministic finite checks, not statistical sampling.

### Baselines

* exact antichain joint solver;
* exhaustive bit-mask origin-subset oracle;
* independently minimized target proofs;
* fixed-order one-pass deletion under the upward-closed predicate;
* no-bridge and single-side controls;
* inherited re-mined and pinned predicates.

No external reducer or solver is executed, so no runtime superiority over ddmin, C-Reduce, Perses, GReduce, MaxSAT, MUS, OCUS, or FoX is claimed.

### Failure criteria

The campaign fails on any exact/oracle existence or cost discrepancy, any conditional factor-two cost-bound violation, any positive/control status mismatch, any invalid anchor/path/change/bridge/proof/union/cost, any mutation accepted by the consumer, any deterministic-output mismatch, any test failure, or any resource-limit exit.

## Retained outcome

All 825 weighted oracle instances agree, all 704 positive cases respect the conditional factor-two cost bound, all 27 public positive configurations replay, all 18 controls remain negative, and all formula-family checks pass. Controlled scaling reaches 65,536 final support pairs. The outcome validates the locked finite claims only.
