# Direct-source expansion audit

## Outcome

The expansion followed the rule declared before inspecting migration outcomes: prefer conversions of existing probes, work in manifest/source order, balance the low, medium, and complex tiers, and add a case only when both a pinned upstream behavior and the archived target behavior are callable. The version 0.2 release candidate contains:

| Source evidence | Probes |
|---|---:|
| Original file plus driver | 444 |
| Text-matched extraction | 8 |
| Inline reimplementation | 73 |
| Synthetic fixture | 34 |
| **Total** | **559** |

Direct-source coverage increased from 75 probes in 12 repositories in the 382-probe development snapshot to 444 probes in all 50 repositories. Every repository has at least five direct probes. The final direct set covers 130 repository-routine pairs; 49 repositories execute at least two distinct pinned routines. Relative to the earlier 412-probe candidate, 147 cases were added and 46 existing weaker contracts were upgraded, raising the direct category from 251 to 444. No `f2py` category remains: former wrapper cases compile the corresponding pinned files with standalone drivers.

The full archived-target replay preserved all 559 cases in the denominator, including repository-level import or invocation errors. It reported 434 agreements, 74 behavioral mismatches, and 51 explicit errors; 26 of 50 repositories passed every check. The 54-case distinct-function expansion contributed 40 agreements, 12 mismatches, and two explicit target-side errors. These figures diagnose the archived target and are not a claim of whole-repository equivalence.

## Distinct-function expansion

After the five-probe minimum was reached, a third outcome-neutral rule targeted functional concentration. At the 505-probe checkpoint, 390 direct checks covered only 103 repository-routine pairs and 27 repositories obtained all direct evidence from one pinned routine. One new deterministic routine and two whole-execution cases were predeclared for each repository before target execution. `Cmathtuts` had no defensible second source/target match: its only matching routine, `matrix_multiply`, was already covered, while the remaining deterministic examples had no generated counterpart and `ranvec` was nondeterministic. Two forward-declared `wavelets:CFFTB` cases replaced that infeasible pair without manufacturing a correspondence.

The phase added 54 direct cases and 27 routine pairs, yielding 559 probes, 444 direct cases, and 130 repository-routine pairs. Twenty-six of the 27 one-routine repositories gained a second routine; `Cmathtuts` is the sole documented exception. Array outputs remained one probe per execution, so the increase reflects new inputs to new functions rather than per-element inflation. The complete frozen routine/input ledger and feasibility decision are in `direct-source-expansion-plan.md`.

The replay retained every newly exposed disagreement. Fourteen new cases were non-passing across 11 repositories: 12 behavioral mismatches and two target-side broadcasting errors in Packmol. Other findings include false-branch handling in test-drive, unsupported schemes in FOODIE, zero-Ritz convergence in ARPACK, unknown-element behavior in Atomsk, head-layout behavior in neural-fortran, derivative parity in Incompact3d, and dynamic-relaxation state in MPM3D-F90. None was used to change selection, shapes, or tolerances.

## Five-direct-probe expansion

After the all-repository milestone, a second rule was frozen before any new migration outcome was executed: add exactly enough deterministic boundary, representation, or ordinary cases to bring each repository below five direct probes up to five. This selected 25 repositories and 44 additions. All 44 compile a pinned upstream file through the existing driver; no weaker case was relabelled in this phase.

The added cases include geometric boundaries (`ABAQUS`), scheme spelling and empty inputs (`FOODIE`), public constants (`forpy` and `hdf5`), sort positions and numerical invariants (`stdlib`, `packmol`, `bspline-fortran`, `Cmathtuts`, `dftd4`, and the Astrodynamics Toolkit), time/string extrema (`toml-f`, `M_strings`, `M_time`, and `M_args-main`), parser/serializer cases (`WPS`, `IO-Fortran-Library`, `coretran`, and `atomsk`), additional element symbols (`crest` and `xtb`), and boundary inputs for the remaining numerical routines. The complete IDs, source locators, and comparison rules are in the two manifests.

The target replay retained the newly exposed disagreements: FOODIE rejects uppercase and empty scheme names while the migrated factory accepts them; the generated M_strings target overflows on the minimum 32-bit integer; the B-spline target violates the source-derived partition check for this case; and the generated forpy analyzer omits `EXCEPTION_ERROR`. These outcomes were not used to revise selection or tolerances.

## Final 17-repository expansion

The last phase supplied direct coverage for all repositories that were still uncovered in the 412-probe candidate. The table names the pinned behavior used; full paths and line ranges are recorded per probe in `manifests/source_information.csv`.

| Tier | Repository | Pinned behavior executed | Direct probes after expansion |
|---|---|---|---:|
| Low | `IO-Fortran-Library` | `String%read_file` from `io_fortran_lib_mod.f90` and its pinned submodules | 4 |
| Low | `bspline-fortran` | `db1val` from the pinned B-spline modules | 4 |
| Low | `forpy` | public parameters from `forpy_mod.F90` | 2 |
| Low | `toml-f` | pinned datetime parsing/round-trip routines | 2 |
| Medium | `FOODIE` | Euler integrator `is_supported` | 2 |
| Medium | `Incompact3d` | `derx_00` from `derive.f90` | 5 |
| Medium | `MPM3D-F90` | `InitParticle` from `Particle.f90` | 6 |
| Medium | `WPS` | `despace` from `module_stringutil.F` | 2 |
| Medium | `arpack-ng` | MPI `pdnorm2` from PARPACK | 7 |
| Medium | `atomsk` | `WRITE_XYZ` from `out_xyz.f90` | 4 |
| Medium | `coretran` | `compact` from `m_strings.f90` | 3 |
| Medium | `dftd4` | `get_rational_damping_name` from `param.f90` | 4 |
| Medium | `neural-fortran` | multi-head attention `split_heads` | 8 |
| Medium | `xtb` | `toSymbol` from the pinned symbol modules | 3 |
| Complex | `elmerfem` | `GaussPointsTriangle` from `Integration.F90` | 24 |
| Complex | `fpm` | `fpm_version` from `fpm_release.F90` | 4 |
| Complex | `openfast` | `InterpBinReal` from `NWTC_Num.f90` | 11 |

The additions are not arbitrary source-only smoke tests. Each direct case compares a value computed by the pinned routine with the corresponding archived migration target. Cases whose target behavior does not correspond to a callable upstream routine remain conservatively classified; for example, the 12 older MPM momentum fixtures remain synthetic, the 16 older fpm compiler-default contracts remain inline, and the original Elmer nearest-neighbour fixtures remain weak.

## Dependency-stub boundary

Some large applications cannot expose a small routine without module dependencies. Minimal stubs were therefore used only to provide kinds, constants, or interfaces that the selected routine requires but does not exercise. They do not implement the behavior under comparison. Notable cases are Atomsk (`comv`/atom interfaces), OpenFAST (`NWTC_IO` interface), fpm (version/error interfaces), Incompact3d (parameter/IBM declarations), FOODIE (`penf` kinds), and ElmerFEM (`LoadMod` and `PElementMaps`). The upstream procedure body itself is compiled from the exact pinned file in every direct case.

## Outcome-neutral failures retained

Stronger oracles intentionally exposed disagreements that weaker mirrors had hidden. Examples include CaNS flow profiles, unnormalized FFTPACK inverse transforms, `fortranlib` file/directory predicates, ccpp formatting, the crest unknown-element case, FOODIE's invalid-scheme case, and four neural-fortran head-order values. These failures were retained rather than normalized away. The selection and tolerance rules were not changed after seeing target results.

## Enforced invariants

`scripts/validate.py` and `tests/test_manifests.py` enforce the 559-row join, the exact four-category totals, all 50 directly covered repositories, at least five direct probes per repository, 130 repository-routine pairs, and 49 repositories with at least two distinct direct routines. The reference runner refuses to emit a report whose result count differs from the fixed 559-probe manifest. All 559 source-information rows are marked verified and contain upstream locators whenever direct or extracted source is claimed.

The audit therefore addresses repository breadth, functional breadth, and oracle provenance. It does not claim that 559 targeted contracts validate all 6.57 million physical lines; that limitation remains explicit in the dataset card and coverage audit.
