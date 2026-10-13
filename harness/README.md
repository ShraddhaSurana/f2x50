# Reference behavioral harness

This directory contains the Python evaluation adapter for the f2x50 checks. It uses a compiled Fortran-side contract and invokes a Python implementation on the same input. The checks include original pinned files, `f2py` wrappers, inline reimplementations, and synthetic fixtures; consult `manifests/source_information.csv` before interpreting a result as direct execution of upstream source.

`python/run_corpus_verification.py` defines the original verifier set and common comparator. `python/extended_repo_verifiers.py` completes the 50-repository coverage. Inventory and automated-probe modules document candidate discovery and reusable resolution logic.

`fortran_stubs/` contains source-only wrappers for selected BLAS, MINPACK, and tsunami behaviors. Build them locally with:

```bash
./harness/build_fortran_stubs.sh
```

The build requires `gfortran`, NumPy with `f2py`, Meson, and Ninja. Compiled extensions and compiler module files are ignored and must not be committed.

Set `F2X_TARGET_ROOT` to the root containing the Python implementations to evaluate. See `docs/probes.md` for the adapter contract and guidance for other target languages.
