"""Run the grid in parallel, appending one JSON line per run. Usage:
    python -m hl.experiment GRID SEED_LO SEED_HI OUT.jsonl
GRID is "confirmatory" or "pilot". The grid is frozen in PREREG.md before confirmatory seeds are run.
"""

from __future__ import annotations

import itertools
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from .sim import Env, run

DATA = Path("data")
RHO = 0.005
_ENVS: dict = {}


def grid(name: str):
    if name == "pilot":
        for reg, n, prop, gate, K in itertools.product(
            ["early", "late"],
            [5000, 20000],
            ["pool", "patch", "mixed"],
            ["seq", "mdl", "batch"],
            [256, 1024],
        ):
            yield dict(regime=reg, n=n, proposer=prop, gate=gate, K=K, rho=RHO)
        return
    for reg, n, prop, gate, K in itertools.product(
        ["early", "late"],
        [5000, 20000, 100000],
        ["pool", "patch", "mixed"],
        ["seq", "seqm", "mdl", "batch"],
        [64, 256, 1024, 4096],
    ):
        yield dict(regime=reg, n=n, proposer=prop, gate=gate, K=K, rho=RHO)
    # sensitivity of the stylised attack to its density
    for reg, prop, rho in itertools.product(["early", "late"], ["patch", "mixed"], [0.002, 0.02]):
        yield dict(regime=reg, n=20000, proposer=prop, gate="seq", K=1024, rho=rho)


def work(task):
    cfg, seed = task
    env = _ENVS.setdefault(cfg["regime"], Env(DATA, regime=cfg["regime"]))
    t0 = time.time()
    r = run(
        env,
        n=cfg["n"],
        proposer=cfg["proposer"],
        gate=cfg["gate"],
        K=cfg["K"],
        seed=seed,
        rho=cfg["rho"],
    )
    r["regime"], r["rho"], r["secs"] = cfg["regime"], cfg["rho"], round(time.time() - t0, 2)
    return r


def main(name: str, lo: int, hi: int, out: Path):
    tasks = [(c, s) for c in grid(name) for s in range(lo, hi)]
    print(f"{len(tasks)} runs", flush=True)
    t0 = time.time()
    with Pool(13) as pool, out.open("a") as f:
        for i, r in enumerate(pool.imap_unordered(work, tasks, chunksize=4)):
            f.write(json.dumps(r) + "\n")
            if i % 500 == 0:
                f.flush()
                print(f"{i}/{len(tasks)} {time.time() - t0:.0f}s", flush=True)
    print("done", time.time() - t0, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
