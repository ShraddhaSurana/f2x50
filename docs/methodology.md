# Benchmark methodology

## Design goal

f2x50 tests migration at repository scale. Unlike task-level translation suites, it exposes build layout, modules, shared state, calling conventions, data handling, and dependencies that appear only when a complete codebase is migrated.

The benchmark fixes three independent objects:

1. a source corpus identified by upstream URL and exact Git revision;
2. a set of behavioral questions selected from that source; and
3. comparison rules that can be applied to any target implementation.

Migration outputs and their scores are not embedded in the dataset.

## Repository tiers

The low, medium, and complex tiers reflect a manual assessment of codebase scale, inter-module coupling, and advanced Fortran features. Size contributes to the assignment but does not determine it, so the ranges overlap. Tier labels should be used for stratified reporting, not interpreted as an interval-valued universal complexity measure.

## Immutable acquisition

Each corpus entry is pinned by a full Git SHA. `clone_corpus.sh` reads the repository manifest, initializes each repository, fetches that object, and checks out `FETCH_HEAD` in detached state. Omitting `--repo` acquires all 50 entries; `--verify-only` checks an existing acquisition, while `--check-metrics` also recomputes the standardized source count.

The benchmark does not use shallow clones of moving default branches. It also does not vendor upstream source, preserving links to the original repositories and avoiding incompatible third-party licences in this repository.

## Source measurement

Counts use only paths returned by `git ls-files` at the pinned revision. Suffix matching is case-insensitive over `.f`, `.for`, `.f90`, `.f95`, `.f03`, and `.f08`. Physical lines include code, comments, and blanks. Generated wrappers and build artifacts that are not tracked upstream are excluded.

## Probe curation

Probe candidates are deterministic behaviours that can be called on small, self-contained inputs. The version 0.1 development snapshot was assembled during a migration study and includes both upstream-linked behaviours and disclosed adapter-oriented fixtures; it is not claimed to be a fully blind test-design exercise. Version 1.0.0 establishes its source-provenance contract without consulting migration pass/fail outcomes. Future additions must follow the same rule, which avoids choosing tests that flatter a particular method.

The source-side contract is obtained in one of five explicitly recorded ways:

- compile an original source routine with a small driver;
- compile a text-matched extraction of a pinned routine;
- expose a selected routine through a NumPy `f2py` wrapper (the category is supported, but version 1.0.0 has no remaining cases in it);
- compile an inline reimplementation of a selected behavior; or
- compile/use a synthetic fixture for an adapter or representation contract.

The repository contains source for the small Fortran wrappers; compiled extension modules are deliberately excluded. `manifests/source_information.csv` gives the source category for every check and the exact upstream and harness locations where an upstream routine is claimed. The reference harness compiles temporary programs at run time with `gfortran` and applies the same fixed input to the source-side contract and target implementation. Inline reimplementations and synthetic fixtures are useful regression contracts but are weaker evidence than executing the pinned upstream routine and are reported separately.

## Comparison policy

For numeric values, arrays must have identical shapes and each element must satisfy

```text
abs(target - source) <= atol + rtol * abs(source)
```

The executable definition stores the probe-specific input and tolerance. The policy uses `1e-14` for closed-form functions, `1e-12` for BLAS kernels, `1e-10` or `1e-8` for composite routines and table lookups, and `1e-6` for iterative solvers. Exact modes use zero tolerance. Duration probes normalize units before equality testing.

## Reporting

A planned probe passes only if the target is runnable and agrees with its versioned Fortran-side contract. Missing, unimportable, or uninvokable targets count as unsuccessful cases rather than being omitted:

```text
behavioral agreement = source-agreeing targets / 561 planned probes
```

Researchers may additionally report agreement among runnable cases, but should not substitute it for the result over all planned cases. Results should also be decomposed by repository and tier because corpus-level averages can hide concentration of failures.
