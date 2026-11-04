# Confirmatory results
59200 runs from `confirmatory.jsonl`.

- H1[early] patch/seq: Wald violation 1.00 (need >=0.90); overstatement +0.0307 (need >=0.01)
- H1[late] patch/seq: Wald violation 1.00 (need >=0.90); overstatement +0.0145 (need >=0.01)
- H2 ledger violations 0/59200 = 0.0000, one-sided 95% upper 0.0001 (need <=0.05); worst cell 0.000 ('late', 100000, 'pool', 'seqm', 4096, 0.005) (need <=0.05)
- H3[early,patch,n=5000] zero-bit violation 1.00 (need >=0.50)
- H3[early,patch,n=20000] zero-bit violation 1.00 (need >=0.50)
- H3[early,patch,n=100000] zero-bit violation 1.00 (need >=0.50)
- H3[late,patch,n=5000] zero-bit violation 1.00 (need >=0.50)
- H3[late,patch,n=20000] zero-bit violation 1.00 (need >=0.50)
- H3[late,patch,n=100000] zero-bit violation 1.00 (need >=0.50)
- H3[late,mixed,n=5000] zero-bit violation 1.00 (need >=0.50)
- H3[late,mixed,n=20000] zero-bit violation 1.00 (need >=0.50)
- H3[late,mixed,n=100000] zero-bit violation 1.00 (need >=0.50)
- H4 early seq K=1024 n=20000: certified>0 pool 1.00 (>=0.95), patch 0.00 (<=0.05); median certified/true on pool 0.43 (>=0.30)
- H5a[mixed] overstatement seq +0.0062 -> mdl -0.0010 (need mdl <= 0.2 x seq)
- H5a[patch] overstatement seq +0.0307 -> mdl +0.0000 (need mdl <= 0.2 x seq)
- H5b pool: mdl keeps 0.944 of seq true gain (need >=0.90); certified gain change +0.0538 (need >=+0.02)
- H6[n=5000] late pool/seq certified>0 0.00 (need <=0.10)
- H6[n=20000] late pool/seq certified>0 0.00 (need <=0.10)
- H6-info n=100000 late pool/seq certified>0 0.00 (reported, not tested)
- H7 early pool K=1024: batch keeps 0.986 of seq true gain (need >=0.80); bits 96 vs 1024
- H8 early patch/seq: median overstatement / ledger radius = 0.121 (need >=0.10: the bound is not vacuous)
- H9 pool/seq median overstatement / ledger radius: early -0.006, late 0.066 (need both <=0.10: natural proposers use little of the budget)

## Verdicts
- **H1: PASS**
- **H2: PASS**
- **H3: PASS**
- **H4: PASS**
- **H5: PASS**
- **H6: PASS**
- **H7: PASS**
- **H8: PASS**
- **H9: PASS**
