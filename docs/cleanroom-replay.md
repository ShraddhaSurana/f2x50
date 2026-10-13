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

1. validated all manifests and their 382 matching source-information records in the version 0.1 development snapshot;
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

The `Dockerfile` provides the Linux counterpart. It installs only Git, GNU Fortran, certificates, Python, and the three pinned Python packages before running the same smoke script. That script uses `clone_corpus.sh` to acquire the exact `roots-fortran` pin. The Linux container replay is recorded in the final section below.

## Five-direct-probe curation checkpoint — 2026-09-20

After the five-direct-probe curation stage, the standard validator passed with 50 repositories, 505 probes, and 505 source-information rows. The full reference adapter also reported every planned case when target imports or calls failed: it recorded 394 agreements, 62 behavioral mismatches, and 49 explicit errors across 505 planned checks and exactly 50 repositories. Thirty-four repositories passed every check. The 44 selected cases contributed 39 agreements, four mismatches, and one explicit target-side error. This is a harness-integrity replay against the archived migration targets, not a new benchmark result for the paper. The existing clean-room `roots-fortran` checkout was rechecked at the recorded revision with matching file and line counts. The fresh public-clone and Linux-container replays were completed subsequently and are recorded below.

## Distinct-routine curation checkpoint — 2026-09-21

After the outcome-neutral distinct-routine curation stage, the standard validator and manifest tests passed with 50 repositories, 559 probes, and 559 source-information rows. The full reference adapter again retained the entire denominator and reported 434 agreements, 74 behavioral mismatches, and 51 explicit errors. Twenty-six repositories passed every check, 22 contained at least one mismatch, and two produced repository-level errors. The 54 selected cases contributed 40 agreements, 12 mismatches, and two target-side errors. This local replay checked harness accounting and the archived target adapter; the later Linux-container and fresh public-clone checks are recorded below.

## Version 1.0.0 contract revalidation — 2026-09-22

Two predeclared whole-execution cases compile the pinned `Cmathtuts:pythagoras` routine and compare its Euclidean norm with the archived generated target's returned `l2_norm` metric. Both the ordinary `(3,4)` and signed `(-5,12)` cases agreed with zero observed difference. The standard validator and manifest tests passed with 50 repositories, 561 probes, 561 source-information rows, 446 direct cases, 131 repository-routine pairs, and at least two distinct pinned routines in every repository. A complete replay against the same reconciled archived target retained all 561 outcomes and reported 436 agreements, 74 behavioral mismatches, and 51 explicit errors; the two added cases account exactly for the increase from the previous replay. This local replay checked harness accounting; the Linux counterpart was then completed as recorded below.

## Linux container run — 2026-09-23

The release image was built from the checked-in `Dockerfile` on a Linux host and run without a pre-existing corpus directory:

```bash
docker build --pull --no-cache -t f2x50-linux-smoke:latest .
docker run --rm f2x50-linux-smoke:latest
```

The image used the `python:3.13-slim-bookworm` base, installed GNU Fortran and Git through Debian, installed the exact NumPy, Meson, and Ninja versions in `requirements-harness.txt`, and then invoked `scripts/cleanroom_smoke.sh`. The container acquired the public `roots-fortran` pin, matched its recorded file and line counts, compiled all seven legacy wrapper sources, and completed the tutorial comparison with exit status zero and `"passed": true`.

This completes the release's Linux clean-room smoke replay. It demonstrates one published source-to-target check in an isolated Linux environment; it is not a claim that every original repository builds or that an evaluated target passes all 561 checks. Complete adapter replays must separately retain all 561 outcomes as described in [`running.md`](running.md#run-and-verify-all-561-checks).
