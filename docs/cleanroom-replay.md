# Clean-room replay record

## macOS ARM64 run — 2026-09-19

The release smoke test was executed from a newly created virtual environment and a newly acquired corpus directory. No packages from the invoking Python installation were visible inside the environment.

| Component | Recorded value |
|---|---|
| Operating system | macOS 26.7 (build 25G229), ARM64 |
| Python | CPython 3.13.0 |
| Git | 2.50.1 |
| Fortran compiler | GNU Fortran 15.2.0 (Homebrew GCC 15.2.0_1) |
| NumPy | 2.5.3 |
| Meson | 1.12.0 |
| Ninja | 1.13.2 |

The replay performed these checks in order:

1. validated all manifests and their 382 matching source-information records;
2. acquired `roots-fortran` at `fb17ecdccb5a966ae8238900c87a869b80ae1cdf` into an empty directory;
3. recomputed and matched its 4 tracked Fortran files and 5,231 physical lines;
4. compiled all seven checked-in `f2py` wrapper sources;
5. compiled the pinned `roots-fortran/src/root_module.F90` with the tutorial driver; and
6. compared its bisection result with the standalone Python tutorial adapter.

The final comparison passed for `f2x50-low-roots-fortran-001`: the absolute root difference was `3.818313416559249e-07` against an absolute tolerance of `1e-06`, and both implementations returned success status zero. This is a reference result for one published check and demonstrates the evaluation path without claiming a full repository migration.

Re-run the same sequence with:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-harness.txt
bash scripts/cleanroom_smoke.sh /tmp/f2x50-corpus
```

The `Dockerfile` provides the Linux counterpart. It installs only Git, GNU Fortran, certificates, Python, and the three pinned Python packages before running the same smoke script. That script uses `clone_corpus.sh` to acquire the exact `roots-fortran` pin. A Docker run should be recorded here after the paper and release candidate are finalized; the macOS result above is already complete.
