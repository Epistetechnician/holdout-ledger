import gzip
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_confirmatory_runs_match_published_hash():
    """The raw runs behind RESULTS.md are the ones the README cites."""
    prefix = re.search(
        r"sha256 of the uncompressed file `([0-9a-f]{8})", (ROOT / "README.md").read_text()
    )
    assert prefix, "README must cite the sha256 prefix"
    h = hashlib.sha256()
    with gzip.open(ROOT / "results" / "confirmatory.jsonl.gz", "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    assert h.hexdigest().startswith(prefix.group(1))


def test_prereg_commit_recorded():
    assert re.fullmatch(r"[0-9a-f]{40}", (ROOT / "results" / "PREREG_COMMIT").read_text().strip())
