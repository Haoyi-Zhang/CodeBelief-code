# Selection semantics: definitions and complete arguments

These are ordinary written mathematical proofs, not proof-assistant-checked theorems. The finite sweep is a separate implementation check. The results are elementary properties of the stipulated model; originality over the broader literature is not claimed.

## Definitions

Let U be a finite indexed population. Each i in U has two support bits p_i,n_i in {0,1}, with p_i+n_i >= 1. The three types are positive only, negative only, and shared. Write p(S)=sum_{i in S}p_i, n(S)=sum_{i in S}n_i. A rational threshold t=a/b satisfies 0<a<=b. A source selection is a subset S of U.

P(S), re-mined replay, holds iff |S|>0, b p(S)>=a|S|, and b n(S)>=a|S|. Q_U(S), pinned replay, holds iff |U|>0, b p(S)>=a|U|, and b n(S)>=a|U|. Empty selections fail both predicates because a>0. Each active support is stipulated to activate one of the opposing propositional units x and not-x. This stipulation does not establish an actual code error.

A set is 1-minimal for a predicate if it is valid and no one-item deletion is valid. It is inclusion-minimal if no proper subset is valid. A minimum-cardinality witness minimizes size over all valid subsets of the fixed U. Minimum cardinality implies inclusion minimality, which implies 1-minimality. The converses need additional assumptions and are not generally true.

## S1. Small nonmonotone counterexample

Take U=(positive only, negative only, shared) and t=2/3. The full set has two supports of each kind and is valid. Deleting the positive-only item leaves positive support one out of two; deleting the negative-only item is symmetric. Deleting the shared item leaves both supports one out of two. Thus every immediate deletion is invalid. The shared singleton supports both commitments with ratio one, so it is valid. The full set is 1-minimal but not inclusion-minimal and not minimum-cardinality.

This also shows failure of upward closure: the shared singleton is valid but adjoining either exclusive item makes it invalid. Conversely, U=(positive only, positive only, shared) is invalid at 2/3 while containing the valid shared singleton. Rejecting an invalid starting population does not answer whether it has a valid re-mined subpopulation.

## S2. Arbitrarily large local gap

Fix integers a,b with b/2<a<b, and k>=1. Take (b-a)k positive-only items, (b-a)k negative-only items, and (2a-b)k shared items. There are bk items in total and ak supports of each kind. Therefore the full set is valid exactly at threshold a/b.

Every deleted item supports at least one of the two sides. After deleting that item, one side has ak-1 supporters in a population of bk-1. This is below threshold because b(ak-1)<a(bk-1) is equivalent to b>a. Every immediate deletion is therefore invalid. Since (2a-b)k>=1, a shared singleton is valid. Empty sets are invalid, so its size one is optimal. The ratio of this 1-minimal set's size to the minimum is bk, unbounded as k increases. No computational enumeration is needed for the argument.

The accompanying family test uses only twenty finite choices of a,b,k, immediate deletions, and a shared singleton. It does not enumerate every subset of populations as large as eighty.

## S3. The re-mined minimum collapses

If a shared item exists, its singleton is valid for every permitted threshold. Empty sets are invalid, so the minimum is one.

Assume no shared item exists. If a valid S exists, p(S)+n(S)=|S|. The two threshold inequalities imply |S|>=2t|S|. Since |S|>0, t<=1/2. Positivity of t also forces at least one item of each exclusive type. Conversely, if both exclusive types exist and t<=1/2, selecting one of each gives both support ratios 1/2. No exclusive singleton is valid, so the minimum is two.

Thus the complete optimum classification is: one with shared support; two without shared support when both exclusive types exist and t<=1/2; no witness otherwise. A scan of the population suffices. In particular, above one half, every full-valid population in this fragment contains a shared singleton. S2 does not establish a difficult minimum-witness optimization problem. It exposes a poor deletion strategy on an easy model.

## S4. Pinned replay is upward closed but a different question

If S subset T subset U and Q_U(S) holds, support counts cannot decrease from S to T while the denominator remains |U|. Both inequalities remain true, proving upward closure. Also Q_U(S) implies P(S) because S is nonempty and |S|<=|U|. The converse fails: the shared singleton in S1 passes P but contributes only 1/3 of each support under Q_U. Pinning changes the predicate; it cannot be called a semantics-preserving correction to re-mining.

For any upward-closed predicate, a 1-minimal valid set S is inclusion-minimal. Otherwise take a valid proper subset T of S and choose x in S minus T. Upward closure from T to S minus {x} makes that immediate deletion valid, contradicting 1-minimality.

A single deletion pass produces a 1-minimal set for an upward-closed predicate: when deletion of x fails, every later attempted deletion of x would be a subset of that failed candidate, so it cannot become valid. Therefore such a pass gives inclusion minimality for Q_U. For arbitrary predicates, repeated passes ending in an unchanged pass give 1-minimality, but S1 refutes the stronger guarantee.

## S5. Pinned cardinality optimum

Assume Q_U(U) holds. Let N=|U|, K=ceil(aN/b), and c be the number of shared items. Then the minimum cardinality is 2K-min(c,K).

Proof of lower bound: if a selection uses z shared, u positive-only, and v negative-only items, validity requires z+u>=K and z+v>=K. If z<=K, size z+u+v>=2K-z>=2K-min(c,K). If z>K, size>=z>K and the desired bound is K since c>=z>K. Thus the bound also holds in that case.

Proof of attainment: if c>=K, select K shared items. If c<K, select all c shared items and K-c items of each exclusive type. There are enough exclusive items because full validity implies c plus the availability of each exclusive type is at least K. The resulting size attains 2K-min(c,K).

Inclusion minimality still does not imply minimum cardinality. At t=1/3, U consisting of two shared, two positive-only, and two negative-only items has K=2. Deleting shared items first can leave four exclusive items; each is then indispensable for its side. The optimum is the two shared items. This is not a new general unsatisfiable-core algorithm.

## S6. A single pass can fail even 1-minimality

For U=(shared,shared,positive only) and t=2/3, first attempt deletion of each shared item in order. Each candidate is one shared plus one positive-only item, invalid on the negative side. Then delete the positive-only item; the two-shared remainder is valid. The pass ends there, although either remaining shared item can now be deleted. Repetition repairs this local failure but not S1's inclusion-minimality failure.

## Encoding boundary

Boolean selectors z_i encode the exact re-mined predicate with sum z_i>=1, b sum p_i z_i>=a sum z_i, and b sum n_i z_i>=a sum z_i. Cardinality is sum z_i; fixed supplied weights give sum w_i z_i. Pinning replaces the denominator sum z_i by |U|. These are ordinary selector/aggregate constraints, not a new optimization formalism. The experiments use enumeration and the closed forms, not an external integer solver. General weighted or multi-rule source minimization is not implemented.
