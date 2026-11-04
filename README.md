# Holdout ledger

Pricing evidence in bits for sealed-holdout self-improvement.

A self-improvement loop asks a sealed holdout "did that help?" over and over. Each verdict leaks holdout information into the next proposal, so the reported gain drifts above the true gain. This repo keeps a hash-chained **ledger** of the verdict bits released and the description length of what shipped, and certifies a gain using the cheaper of the two routes.

Everything below was pre-registered (`PREREG.md`, commit in `results/PREREG_COMMIT`) before the 200 confirmatory seeds ran. 59,200 runs, 9 hypotheses, **all 9 pass** (`results/RESULTS.md`). Read "What this does not show" before citing it.

## Result (early regime, n = 20,000 holdout examples, 1,024 queries, one-bit gate)

| proposer | admitted gain | true gain (reserve) | usual 95% Wald bound | ledger bound |
|---|---|---|---|---|
| pool swaps (honest) | 0.229 | 0.229 | 0.223 (valid, 3% violation) | 0.098 |
| patch (holdout fitting) | 0.037 | 0.006 | 0.033, **wrong in 100% of runs** | -0.002 (no claim) |
| mixed | 0.217 | 0.211 | 0.211, **wrong in 54%** | 0.112 |

* The ledger certificate was never wrong: 0 violations in 59,200 runs (one-sided 95% upper bound 0.0001).
* The same radius with zero bits billed was wrong in 100% of attacked runs in every cell tested.
* A complexity-priced admission gate (`mdl`) admitted no patches and kept 94% of the true gain; certified gain rose from 0.098 to 0.152.
* Batching 64 candidates per verdict kept 98.6% of the gain with 96 bits instead of 1,024; certified gain 0.166.
* Honest limit: in the late regime (15 members already tuned, true gain about 0.001) nothing is certifiable at n up to 100,000.

Figures: `results/figures/`. Raw runs: `results/confirmatory.jsonl.gz` (sha256 of the uncompressed file `39401832...b3bc`).

## What is new, and what is not

Not new: adaptive overfitting and its remedies (Dwork et al. 2015; Blum and Hardt 2015; Zrnic and Hardt 2019) and the observation that agents given one bit lose little (Bertran and Roth 2026).

New here, as tested: a certificate that charges the minimum of verdict bits and output description length, with a "core" fallback that certifies the compressible part after stripping the incompressible part; a measured separation of honest and fitting progress by billed bits; a complexity-priced online gate; and a measurement of how little of the worst-case budget natural proposers use.

## Where the certificate's strength comes from

At 1,024 one-bit queries the information route alone is vacuous (-0.038). Essentially all certified gain comes from the description route: the final system is a handful of swaps, about 100 bits. The result is a compression argument, and the ledger's job is to make it auditable and to fall back to the core when a patch is present. The information route matters when descriptions are long and queries are few, which this grid barely probes.

## What this does not show

* One dataset (Covertype 1 vs 2), tabular models, not an LLM agent.
* The attacker is stylised (random low-margin flips). No adversary was built against the `mdl` gate. The union bound, not the gate, protects the certificate.
* H1-H3 are implementation sanity checks. Thresholds were set after a pilot (disclosed in `PREREG.md`). H4, H5, H8, H9 carry the empirical content.
* The reserve shares the holdout's distribution.
* Formal evidence is Level 1: `formal/HoldoutLedger.lean` proves the counting union bounds and monotonicity of the certificate in core Lean (standard axioms only). The concentration inequality is an assumed hypothesis, and nothing proves the Python implementation.

## Reproduce

```bash
python -m hl.pool && python -m hl.prepare          # builds data/ (about 1 minute)
python -m hl.experiment confirmatory 1000 1200 results/confirmatory.jsonl   # about 110 minutes on 13 cores
python -m hl.analyze results/confirmatory.jsonl results/
lean formal/HoldoutLedger.lean
```

## Next experiment

Replace the scripted proposers with an LLM agent that sees only verdicts, including one told to defeat the `mdl` gate. Run it on a second dataset, with the budget and thresholds pre-registered first.
