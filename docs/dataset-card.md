# Dataset card

## Summary

f2x50 is a curated, repository-scale benchmark for Fortran-to-X software migration. Version 0.2 fixes 50 public repositories at immutable Git revisions and associates them with 559 deterministic behavioral contracts. The corpus spans scientific libraries, numerical methods, simulation codes, infrastructure, build tooling, and language utilities.

The name uses **X** intentionally. Fortran is the fixed source language; the target may be any language or platform for which an adapter can invoke the translated behavior and submit values to the same comparison rules. The bundled adapter targets Python.

## Composition

| Tier | Repositories | File range | Physical-line range | Probes |
|---|---:|---:|---:|---:|
| Low | 20 | 3–112 | 1,448–40,841 | 203 |
| Medium | 20 | 4–405 | 4,385–191,946 | 199 |
| Complex | 10 | 158–3,600 | 28,956–1,571,444 | 157 |

The totals are 12,116 Git-tracked Fortran files, 6,569,806 physical lines, and 559 probes. Adjacent tiers overlap in size because stratification also considered inter-module coupling and use of advanced Fortran features.

Repositories cover root finding, numerical integration, linear algebra, fluid dynamics, atmospheric modelling, finite elements, molecular and quantum chemistry, probabilistic programming, scientific data storage, package management, parsers, utilities, and machine learning. This breadth is intentional but is not a probability sample of all public Fortran software.

## Selection and repository origins

Candidate repositories were screened for public accessibility, at least 1,000 Fortran lines, practical compilation with a standard Fortran toolchain, and absence—at the time of selection—of a known public Python translation that could serve as a memorised target. The final set was manually stratified into 20 low-, 20 medium-, and 10 complex-tier projects.

Every record gives the original repository's HTTPS URL and a full 40-character Git commit. Default branches are not part of the benchmark identity. Acquisition checks out the recorded revision in detached-HEAD state.

The licence audit is revision-specific. Forty-seven records have an unambiguous project-level expression. `Cmathtuts` carries a root GPL-3.0 text, but its README says that individual examples may have their own licences, so the aggregate is marked `NOASSERTION`. `ABAQUS` and `MPM3D-F90` remain in the benchmark to preserve the published composition, but no explicit licence was found at the pinned revisions. Presence in a public Git repository does not itself grant redistribution rights.

## Measurement policy

File and line counts are recomputed from the clean Git tree at the pinned commit. A Fortran source file is a Git-tracked path whose suffix, compared case-insensitively, is one of `.f`, `.for`, `.f90`, `.f95`, `.f03`, or `.f08`. A line is a physical line, including blank and comment lines.

This policy intentionally excludes generated files, ignored build products, untracked behavioral-test directories, and working-tree contamination. It is simple and reproducible, but it is not a measure of logical source statements.

## Behavioral labels

The 559 cases are planned behavioral contracts rather than pass/fail labels from a migration run. Candidate public behaviours were curated from the Fortran repositories; the completed set also contains explicitly marked adapter-oriented reimplementations and synthetic fixtures. Probe inputs and source-side programs are defined in the executable harness, and the source-information manifest keeps these categories distinct. The catalogue contains:

- 278 numeric-tolerance comparisons;
- 158 exact array comparisons;
- 80 exact scalar or string comparisons;
- 33 exact Boolean-array comparisons;
- 5 exact Boolean comparisons; and
- 5 duration comparisons after unit normalization.

The distinction between a planned probe, a runnable target, and a passing result is essential. f2x50 publishes the planned probes. A study must report non-runnable targets in the denominator rather than silently dropping them.

## Intended uses

- Evaluate full-repository migration systems under a fixed source corpus.
- Compare target languages or translation strategies using identical versioned contracts, while reporting source-evidence categories separately.
- Study how repository scale, dependency structure, and Fortran features affect migration.
- Test build recovery, target resolution, and preservation of observable behavior.

## Prior public use

An earlier 382-probe development snapshot was used across all 50 pins in the public preprint *Identifying Latent Declarative Representations of Code for Assisting Repository Migration* (arXiv:2608.23619). Because its authors overlap with the benchmark authors, this demonstrates a concrete research use but is not evidence of independent external adoption. Results from that snapshot retain their 382-case denominator and must not be compared as if they used version 0.2's 559 cases.

## Out-of-scope uses

- Treating probe agreement as a proof of semantic equivalence for all inputs.
- Training on the benchmark and then reporting the same release as an unseen test set.
- Inferring quality trends for all Fortran projects from this purposive sample.
- Redistributing an original repository without checking its recorded licence and current legal context.

## Limitations and risks

The probes are targeted rather than exhaustive. The source-information manifest classifies 444 as original-file-plus-driver, 8 as text-matched extractions, 73 as inline reimplementations, and 34 as synthetic fixtures. The latter two categories are regression contracts, not direct evidence that code from the pinned original repository was executed. Direct execution covers all 50 repositories with at least five checks each and 130 distinct repository-routine pairs; 49 repositories execute at least two distinct pinned routines. `Cmathtuts` has one direct routine because no second deterministic pinned routine corresponds to callable target behavior. Relative to the 382-probe development snapshot, the release has 369 more direct-source checks and 177 more checks overall. Repository tiers are expert judgements, not a learned or universally calibrated complexity scale. The 559 contracts remain sparse relative to 6.57 million physical lines and are targeted behavioral evidence, not a proof of repository equivalence. GitHub availability can change, submodules and large assets may require additional acquisition, and compilers may expose portability defects in old code.

The included target adapter contains repository-specific resolution logic. Such adaptation is unavoidable when APIs change during migration, but studies should disclose any new mappings and apply them consistently across compared methods.

## Versioning and maintenance

Version 0.2 is the strengthened pre-publication release candidate assembled after the 382-probe version 0.1 development snapshot. Published benchmark releases should be immutable. Corrections to metadata or harness defects should increment the version and be recorded in `CHANGELOG.md`; replacing a recorded repository commit or changing a probe constitutes a new benchmark release.
