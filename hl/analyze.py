"""Evaluate the pre-registered hypotheses (PREREG.md) and draw the figures. Frozen before confirmatory seeds run.
    python -m hl.analyze results/confirmatory.jsonl results/
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import beta

from .bounds import ell_full, radius

CERTS = ["L_wald", "L_naive", "L_info", "L_desc", "L_ledger"]


def load(path):
    return [json.loads(l) for l in open(path)]


def sel(rows, **kw):
    return [r for r in rows if all(r[k] == v for k, v in kw.items())]


def viol(r, c):
    return r[c] > (r["d_true_pick"] if c == "L_ledger" else r["d_true"])


def rate(rows, f):
    k = sum(1 for r in rows if f(r))
    return k, len(rows), k / max(len(rows), 1)


def cp_upper(k, n, a=0.05):
    return 1.0 if n == 0 else float(beta.ppf(1 - a, k + 1, n - k)) if k < n else 1.0


def mean(rows, key):
    return float(np.mean([r[key] for r in rows])) if rows else float("nan")


def evaluate(rows):
    out, H = [], {}
    base = dict(n=20000, K=1024)

    # H1: the common-practice certificate fails under adaptivity
    ok1 = True
    for reg in ("early", "late"):
        rs = sel(rows, regime=reg, proposer="patch", gate="seq", rho=0.005, **base)
        v = rate(rs, lambda r: viol(r, "L_wald"))[2]
        over = mean(rs, "d_hat") - mean(rs, "d_true")
        out.append(f"H1[{reg}] patch/seq: Wald violation {v:.2f} (need >=0.90); overstatement {over:+.4f} (need >=0.01)")
        ok1 &= v >= 0.90 and over >= 0.01
    H["H1"] = ok1

    # H2: ledger validity over the whole grid
    k, n, r_ = rate(rows, lambda r: viol(r, "L_ledger"))
    worst = max(((rate(g, lambda r: viol(r, "L_ledger"))[2], key) for key, g in groups(rows).items()), default=(0, None))
    out.append(f"H2 ledger violations {k}/{n} = {r_:.4f}, one-sided 95% upper {cp_upper(k, n):.4f} (need <=0.05); worst cell {worst[0]:.3f} {worst[1]} (need <=0.05)")
    H["H2"] = cp_upper(k, n) <= 0.05 and worst[0] <= 0.05

    # H3: zero-bit certificate (same family as the ledger) is invalid under attack
    ok3 = True
    for reg, prop in (("early", "patch"), ("late", "patch"), ("late", "mixed")):
        for nn in (5000, 20000, 100000):
            rs = sel(rows, regime=reg, proposer=prop, gate="seq", rho=0.005, n=nn, K=1024)
            v = rate(rs, lambda r: viol(r, "L_naive"))[2]
            out.append(f"H3[{reg},{prop},n={nn}] zero-bit violation {v:.2f} (need >=0.50)")
            ok3 &= v >= 0.5
    H["H3"] = ok3

    # H4: separation in the early regime
    pool = sel(rows, regime="early", proposer="pool", gate="seq", rho=0.005, **base)
    patch = sel(rows, regime="early", proposer="patch", gate="seq", rho=0.005, **base)
    pp = rate(pool, lambda r: r["L_ledger"] > 0)[2]
    pa = rate(patch, lambda r: r["L_ledger"] > 0)[2]
    ratio = float(np.median([r["L_ledger"] / r["d_true_pick"] for r in pool if r["d_true_pick"] > 0]))
    out.append(f"H4 early seq K=1024 n=20000: certified>0 pool {pp:.2f} (>=0.95), patch {pa:.2f} (<=0.05); median certified/true on pool {ratio:.2f} (>=0.30)")
    H["H4"] = pp >= 0.95 and pa <= 0.05 and ratio >= 0.30

    # H5: complexity-priced gate
    ok5 = True
    for prop in ("mixed", "patch"):
        s_ = sel(rows, regime="early", proposer=prop, gate="seq", rho=0.005, **base)
        m_ = sel(rows, regime="early", proposer=prop, gate="mdl", rho=0.005, **base)
        os_, om_ = mean(s_, "d_hat") - mean(s_, "d_true"), mean(m_, "d_hat") - mean(m_, "d_true")
        out.append(f"H5a[{prop}] overstatement seq {os_:+.4f} -> mdl {om_:+.4f} (need mdl <= 0.2 x seq)")
        ok5 &= om_ <= 0.2 * os_
    s_ = sel(rows, regime="early", proposer="pool", gate="seq", rho=0.005, **base)
    m_ = sel(rows, regime="early", proposer="pool", gate="mdl", rho=0.005, **base)
    keep = mean(m_, "d_true") / mean(s_, "d_true")
    dL = mean(m_, "L_ledger") - mean(s_, "L_ledger")
    out.append(f"H5b pool: mdl keeps {keep:.3f} of seq true gain (need >=0.90); certified gain change {dL:+.4f} (need >=+0.02)")
    H["H5"] = ok5 and keep >= 0.90 and dL >= 0.02

    # H6: honest limit, late regime
    ok6 = True
    for nn in (5000, 20000):
        rs = sel(rows, regime="late", proposer="pool", gate="seq", rho=0.005, n=nn, K=1024)
        v = rate(rs, lambda r: r["L_ledger"] > 0)[2]
        out.append(f"H6[n={nn}] late pool/seq certified>0 {v:.2f} (need <=0.10)")
        ok6 &= v <= 0.10
    rs = sel(rows, regime="late", proposer="pool", gate="seq", rho=0.005, n=100000, K=1024)
    out.append(f"H6-info n=100000 late pool/seq certified>0 {rate(rs, lambda r: r['L_ledger'] > 0)[2]:.2f} (reported, not tested)")
    H["H6"] = ok6

    # H7: batching keeps progress
    s_ = sel(rows, regime="early", proposer="pool", gate="seq", rho=0.005, **base)
    b_ = sel(rows, regime="early", proposer="pool", gate="batch", rho=0.005, **base)
    r7 = mean(b_, "d_true") / mean(s_, "d_true")
    out.append(f"H7 early pool K=1024: batch keeps {r7:.3f} of seq true gain (need >=0.80); bits {mean(b_, 'b_in'):.0f} vs {mean(s_, 'b_in'):.0f}")
    H["H7"] = r7 >= 0.80

    # H8/H9: how tight is the worst-case radius, for an attacker versus a natural proposer?
    def tight(rs):
        return float(np.median([(r["d_hat"] - r["d_true"]) / radius(min(r["b_in"], r["ell_full"]), r["n"], 0.05, 4, r["v_final"]) for r in rs]))
    t8 = tight(sel(rows, regime="early", proposer="patch", gate="seq", rho=0.005, **base))
    out.append(f"H8 early patch/seq: median overstatement / ledger radius = {t8:.3f} (need >=0.10: the bound is not vacuous)")
    H["H8"] = t8 >= 0.10
    t9 = [tight(sel(rows, regime=reg, proposer="pool", gate="seq", rho=0.005, **base)) for reg in ("early", "late")]
    out.append(f"H9 pool/seq median overstatement / ledger radius: early {t9[0]:.3f}, late {t9[1]:.3f} (need both <=0.10: natural proposers use little of the budget)")
    H["H9"] = max(t9) <= 0.10
    return out, H


def groups(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r["regime"], r["n"], r["proposer"], r["gate"], r["K"], r["rho"])].append(r)
    return g


def figures(rows, outdir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = outdir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    col = {"pool": "#2a7", "patch": "#c33", "mixed": "#c80"}

    # F1: admitted vs true vs certified over queries (seq gate, n=20000), early and late
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.2), sharex=True)
    for ax, reg in zip(axs, ("early", "late")):
        for prop in ("pool", "patch", "mixed"):
            rs = sel(rows, regime=reg, proposer=prop, gate="seq", rho=0.005, n=20000, K=4096)
            if not rs:
                continue
            T = np.array([[t[:3] for t in r["traj"]] for r in rs])
            q = T[0, :, 0]
            ax.plot(q, T[:, :, 1].mean(0), color=col[prop], ls="--", label=f"{prop} admitted")
            ax.plot(q, T[:, :, 2].mean(0), color=col[prop], ls="-", label=f"{prop} true")
            Ls = []
            for r in rs:
                Ls.append([t[1] - radius(min(t[3], ell_full(int(t[4]), int(t[5]), 800, 5 if reg == "early" else 15)), 20000, 0.05, 2)
                           for t in r["traj"]])
            ax.plot(q, np.mean(Ls, 0), color=col[prop], ls=":", label=f"{prop} certified (final system)")
        ax.set_xscale("log"); ax.set_xlabel("holdout queries"); ax.set_title(f"{reg} regime, n=20,000")
        ax.axhline(0, color="k", lw=0.5)
    axs[0].set_ylabel("gain over reference system"); axs[1].legend(fontsize=7, ncol=1)
    fig.tight_layout(); fig.savefig(fig_dir / "f1_admitted_true_certified.png", dpi=150); plt.close(fig)

    # F2: violation rates by certificate, K=1024, n=20000, seq
    fig, axs = plt.subplots(1, 2, figsize=(12, 3.8), sharey=True)
    for ax, reg in zip(axs, ("early", "late")):
        w = 0.25
        for i, prop in enumerate(("pool", "patch", "mixed")):
            rs = sel(rows, regime=reg, proposer=prop, gate="seq", rho=0.005, n=20000, K=1024)
            ax.bar(np.arange(len(CERTS)) + (i - 1) * w, [rate(rs, lambda r, c=c: viol(r, c))[2] for c in CERTS], w, color=col[prop], label=prop)
        ax.axhline(0.05, color="k", lw=0.8, ls="--"); ax.set_xticks(range(len(CERTS)), CERTS, fontsize=8); ax.set_title(reg)
    axs[0].set_ylabel("violation rate (certified > true)"); axs[0].legend()
    fig.tight_layout(); fig.savefig(fig_dir / "f2_violation_rates.png", dpi=150); plt.close(fig)

    # F3: admitted vs true gain by gate (early, n=20000, K=1024)
    fig, ax = plt.subplots(figsize=(5.6, 5))
    mk = {"seq": "o", "seqm": "s", "mdl": "*", "batch": "^"}
    for gate in ("seq", "seqm", "mdl", "batch"):
        for prop in ("pool", "patch", "mixed"):
            rs = sel(rows, regime="late", proposer=prop, gate=gate, rho=0.005, n=20000, K=1024)
            if rs:
                ax.scatter(mean(rs, "d_true"), mean(rs, "d_hat"), marker=mk[gate], color=col[prop], s=70, label=f"{gate}/{prop}")
    lim = ax.get_xlim(); ax.plot(lim, lim, "k-", lw=0.5); ax.set_xlabel("true gain (reserve)"); ax.set_ylabel("admitted gain (holdout)")
    ax.set_title("late regime: above the line = overstated"); ax.legend(fontsize=6, ncol=2)
    fig.tight_layout(); fig.savefig(fig_dir / "f3_overstatement_by_gate.png", dpi=150); plt.close(fig)


def main(path: Path, outdir: Path):
    rows = load(path)
    lines, H = evaluate(rows)
    md = ["# Confirmatory results", f"{len(rows)} runs from `{path.name}`.", ""] + [f"- {l}" for l in lines] + ["", "## Verdicts"]
    md += [f"- **{k}: {'PASS' if v else 'FAIL'}**" for k, v in sorted(H.items())]
    (outdir / "RESULTS.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    figures(rows, outdir)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
