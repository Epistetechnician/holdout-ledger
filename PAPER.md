# Pricing evidence in bits: a ledger certificate for sealed-holdout self-improvement

Draft for outside readers, 2026-11-14. AI-assisted draft from `PREREG.md`, `results/RESULTS.md` and a recomputation from `results/confirmatory.jsonl`; the author should rewrite the prose before circulating. Every number below was recomputed from the raw runs and matches the committed results. References are as cited in `PREREG.md` and have not been re-checked against the sources.

## Summary

A self-improvement loop that keeps a change only when a sealed holdout says it helped is running an adaptive analysis on that holdout. The reported gain drifts above the true gain, and the usual confidence interval does not notice. We keep a hash-chained ledger of two quantities: the bits the holdout released to the proposer, and the description length of the system that shipped. A gain is certified with a union bound charged at the smaller of the two. In a pre-registered simulation (59,200 runs, 800 real models on Covertype) the certificate was never wrong, it certified honest progress and refused holdout-fitted progress, and the standard interval was wrong in every run under the fitting attack. The certificate is conservative, it certifies under half of the true gain in the main cell, and it certifies nothing when the true gain is small or the holdout is small.

## 1. Problem

Let a loop propose K candidate changes. For each, a gate looks at the holdout and returns a verdict. Admitted changes accumulate. At the end the loop reports the holdout gain of the final system over the starting system, with a one-sided 95% interval that treats the holdout as fresh.

That interval is invalid: the final system was selected using the holdout. This is the adaptive-overfitting problem of Dwork et al. (2015) and Blum and Hardt (2015). What a practitioner running an agent loop needs is narrower than the general theory: a number they can attach to a reported gain, that an auditor can recheck from a log, and that tells them when the loop has been fitting the holdout.

## 2. The certificate

Two union bounds are valid for the final system, whatever the proposer did.

- **Information route.** If the gate released B bits in total, the proposer's output is a function of a transcript of at most B bits, so it is one of at most 2^B systems fixed before the holdout was read.
- **Description route.** If the final system can be written in ℓ bits in a prefix-free code fixed in advance, it is one of at most 2^ℓ programs, however many queries were made.

For a paired per-example gain in [-1, 1], Hoeffding gives a radius of sqrt(2 (b ln 2 + ln(m/δ)) / n) for a union over 2^b systems and m events; the empirical-Bernstein radius of Maurer and Pontil (2009) is used when it is smaller. Neither inequality is new.

The ledger certificate takes b = min(B, ℓ). It also evaluates a second system, the **core**: the final system with its incompressible parts removed (here, arbitrary 32-bit patches), which has a short description even when the full system does not. The certificate is the better of the two, with the four events (two systems, two routes) charged in the radius. The ledger is a SHA-256 chain over every verdict, so the bit total cannot be edited afterwards.

`formal/HoldoutLedger.lean` proves the counting argument behind both routes and that charging the cheaper route never certifies less than either alone. The concentration inequality enters as a hypothesis, and nothing is proved about the Python implementation.

## 3. Experiment

Frozen in `PREREG.md` before confirmatory seeds 1000-1199 were run; the commit is recorded in `results/PREREG_COMMIT`.

- **Data.** UCI Covertype, classes 1 vs 2, 495,141 rows: train 60,000, dev 20,000, holdout pool 265,000, reserve 150,000. Only the auditor reads the reserve.
- **System.** A majority-vote ensemble drawn from a pool of 800 trained models. *Early* regime starts from 5 arbitrary members (large headroom). *Late* starts from 15 members forward-selected on dev (near saturation).
- **Proposers.** `pool` swaps one member for a pool member (honest). `patch` flips predictions in the low-margin region selected by a hash, with density 0.005: a stylised hack with no expected true gain. `mixed` picks one of the two at random each move.
- **Gates.** `seq` one bit per query, admit on any positive holdout gain. `seqm` one bit, admit above 1/sqrt(n). `mdl` one bit, admit only if the gain exceeds the radius of the move's own description length. `batch` 64 candidates per round, returning whether any improved and which was best.
- **Grid.** 2 regimes × 3 holdout sizes (5,000; 20,000; 100,000) × 3 proposers × 4 gates × 4 query budgets (64 to 4,096), plus a patch-density sensitivity. 200 seeds per cell.
- **Violation.** A certificate exceeds the reserve-measured gain of the system it is about.

Nine hypotheses with numeric pass criteria were registered. Thresholds were set after a six-seed pilot, which is disclosed; H1-H3 are close to implementation sanity checks, and H4, H5, H8 and H9 carry the empirical content.

## 4. Results

All nine hypotheses pass. Main cell: early regime, n = 20,000, 1,024 queries, 200 seeds per row.

| Gate | Proposer | Admitted gain | True gain | Wald 95% bound (violation rate) | Ledger certificate | Bits released | Description bits |
|---|---|---|---|---|---|---|---|
| seq | pool | 0.229 | 0.229 | 0.223 (3%) | 0.098 | 1,024 | 326 |
| seq | patch | 0.037 | 0.006 | 0.033 (100%) | -0.002 | 1,024 | 6,788 |
| seq | mixed | 0.217 | 0.211 | 0.211 (54%) | 0.112 | 1,024 | 2,079 |
| mdl | pool | 0.216 | 0.217 | 0.210 (3%) | 0.152 | 1,024 | 108 |
| mdl | patch | 0.000 | 0.000 | 0.000 (0%) | -0.002 | 1,024 | 2 |
| mdl | mixed | 0.209 | 0.210 | 0.203 (3%) | 0.147 | 1,024 | 103 |
| batch | pool | 0.226 | 0.226 | 0.220 (6%) | 0.166 | 96 | 139 |
| batch | patch | 0.010 | 0.001 | 0.008 (100%) | -0.002 | 96 | 522 |
| batch | mixed | 0.217 | 0.217 | 0.211 (6%) | 0.157 | 96 | 267 |

1. **Validity.** The ledger certificate exceeded the true gain in 0 of 59,200 runs (one-sided 95% upper bound 0.0001).
2. **The usual interval fails under fitting.** With the patch proposer and the plain gate, the Wald bound was above the true gain in 100% of runs, at all three patch densities tested (0.002, 0.005, 0.02). With the mixed proposer it was wrong in 54%.
3. **Honest and fitted progress separate.** The certificate was positive in 100% of pool runs and 0% of patch runs. For the mixed proposer it certified 0.112 by falling back to the core system.
4. **Pricing admission by complexity blocks fitting cheaply.** The `mdl` gate admitted no patches, kept 94% of the honest true gain, and raised the certified gain from 0.098 to 0.152, because the admitted system is shorter (108 bits against 326).
5. **Batching.** One verdict per 64 candidates kept 98.6% of the true gain with 96 bits instead of 1,024, and certified 0.166. This is the one setting where the information route does the work.
6. **Natural proposers use little of the worst-case budget.** Median overstatement over ledger radius was 0.12 under the patch attack and at most 0.07 for the honest proposer.

Where the strength comes from: at 1,024 one-bit queries the information route alone gives -0.038, which is vacuous. With the plain and `mdl` gates, the certified gain comes from the description route. The result there is a compression argument, and the ledger makes it auditable.

## 5. Limits

- **It certifies less than half the truth in the main cell** (0.098 of 0.229; median ratio 0.43).
- **Small holdouts certify nothing.** At n = 5,000 the early-regime certificate is -0.070 against a true gain of 0.227. At n = 100,000 it is 0.183.
- **Small gains certify nothing.** In the late regime (true gain about 0.001) the certificate is negative in every run at every n up to 100,000. A loop near saturation cannot use this.
- **A zero-bit radius is not always wrong.** It failed in 100% of runs in the registered attack cells, but only 10% in the early mixed cell. "Charging zero bits is unsafe" holds; "it always fails" does not.
- **One dataset, tabular models, scripted proposers.** No LLM agent was run.
- **The attacker is stylised.** No adversary was built against the `mdl` gate. The union bound, not the gate, protects the certificate; a gate-aware attacker could reduce how much honest gain is admitted.
- **The reserve shares the holdout's distribution.** Nothing here addresses shift.
- **Not independently reviewed.** Single author, single machine.

## 6. Relation to prior work

As listed in `PREREG.md`: the reusable holdout (Dwork et al. 2015), the Ladder (Blum and Hardt 2015), rounds-of-adaptivity bounds for natural analysts (Zrnic and Hardt 2019), and the finding that research agents given one bit of feedback lose little, with a description-length explanation but no certificate (Bertran and Roth 2026, arXiv 2606.11045). The contribution claimed here is the combination: a logged minimum over the two routes with a core fallback, an admission gate priced by description length, and measurements of both on real models. Whether that combination is new has not been checked by a literature search beyond these references.

## 7. What would change our mind

We would like readers to try to break the following.

1. A proposer that sees only verdicts and makes the ledger certificate exceed the true gain.
2. A proposer that defeats the `mdl` gate: gets fitted moves admitted, or starves honest ones.
3. A realistic system whose useful changes have no short description, so that the core fallback certifies nothing.
4. An error in the description-length accounting (`hl/bounds.py`, `ell_core`, `ell_full`), in particular the choice to treat pool members as free side information.

## Reproduce

```bash
python -m hl.pool && python -m hl.prepare
python -m hl.experiment confirmatory 1000 1200 results/confirmatory.jsonl
python -m hl.analyze results/confirmatory.jsonl results/
lean formal/HoldoutLedger.lean
```

About 110 minutes on 13 cores. Raw runs: `results/confirmatory.jsonl.gz`.
