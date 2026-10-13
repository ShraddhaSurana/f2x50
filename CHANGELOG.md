# Changelog

All notable benchmark-definition changes are documented here.

## [Unreleased]

- Added a validator-enforced source-information record for every one of the 382 checks.
- Distinguished original-file, text-matched extraction, `f2py`, inline-reimplementation, and synthetic-fixture contracts.
- Added per-repository coverage metrics and an optional deterministic 50-probe review sample; version 0.1 makes no claim of independent validation.
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
