# Independent measurement-validity checks

Read `VALIDITY_REVIEW_zh.md`. This is a synthetic validity investigation, not an upstream repository reproduction or a GT reassessment.

## Files

- `independent_checks.py`: eight new synthetic check groups and twelve passing assertions
- `independent_results.json`: numeric output and provenance
- `reference/quality_core.py`: byte-identical copy of the returned package's core, SHA-256 be5d213c690db111f2eb0174a36b81c3fc7001312491c58b4b4b5c91232569dd
- `run_output.json`: saved execution stdout

## Run

With NumPy, SciPy and Shapely installed:

```sh
PYTHONDONTWRITEBYTECODE=1 python independent_checks.py
```

In the reviewed container:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/scratch/a365811da80c/audit-oct1-deps python independent_checks.py
```

The script imports only the local reference copy, prevents bytecode generation, and writes its JSON results to this directory. It does not access photos or alter any input, GT, source repository, or original returned package.

The exact-nearest-tie example uses valid analytic 3D Geometry directly to expose a positive-length correspondence ambiguity. Its separate ERP-roundtrip result is also saved and does not exhibit the same cyclic discrepancy, due to floating-point perturbations breaking the exact tie. Do not conflate them or claim a real-data ranking reversal.
