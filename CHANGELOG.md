# Changelog

All notable benchmark-definition changes are documented here.

## [1.0.0] - 2026-10-13

- Prepared f2x50 1.0.0 as the first stable benchmark release, with 561 checks selected under an outcome-neutral curation protocol.
- Established direct pinned-source evidence in every repository, with at least five direct probes per repository.
- Converted 46 weaker development-snapshot contracts and added source-grounded cases during curation; the stable contract contains 446 `original-file-plus-driver` checks, 8 text-matched extractions, 73 inline reimplementations, and 34 synthetic fixtures.
- Established direct functional breadth across 131 repository-routine pairs; all 50 repositories execute at least two distinct pinned routines.
- Added a validator-enforced source-information record for every one of the 561 checks.
- Distinguished original-file, text-matched extraction, `f2py`, inline-reimplementation, and synthetic-fixture contracts.
- Added per-repository coverage metrics and explicit source-evidence classifications.
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
- Recorded a revision-specific upstream licence review.
