# Replicating this result

Three levels, cheapest first. Please report any failure as an issue.

1. **Integrity (seconds).** `pip install -r requirements-dev.txt && pytest -q` checks the ledger,
   the bounds, and that `results/confirmatory.jsonl.gz` matches the hash the README cites.
2. **Re-analysis (minutes).** `gunzip -k results/confirmatory.jsonl.gz && python -m hl.analyze results/confirmatory.jsonl /tmp/out`
   and diff `/tmp/out` against `results/RESULTS.md`. All nine hypotheses should pass.
3. **Full rerun (about 110 min on 13 cores).** `python -m hl.pool && python -m hl.prepare`, then
   `python -m hl.experiment confirmatory 1000 1200 out.jsonl`. Seeds are fixed; numbers should match.

Pre-registration: `PREREG.md`, frozen at the commit in `results/PREREG_COMMIT`. Code was later
reformatted with ruff (whitespace only); diff against that commit to check.
