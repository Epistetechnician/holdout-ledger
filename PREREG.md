# Pre-registration: pricing evidence in bits for sealed-holdout self-improvement

Frozen before any confirmatory seed was run. The commit that contains this file also contains
`hl/` (the simulator, certificates and analysis). Confirmatory seeds are 1000-1199.

## Question

A self-improvement loop asks a sealed holdout "did that change help?" many times. Every answer leaks
information about the holdout into the next proposal, so the holdout's reported gain drifts upward
while the true gain does not. Can the loop keep an auditable *ledger of the bits the holdout released*
and the *description length of what it shipped*, bill the evidence by the cheaper of the two, and so
(a) issue gain certificates that are never wrong, (b) tell honest progress from holdout-fitting without
inspecting intent, and (c) admit moves online only when their gain beats the radius of their own description?

## Prior art, and what is and is not new

Not new: the adaptive-overfitting problem and union-bound/compression remedies (Dwork et al. 2015,
*The reusable holdout*; Blum & Hardt 2015, *The Ladder*), rounds-of-adaptivity bounds for "natural"
analysts (Zrnic & Hardt 2019), and the empirical finding that research agents given one bit of feedback
lose little (Bertran & Roth 2026, arXiv 2606.11045, which offers a description-length explanation but no
certificate). The concentration inequalities used here are Hoeffding and empirical Bernstein
(Maurer & Pontil 2009).

Claimed as new, and tested below: (i) a ledger-backed certificate that charges the *minimum* of the
information route (verdict bits) and the description route (output length), with a "core" fallback that
certifies the compressible part of a system after the incompressible part is stripped; (ii) a measured
separation of honest and holdout-fitting progress by billed bits; (iii) a complexity-priced online
admission gate; (iv) a measurement of how far natural proposers sit below the worst-case radius.

## Design

* Data: UCI Covertype, classes 1 vs 2 (495,141 rows), shuffled with seed 20261104. Train 60,000 (all
  pool models are fitted here only), dev 20,000 (chooses the late-regime warm start only), holdout pool
  265,000 (a run draws n of these without replacement), reserve 150,000 (auditor only).
* Pool: 800 real models (trees, extra-trees, forests, logistic regression, naive Bayes, gradient
  boosting) on random feature subsets and subsamples of the train split. Pool manifest hash in `data/`.
* System: a k-member majority-vote ensemble. Ties fall back to a fixed depth-8 tree. Reference system E0:
  *early* = 5 arbitrary pool members (large headroom); *late* = 15 members forward-selected on dev
  (near saturation). Gain is always measured against E0.
* Moves: `pool` = swap one member for a pool member (natural). `patch` = flip, with density rho = 0.005,
  the predictions in the low-margin region (|vote| <= 1) chosen by a hash of (seed, example id): a stylised
  "special-case the borderline cases" hack with no expected true gain. `mixed` = each move is a pool swap or
  a patch with probability 1/2.
* Gates: `seq` = one bit per query, admit if the holdout gain is strictly positive. `seqm` = one bit,
  admit if gain exceeds 1/sqrt(n). `mdl` = one bit, admit if gain exceeds the empirical-Bernstein radius for
  the move's own description (log2(k)+log2(800) bits for a swap, 32 for a patch). `batch` = 64 candidates per
  round, the gate returns only (improved?, index of best), log2(65) bits per round.
* Grid: regime {early, late} x n {5,000; 20,000; 100,000} x proposer {pool, patch, mixed} x gate
  {seq, seqm, mdl, batch} x K {64; 256; 1,024; 4,096} candidate evaluations, plus a rho sensitivity
  (0.002, 0.02) at n = 20,000, K = 1,024, seq. 200 seeds per cell.
* Certificates (all one-sided, delta = 0.05, paired difference of per-example correctness vs E0):
  `L_wald` = gain - 1.645 SE (what is normally reported); `L_naive` = Hoeffding/empirical-Bernstein
  radius with zero bits; `L_info` = radius at the ledger's verdict bits; `L_desc` = radius at the output's
  description length; `L_ledger` = best of {final system, core system (patches stripped)} each charged
  min(info bits, description bits), with the union over 4 events charged in the radius.
* Violation: certificate > true gain (reserve) of the system the certificate is about. Reserve noise
  (paired difference, 150k examples) is about 0.001.

## Hypotheses and pass criteria

| id | claim | pass if |
|---|---|---|
| H1 | The usual certificate fails under adaptivity | patch, seq, n=20k, K=1024, each regime: `L_wald` violation >= 0.90 and mean (admitted - true) >= 0.01 |
| H2 | The ledger certificate is valid | across all runs violation rate has one-sided 95% Clopper-Pearson upper bound <= 0.05, and no cell exceeds 0.05 |
| H3 | Zero-bit certificates are invalid under attack | `L_naive` violation >= 0.50 for (early, patch), (late, patch), (late, mixed) at every n, seq, K=1024 |
| H4 | Honest and fitting progress separate | early, seq, K=1024, n=20k: `L_ledger` > 0 in >= 95% of pool runs and <= 5% of patch runs; median `L_ledger`/true gain on pool >= 0.30 |
| H5 | Complexity pricing blocks fitting at little cost | early, n=20k, K=1024: mdl overstatement <= 0.2 x seq overstatement for mixed and patch; on pool mdl keeps >= 0.90 of seq true gain and raises mean `L_ledger` by >= 0.02 |
| H6 | Honest limit | late, pool, seq, K=1024: `L_ledger` > 0 in <= 10% of runs at n = 5k and 20k (marginal gains are not certifiable at these n). n = 100k is reported, not tested |
| H7 | Batching keeps progress | early, pool, K=1024: batch keeps >= 0.80 of seq true gain |
| H8 | The worst-case radius is not vacuous | early, patch, seq, n=20k, K=1024: median (admitted - true)/radius >= 0.10 |
| H9 | Natural proposers use little of the budget | pool, seq, n=20k, K=1024: median (admitted - true)/radius <= 0.10 in both regimes |

Everything else (trajectories, rho sensitivity, route attribution, other cells) is exploratory.

## Disclosure

A pilot (seeds 0-5, files under `results/pilot/`, git-ignored) was used to debug the simulator and to
choose the regimes, rho, the `mdl` gate and the thresholds above. Two design flaws were found and fixed
in the pilot: adding one member to an odd-size vote never changes a prediction (so the natural move
became a swap), and a violation must be scored against the system the certificate is about. Confirmatory
seeds are disjoint from pilot seeds. All thresholds were fixed after seeing pilot means and are
therefore easy-to-moderate; H1-H3 are largely mathematical sanity checks of the implementation, and H4,
H5, H8 and H9 are the empirical content.

## Limits that no result here can remove

One dataset; tabular models, not an LLM agent; a stylised attacker, not an adaptive adversary built against
the `mdl` gate (the union bound, not the gate, is what protects the certificate); proposers see verdicts but not labels;
the reserve is the same distribution as the holdout. Level 1 evidence in the repo's own ladder: local,
synthetic-attacker, real models.
