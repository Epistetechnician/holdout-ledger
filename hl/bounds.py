"""Certificates: how many bits of evidence did an admitted gain consume, and what radius does that buy?

Two valid accounting routes (both are union bounds over a finite class fixed before the holdout is read):

* information route  B_in : the verdicts the gate released. Every system the proposer could output is
  indexed by the verdict transcript, so there are at most 2**B_in of them.
* description route  ell  : the length of the output system in a fixed prefix-free grammar (Occam).
  The class of programs of length <= ell is fixed in advance, whatever the proposer queried.

For a paired gain d_i = 1[sys correct] - 1[base correct] in [-1, 1], Hoeffding gives
P(empirical gain - true gain >= t) <= exp(-n t^2 / 2) per fixed system, so the radius for a union of
2**bits systems at confidence delta over `routes` events is sqrt(2 (bits ln2 + ln(routes/delta)) / n).
The concentration step is classical; nothing here claims a new inequality.
"""

from __future__ import annotations

import math

LN2 = math.log(2.0)
SEED_BITS = 32  # an arbitrary patch is an arbitrary 32-bit seed: incompressible content


def gamma_len(z: int) -> float:
    """Elias-gamma code length for an integer z >= 1 (prefix-free)."""
    return 2 * math.floor(math.log2(z)) + 1


def log2_choose(m: int, s: int) -> float:
    return (math.lgamma(m + 1) - math.lgamma(s + 1) - math.lgamma(m - s + 1)) / LN2


def ell_core(s: int, pool_size: int, k: int) -> float:
    """Bits to name s swaps (position in the k-member ensemble, pool member). Training data is side
    information, so a pool member's weights are free; naming it costs log2(pool_size)."""
    return gamma_len(s + 1) + s * (math.log2(k) + math.log2(pool_size))


def ell_full(s: int, p: int, pool_size: int, k: int) -> float:
    """Swaps plus p arbitrary patch seeds."""
    return ell_core(s, pool_size, k) + gamma_len(p + 1) + SEED_BITS * p


def radius(bits: float, n: int, delta: float, routes: int = 1, vhat: float | None = None) -> float:
    """Radius for a union of 2**bits systems over `routes` events.

    Hoeffding (range 2). If the sample variance vhat of the paired differences is given, also the
    empirical-Bernstein radius of Maurer & Pontil (2009, Thm 4) and take the smaller; that pair of
    bounds doubles the event count, which is charged here.
    """
    if vhat is None:
        return math.sqrt(2.0 * (bits * LN2 + math.log(routes / delta)) / n)
    h = math.sqrt(2.0 * (bits * LN2 + math.log(2 * routes / delta)) / n)
    L = bits * LN2 + math.log(4 * routes / delta)
    eb = math.sqrt(2.0 * vhat * L / n) + 14.0 * L / (3.0 * (n - 1))
    return min(h, eb)


def wald_lower(dhat: float, vhat: float, n: int, z: float = 1.645) -> float:
    """What people report: a one-sided 95% interval that treats the holdout as fresh."""
    return dhat - z * math.sqrt(vhat / n)


def certificates(
    dhat_final: float,
    dhat_core: float,
    n: int,
    delta: float,
    b_in: float,
    ell_final: float,
    ell_core_bits: float,
    v_final: float,
    v_core: float,
) -> dict:
    """Lower bounds on true gain. Each is valid at confidence 1 - delta for the route it names."""
    out = {
        "L_wald": wald_lower(dhat_final, v_final, n),  # common practice: fresh-holdout interval
        "L_naive": dhat_final
        - radius(0.0, n, delta, 1, v_final),  # same family as the ledger, zero bits charged
        "L_info": dhat_final - radius(b_in, n, delta, 1, v_final),  # information route only
        "L_desc": dhat_final - radius(ell_final, n, delta, 1, v_final),  # description route only
    }
    # ledger: best of {final, core}, each charged min(info, description); 2 systems x 2 routes = 4 events
    cand = [
        (dhat_final - radius(min(b_in, ell_final), n, delta, 4, v_final), "final"),
        (dhat_core - radius(min(b_in, ell_core_bits), n, delta, 4, v_core), "core"),
    ]
    out["L_ledger"], out["ledger_pick"] = max(cand)
    out["route"] = "info" if b_in <= ell_final else "desc"
    return out
