# Model and certificate contract

## 1. Semantic objects

An **origin** is a selectable evidence record with an identifier, kind, nonnegative integer weight, and optional source anchor. Supported kinds are:

* `code`: a relative path and exact retained text anchor in one declared snapshot;
* `change`: a record naming two distinct snapshot endpoints and their anchors;
* `bridge`: an explicit assumption relating snapshot-local entities;
* `seed` or `context`: controlled finite-experiment evidence without a source path.

A **fact** is a named ground literal plus a tuple of origin identifiers. It is enabled exactly when all of those origins are selected. A **rule** is a named fixed positive-Horn implication from distinct ground body literals to a ground head literal. Rules do not carry selectable cost. The target pair must be `p` and `not:p` for some literal spelling; `not:` is syntactic strong negation.

For a selection `S`, forward closure starts with every fact whose support is contained in `S` and repeatedly applies every rule whose body is present. The predicate is upward closed because the facts and rules are fixed.

## 2. Optimization objective

A proof support is the union of the origin supports at its base-fact leaves. A certificate consists of one proof of the positive target and one proof of the negative target. Its selected set is the union of their supports, and its cost is the sum of each selected origin's weight once.

The objective is not the sum of two independently optimized proof costs. Shared code, change, or bridge evidence is paid once. Deterministic ties are broken by total cost, selected cardinality, lexicographic selected identifiers, and proof-step identifiers; the tie break affects only which optimum is serialized.

## 3. Exact algorithm

For every literal, the producer stores an antichain of supports: no retained support strictly contains another retained support for the same literal. Base fact supports are inserted first. Every rule then combines one retained support from each body frontier, unions them, and inserts the result into the head frontier. A smaller support deletes strict supersets. Iteration stops when no frontier changes.

The proof notes establish:

1. finite termination;
2. derivational soundness of every retained backpointer tree;
3. completeness for every inclusion-minimal proof support; and
4. global optimality after evaluating every positive-frontier/negative-frontier pair.

The worst-case frontier is exponential. The implementation exposes a defensive frontier-entry cap; exceeding it is an error, not a claim that no certificate exists.

## 4. Independent and deletion baselines

`independent_sides` chooses a minimum-cost support for each target separately and returns their union. Nonnegative costs imply a factor-2 bound relative to the joint optimum. The retained family approaches two.

`greedy_delete` begins with all origins and tries each origin once in a declared order, retaining a deletion when the fixed contradiction predicate remains true. Upward closure implies the final set is inclusion-minimal. It need not be globally minimum and has an unbounded cost ratio.

The older re-mined threshold predicate is not the predicate above. Removing an observation changes its denominator and therefore the rule being tested. Its local-minimality behavior and closed-form collapse are kept in separate files.

## 5. JSON certificate

A positive certificate document contains:

```text
schema
problem:
  name, positive, negative, metadata
  origins[]: id, kind, weight, path, anchor, metadata
  facts[]: name, literal, origins[]
  rules[]: name, body[], head
solution:
  algorithm, status="certificate"
  selected[], cost
  positive_proof, negative_proof
  metrics
```

A proof node contains `literal`, `support`, `step`, and `premises`. A fact node's step must name a declared fact with the same literal and support. A rule node's step must name a declared rule with the same head; its ordered premise literals must equal the rule body; and its support must equal the union of premise supports.

A negative-control document uses `status="no-contradiction-certificate"`. It does not invent a proof of absence. The bounded consumer recomputes exhaustive optimality for those public cases.

## 6. Source-level replay obligations

The independent consumer rejects a document unless all of the following hold:

1. every origin/fact/rule identifier is unique and all references resolve;
2. every path normalizes inside the repository root;
3. every declared code anchor occurs exactly once in its retained file;
4. every change record names two existing, distinct snapshot endpoints;
5. every bridge is explicit rather than inferred from equal names;
6. each proof tree is locally valid and derives the declared target;
7. the top-level selected set equals the union of the two root supports;
8. the reported cost equals the recomputed unique-origin sum;
9. fixed closure of the selected set contains both targets;
10. a bounded exhaustive oracle agrees on existence and minimum cost;
11. declared negative controls remain non-contradictory.

The replay code does not deserialize executable objects, follow absolute paths, fetch network data, or import the producer module.

## 7. Trust boundary

The certificate proves only the declared finite claim. The frontend or analyst remains responsible for the truth of source-to-fact mappings, rule semantics, bridge meaning, and origin weights. A perfectly replayed certificate can still be unhelpful if those declarations are poor. Conversely, no consumer needs to trust the producer's search once the problem, sources, and proof-carrying certificate are available.
