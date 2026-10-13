# Behavioral-coverage audit

This report quantifies the released behavioral contract; it does not claim statement, branch, or semantic coverage of the upstream repositories.

## Release-level summary

- 559 probes across 50 repositories (11.18 probes per repository).
- 0.085086 probes per thousand physical Fortran lines corpus-wide.
- Per-repository density ranges from 0.007505 to 16.574586 probes per KLOC; size therefore makes raw line-normalized density highly uneven.

| Source evidence | Probes | Share |
|---|---:|---:|
| `original-file-plus-driver` | 444 | 79.4% |
| `f2py-wrapper` | 0 | 0.0% |
| `extracted-source` | 8 | 1.4% |
| `inline-reimplementation` | 73 | 13.1% |
| `synthetic-fixture` | 34 | 6.1% |

## Interpretation

The fixed contract guarantees breadth across all 50 repositories and preserves every planned case in the denominator. It is targeted regression evidence, not a proof of repository equivalence. Original-file-plus-driver probes provide the strongest direct source connection; version 0.2 has no remaining f2py-wrapper cases. Inline reimplementations and synthetic fixtures are disclosed separately because compiling a small Fortran program is not by itself evidence that the pinned upstream implementation was executed.

`manifests/coverage_by_repository.csv` supports tier/repository decompositions. `manifests/independent_audit_sample.csv` deterministically selects one probe per repository using SHA-256 over the stable probe ID. A person who did not author the corresponding verifier should check the source locator, input, expected behavior, and comparison rule and fill the three review columns. Until then, the sample is explicitly marked pending and must not be described as independently audited.

## Recommended expansion rule

Future versions should prioritize public routines not yet represented, boundary/error cases, and probes that replace inline reimplementations with execution of the pinned source. Additions must be selected without inspecting a migration method's pass/fail outcomes and must increment the benchmark version.
