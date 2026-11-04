"""Build the candidate pool: ~800 real models trained on real data (UCI Covertype, classes 1 vs 2).

The pool is generated from the TRAIN split only. Holdout and reserve are never seen
by any model, so indexing a pool member costs log2(M) bits of description, not its weights.
"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed
from sklearn.datasets import fetch_covtype
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, ExtraTreeClassifier

SPLIT_SEED = 20261104
N_TRAIN, N_HOLD = 60_000, 285_000  # reserve = everything else (150k)


def load_split(cache: Path):
    data = fetch_covtype(data_home=str(cache), download_if_missing=True)
    X, y = data.data, data.target
    keep = np.isin(y, [1, 2])
    X, y = X[keep].astype(np.float32), (y[keep] == 2).astype(np.int8)
    perm = np.random.default_rng(SPLIT_SEED).permutation(len(y))
    X, y = X[perm], y[perm]
    return X, y


def make_spec(m: int) -> dict:
    """Deterministic spec for pool member m: a model family plus hyperparameters."""
    r = np.random.default_rng(1000 + m)
    fam = ["tree", "xtree", "forest", "xforest", "logreg", "nb", "hgb"][m % 7]
    nfeat = X_N_FEATURES
    feats = np.sort(r.choice(nfeat, size=int(r.integers(6, nfeat + 1)), replace=False))
    sub = int(r.integers(2_000, N_TRAIN + 1))
    spec = dict(m=m, fam=fam, feats=feats.tolist(), sub=sub, seed=int(r.integers(1 << 30)))
    if fam in ("tree", "xtree"):
        spec["depth"] = int(r.integers(2, 21))
    elif fam in ("forest", "xforest"):
        spec["depth"] = int(r.integers(3, 16))
        spec["trees"] = int(r.integers(3, 31))
    elif fam == "logreg":
        spec["C"] = float(10 ** r.uniform(-3, 1))
    elif fam == "hgb":
        spec["iters"] = int(r.integers(5, 60))
        spec["depth"] = int(r.integers(2, 8))
    return spec


X_N_FEATURES = 54


def fit_predict(spec, Xtr, ytr, Xall):
    r = np.random.default_rng(spec["seed"])
    idx = r.choice(len(ytr), size=spec["sub"], replace=False)
    f = np.array(spec["feats"])
    A, b = Xtr[idx][:, f], ytr[idx]
    fam = spec["fam"]
    if fam == "tree":
        mdl = DecisionTreeClassifier(max_depth=spec["depth"], random_state=spec["seed"])
    elif fam == "xtree":
        mdl = ExtraTreeClassifier(max_depth=spec["depth"], random_state=spec["seed"])
    elif fam == "forest":
        mdl = RandomForestClassifier(n_estimators=spec["trees"], max_depth=spec["depth"], random_state=spec["seed"], n_jobs=1)
    elif fam == "xforest":
        mdl = ExtraTreesClassifier(n_estimators=spec["trees"], max_depth=spec["depth"], random_state=spec["seed"], n_jobs=1)
    elif fam == "logreg":
        mdl = make_pipeline(StandardScaler(), LogisticRegression(C=spec["C"], max_iter=200))
    elif fam == "nb":
        mdl = GaussianNB()
    else:
        mdl = HistGradientBoostingClassifier(max_iter=spec["iters"], max_depth=spec["depth"], random_state=spec["seed"])
    mdl.fit(A, b)
    return mdl.predict(Xall[:, f]).astype(np.int8)


def main(out: Path, M: int = 800):
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    X, y = load_split(out / "raw")
    N = len(y)
    Xtr, ytr = X[:N_TRAIN], y[:N_TRAIN]
    print(f"N={N} train={N_TRAIN} hold={N_HOLD} reserve={N - N_TRAIN - N_HOLD}", flush=True)
    specs = [make_spec(m) for m in range(M)]
    preds = Parallel(n_jobs=12, verbose=5)(delayed(fit_predict)(s, Xtr, ytr, X) for s in specs)
    P = np.stack(preds)  # (M, N) int8 in {0,1}
    acc_hold = (P[:, N_TRAIN:N_TRAIN + N_HOLD] == y[N_TRAIN:N_TRAIN + N_HOLD]).mean(1)
    acc_res = (P[:, N_TRAIN + N_HOLD:] == y[N_TRAIN + N_HOLD:]).mean(1)
    np.savez(out / "pool.npz", P=P, y=y, n_train=N_TRAIN, n_hold=N_HOLD)
    digest = hashlib.sha256(P.tobytes() + y.tobytes()).hexdigest()
    (out / "pool_manifest.txt").write_text(
        f"sha256 {digest}\nM {M}\nN {N}\nsplit_seed {SPLIT_SEED}\n"
        f"acc_reserve min/median/max {acc_res.min():.4f} {np.median(acc_res):.4f} {acc_res.max():.4f}\n"
        f"acc_hold-vs-reserve max abs diff {np.abs(acc_hold - acc_res).max():.4f}\n"
    )
    print((out / "pool_manifest.txt").read_text())
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 800)
