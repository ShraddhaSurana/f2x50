# Changelog

All notable benchmark-definition changes are documented here.

## [Unreleased]

- Targeted the strengthened 0.2.0 release candidate.
- Expanded the benchmark from 382 to 559 checks, including outcome-neutral direct-source expansions that cover every repository with at least five pinned-source probes.
- Upgraded 46 existing weaker checks and added 147 cases relative to the 412-probe intermediate candidate.
- Increased `original-file-plus-driver` evidence from 75 to 444 checks; the remaining evidence is 8 text-matched extractions, 73 inline reimplementations, and 34 synthetic fixtures.
- Expanded direct functional breadth from 103 to 130 repository-routine pairs; 49 of 50 repositories now execute at least two distinct pinned routines, with a documented source/target feasibility exclusion for `Cmathtuts`.
- Added a validator-enforced source-information record for every one of the 559 checks.
- Distinguished original-file, text-matched extraction, `f2py`, inline-reimplementation, and synthetic-fixture contracts.
- Added per-repository coverage metrics and an optional deterministic 50-probe review sample; version 0.2 makes no claim of independent validation.
- Added pinned harness dependencies, a Dockerfile, environment capture, and a clean-room smoke test.
- Made the end-to-end `roots-fortran` example execute published check `f2x50-low-roots-fortran-001`.
- Updated all seven `roots-fortran` checks to compile the pinned upstream source with small drivers.
- Replaced method-specific Python-target paths and environment names with the generic `F2X_TARGET_ROOT` interface.
- Replaced the Python acquisition entry point with a manifest-driven `clone_corpus.sh` that fetches and verifies exact revisions.
- Corrected the QUADPACK verifier's repository identifier to match the manifest.

## [0.1.0] - 2026-09-02

- Created the standalone f2x50 repository.
- Pinned 50 upstream repositories with Git-tracked file and physical-line counts.
- Published the target-independent catalogue of 382 versioned behavioural contracts.
- Added the Python-target reference harness and Fortran wrapper sources.
- Added deterministic acquisition, validation, summaries, and reproducible figures.
- Recorded a revision-specific upstream licence audit.
