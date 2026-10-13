# Behavioral-coverage audit

This report quantifies the released behavioral contract; it does not claim statement, branch, or semantic coverage of the upstream repositories.

## Release-level summary

- 382 probes across 50 repositories (7.64 probes per repository).
- 0.058145 probes per thousand physical Fortran lines corpus-wide.
- Per-repository density ranges from 0.007451 to 8.823529 probes per KLOC; size therefore makes raw line-normalized density highly uneven.

| Source evidence | Probes | Share |
|---|---:|---:|
| `original-file-plus-driver` | 75 | 19.6% |
| `f2py-wrapper` | 24 | 6.3% |
| `extracted-source` | 16 | 4.2% |
| `inline-reimplementation` | 207 | 54.2% |
| `synthetic-fixture` | 60 | 15.7% |

## Interpretation

The fixed contract guarantees breadth across all 50 repositories and preserves every planned case in the denominator. It is targeted regression evidence, not a proof of repository equivalence. Original-file and f2py probes provide the strongest direct source connection. Inline reimplementations and synthetic fixtures are disclosed separately because compiling a small Fortran program is not by itself evidence that the pinned upstream implementation was executed.

`manifests/coverage_by_repository.csv` supports tier/repository decompositions. `manifests/independent_audit_sample.csv` deterministically selects one probe per repository using SHA-256 over the stable probe ID. It is retained as an optional checklist for a future external review and is not used as evidence in version 0.1. No independent validation is claimed.

## Recommended expansion rule

Future versions should prioritize public routines not yet represented, boundary/error cases, and probes that replace inline reimplementations with execution of the pinned source. Additions must be selected without inspecting a migration method's pass/fail outcomes and must increment the benchmark version.
