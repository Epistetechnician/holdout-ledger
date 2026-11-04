"""Convert pool.npz to memmap-friendly files and fit the pre-declared base system (train split only)."""
import sys
from pathlib import Path

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from .pool import X_N_FEATURES, load_split, N_TRAIN, N_HOLD  # noqa: F401


def main(data: Path):
    z = np.load(data / "pool.npz")
    P, y = z["P"], z["y"]
    np.save(data / "S.npy", (2 * P.astype(np.int8) - 1).astype(np.int8))
    X, y2 = load_split(data / "raw")
    assert (y2 == y).all()
    base = DecisionTreeClassifier(max_depth=8, random_state=0).fit(X[:N_TRAIN], y[:N_TRAIN])
    base01 = base.predict(X).astype(np.int8)
    np.savez(data / "meta.npz", y=y, n_train=N_TRAIN, n_hold=N_HOLD, base01=base01)
    R0 = N_TRAIN + N_HOLD
    print(f"base accuracy: train {np.mean(base01[:N_TRAIN]==y[:N_TRAIN]):.4f} reserve {np.mean(base01[R0:]==y[R0:]):.4f}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
