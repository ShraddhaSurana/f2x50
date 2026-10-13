# Behavioral-coverage analysis

This report quantifies the released behavioral contract; it does not claim statement, branch, or semantic coverage of the upstream repositories.

## Release-level summary

- 561 probes across 50 repositories (11.22 probes per repository).
- 0.085391 probes per thousand physical Fortran lines corpus-wide.
- Per-repository density ranges from 0.007505 to 16.574586 probes per KLOC; size therefore makes raw line-normalized density highly uneven.

| Source evidence | Probes | Share |
|---|---:|---:|
| `original-file-plus-driver` | 446 | 79.5% |
| `f2py-wrapper` | 0 | 0.0% |
| `extracted-source` | 8 | 1.4% |
| `inline-reimplementation` | 73 | 13.0% |
| `synthetic-fixture` | 34 | 6.1% |

## Interpretation

The fixed contract guarantees breadth across all 50 repositories and preserves every planned case in the denominator. It is targeted regression evidence, not a proof of repository equivalence. Original-file-plus-driver probes provide the strongest direct source connection; version 1.0.0 has no remaining f2py-wrapper cases. Inline reimplementations and synthetic fixtures are disclosed separately because compiling a small Fortran program is not by itself evidence that the pinned upstream implementation was executed.

`manifests/coverage_by_repository.csv` supports tier/repository decompositions. The figures are descriptive summaries of the published manifests.

## Recommended future-coverage rule

Future versions should prioritize public routines not yet represented, boundary/error cases, and probes that replace inline reimplementations with execution of the pinned source. Additions must be selected without inspecting a migration method's pass/fail outcomes and must increment the benchmark version.
