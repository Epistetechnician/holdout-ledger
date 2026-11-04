"""Self-improvement loop against a sealed holdout: proposers x gates, with an out-of-band auditor.

Isolation: `Loop` never gives the proposer labels. The gate sees only holdout labels. The auditor
(`true_gain`) is the only code path that touches the reserve, and nothing it computes flows back.

System = a k-member voting ensemble of real trained models, started from E0 (chosen on a dev split;
ties fall back to a fixed base tree). Natural moves swap one member for a pool member. Patches flip the
low-margin predictions selected by a hash of (seed, example id): a stylised "special-case the
borderline cases" reward hack with zero expected true gain.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .bounds import SEED_BITS, certificates, ell_core, ell_full, radius
from .ledger import Ledger

DEV = 20_000
TAU, RHO = 1, 0.05  # patch region |vote| <= TAU, flip density RHO (frozen in PREREG.md)


def uhash(seed: int, idx: np.ndarray) -> np.ndarray:
    """Counter-based uniform(0,1) per (seed, example id); same value wherever the example appears."""
    with np.errstate(over="ignore"):
        x = idx.astype(np.uint64) + np.uint64(seed) * np.uint64(0x9E3779B97F4A7C15)
        x ^= x >> np.uint64(30)
        x *= np.uint64(0xBF58476D1CE4E5B9)
        x ^= x >> np.uint64(27)
        x *= np.uint64(0x94D049BB133111EB)
        x ^= x >> np.uint64(31)
    return (x >> np.uint64(11)).astype(np.float64) * (1.0 / (1 << 53))


class Env:
    def __init__(self, data: Path, regime: str = "early"):
        self.S = np.load(data / "S.npy", mmap_mode="r")      # (M, N) int8 in {-1,+1}
        z = np.load(data / "meta.npz")
        self.y, self.n_train, self.n_hold = z["y"], int(z["n_train"]), int(z["n_hold"])
        self.base01 = z["base01"]                             # (N,) int8 base predictions
        self.M, self.N = self.S.shape
        self.R0 = self.n_train + self.n_hold                  # reserve = [R0, N)
        self.yR = self.y[self.R0:]
        self.idxR = np.arange(self.R0, self.N)
        self.dev0, self.dev1 = self.n_train, self.n_train + DEV   # dev = head of hold pool; H never touches it
        self.regime = regime
        # early: 5 arbitrary members (lots of headroom); late: 15 forward-selected on dev (near saturation)
        self.E0 = (list(np.random.default_rng(7).choice(self.M, 5, replace=False))
                   if regime == "early" else self._warm_start(15))
        self.E0 = [int(m) for m in self.E0]

    def _warm_start(self, k: int) -> list[int]:
        """Fixed reference system: forward-select k pool members on DEV labels. Independent of any holdout."""
        Sd = np.asarray(self.S[:, self.dev0:self.dev1]).astype(np.int16)
        yd, bd = self.y[self.dev0:self.dev1], self.base01[self.dev0:self.dev1]
        v, chosen = np.zeros(Sd.shape[1], np.int16), []
        for _ in range(k):
            best, bm = -1, -1
            for m in range(self.M):
                if m in chosen:
                    continue
                vv = v + Sd[m]
                c = int((((vv > 0) | ((vv == 0) & (bd == 1))) == yd).sum())
                if c > best:
                    best, bm = c, m
            chosen.append(bm)
            v = v + Sd[bm]
        return chosen


@dataclass
class Move:
    kind: str   # "pool" | "patch"
    arg: int


class Sys:
    """Incumbent system with incremental vote tallies on the holdout (H) and the reserve (R)."""

    def __init__(self, env: Env, hidx: np.ndarray, rho: float = RHO):
        self.env, self.hidx, self.rho = env, hidx, rho
        self.SH = np.asarray(env.S[:, hidx])                  # (M, n) int8 gather, once per run
        self.yH = env.y[hidx]
        self.baseH01 = env.base01[hidx]
        self.vH = self.SH[env.E0].sum(0, dtype=np.int16)          # warm-start ensemble E0 votes first
        self.vR = np.asarray(env.S[env.E0, env.R0:]).sum(0, dtype=np.int16)
        self.FH = np.zeros(len(hidx), bool)
        self.FR = np.zeros(len(env.idxR), bool)
        self.active: list[int] = list(env.E0)
        self.swaps: list[tuple[int, int]] = []
        self.patches: list[int] = []

    @staticmethod
    def _pred(v, base01, F):
        p = (v > 0) | ((v == 0) & (base01 == 1))
        return p ^ (F & (np.abs(v) <= TAU))

    def correct_H(self, v=None, F=None) -> int:
        v = self.vH if v is None else v
        F = self.FH if F is None else F
        return int((self._pred(v, self.baseH01, F) == self.yH).sum())

    def cand_H(self, mv: Move) -> int:
        if mv.kind == "pool":
            j, m = mv.arg
            return self.correct_H(v=self.vH + self.SH[m] - self.SH[self.active[j]])
        return self.correct_H(F=self.FH ^ (uhash(mv.arg, self.hidx) < self.rho))

    def _corr(self, v, F) -> np.ndarray:
        return (self._pred(v, self.baseH01, F) == self.yH).astype(np.int8)

    def cand_vec_H(self, mv: Move) -> np.ndarray:
        if mv.kind == "pool":
            j, m = mv.arg
            return self._corr(self.vH + self.SH[m] - self.SH[self.active[j]], self.FH)
        return self._corr(self.vH, self.FH ^ (uhash(mv.arg, self.hidx) < self.rho))

    def commit(self, mv: Move) -> None:
        env = self.env
        if mv.kind == "pool":
            j, m = mv.arg
            old = self.active[j]
            self.vH = self.vH + self.SH[m] - self.SH[old]
            self.vR = self.vR + env.S[m, env.R0:] - env.S[old, env.R0:]
            self.active[j] = m
            self.swaps.append((j, m))
        else:
            self.FH = self.FH ^ (uhash(mv.arg, self.hidx) < self.rho)
            self.FR = self.FR ^ (uhash(mv.arg, env.idxR) < self.rho)
            self.patches.append(mv.arg)

    # ---- auditor-only (reserve) ----
    def true_correct(self, core: bool = False) -> float:
        F = np.zeros_like(self.FR) if core else self.FR
        return float((self._pred(self.vR, self.env.base01[self.env.R0:], F) == self.env.yR).mean())

    def core_correct_H(self) -> int:
        return self.correct_H(F=np.zeros_like(self.FH))

    def corr_vec_H(self, core: bool = False) -> np.ndarray:
        F = np.zeros_like(self.FH) if core else self.FH
        return (self._pred(self.vH, self.baseH01, F) == self.yH).astype(np.int8)


def propose(kind: str, sysm: Sys, rng: np.random.Generator) -> Move:
    if kind == "mixed":
        kind = "pool" if rng.random() < 0.5 else "patch"
    if kind == "pool":
        while True:
            m = int(rng.integers(sysm.env.M))
            if m not in sysm.active:
                return Move("pool", (int(rng.integers(len(sysm.active))), m))
    return Move("patch", int(rng.integers(1, 1 << 31)))


def run(env: Env, *, n: int, proposer: str, gate: str, K: int, seed: int, delta: float = 0.05,
        N_batch: int = 64, eta_mult: float = 1.0, rho: float = RHO) -> dict:
    """gate: 'seq' (1 bit/query, margin 0) | 'mdl' (1 bit/query, margin = radius of the move's own description) | 'seqm' (1 bit/query, margin eta_mult/sqrt(n)) | 'batch' (argmax per round)."""
    rng = np.random.default_rng([seed, n, K, zlib.crc32(proposer.encode()), zlib.crc32(gate.encode())])
    hidx = env.dev1 + rng.choice(env.n_hold - DEV, size=n, replace=False)
    s = Sys(env, hidx, rho)
    led = Ledger(n, delta)
    c_base = s.correct_H()
    cb_vec = s.corr_vec_H()
    r_base = s.true_correct()
    cur = c_base
    eta = 0.0 if gate in ("seq", "batch") else eta_mult / math.sqrt(n)
    marks = {2 ** j for j in range(int(math.log2(K)) + 1)} | {K}
    traj = []

    def snapshot(q):
        d_hat = (cur - c_base) / n
        d_true = s.true_correct() - r_base
        traj.append((q, d_hat, d_true, led.bits_in, len(s.swaps), len(s.patches)))

    q = 0
    if gate == "batch":
        rounds = K // N_batch
        for g in range(rounds):
            mvs = [propose(proposer, s, rng) for _ in range(N_batch)]
            cs = np.array([s.cand_H(m) for m in mvs])
            i = int(cs.argmax())
            improved = (cs[i] - cur) / n > eta
            led.append(math.log2(N_batch + 1), [int(improved), i if improved else -1])
            if improved:
                s.commit(mvs[i]); cur = int(cs[i])
            q = (g + 1) * N_batch
            if q in marks or g == rounds - 1:
                snapshot(q)
    elif gate == "mdl":
        # complexity-priced admission: a move must beat the radius of ITS OWN description length
        k = len(env.E0)
        inc = s.corr_vec_H().astype(np.int16)
        for q in range(1, K + 1):
            mv = propose(proposer, s, rng)
            cv = s.cand_vec_H(mv)
            dl = cv.astype(np.int16) - inc
            bits = (math.log2(k) + math.log2(env.M)) if mv.kind == "pool" else SEED_BITS
            improved = float(dl.mean()) > radius(bits, n, delta, 1, float(dl.var(ddof=1)))
            led.append(1.0, int(improved))
            if improved:
                s.commit(mv); inc = cv.astype(np.int16); cur = int(cv.sum())
            if q in marks:
                snapshot(q)
    else:
        for q in range(1, K + 1):
            mv = propose(proposer, s, rng)
            c = s.cand_H(mv)
            improved = (c - cur) / n > eta
            led.append(1.0, int(improved))
            if improved:
                s.commit(mv); cur = c
            if q in marks:
                snapshot(q)

    assert led.verify()
    d_final = (cur - c_base) / n
    d_core = (s.core_correct_H() - c_base) / n
    t_final = s.true_correct() - r_base
    t_core = s.true_correct(core=True) - r_base
    sm, pt = len(s.swaps), len(s.patches)
    k = len(env.E0)
    ef, ec = ell_full(sm, pt, env.M, k), ell_core(sm, env.M, k)
    v_final = float(np.var(s.corr_vec_H().astype(np.int16) - cb_vec, ddof=1))
    v_core = float(np.var(s.corr_vec_H(core=True).astype(np.int16) - cb_vec, ddof=1))
    cert = certificates(d_final, d_core, n, delta, led.bits_in, ef, ec, v_final, v_core)
    pick_true = t_core if cert["ledger_pick"] == "core" else t_final
    return dict(n=n, proposer=proposer, gate=gate, K=K, seed=seed, swaps=sm, d_true_pick=pick_true, patches=pt,
                v_final=v_final, b_in=led.bits_in, ell_full=ef, ell_core=ec, d_hat=d_final, d_hat_core=d_core,
                d_true=t_final, d_true_core=t_core, base_acc_R=r_base, **cert, traj=traj)
