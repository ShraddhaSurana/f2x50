# Direct-source provenance

## Outcome

The curation followed the rule declared before inspecting migration outcomes: prefer conversions of existing probes, work in manifest/source order, balance the low, medium, and complex tiers, and add a case only when both a pinned upstream behavior and the archived target behavior are callable. The version 1.0.0 benchmark contains:

| Source evidence | Probes |
|---|---:|
| Original file plus driver | 446 |
| Text-matched extraction | 8 |
| Inline reimplementation | 73 |
| Synthetic fixture | 34 |
| **Total** | **561** |

The version 1.0.0 contract contains 446 direct probes across all 50 repositories. Every repository has at least five direct probes and executes at least two distinct pinned routines, spanning 131 repository-routine pairs. The curation converted weaker development-snapshot contracts only when pinned-source execution was established. No `f2py` category remains: former wrapper cases compile the corresponding pinned files with standalone drivers.

The full archived-target replay preserved all 561 cases in the denominator, including repository-level import or invocation errors. It reported 436 agreements, 74 behavioral mismatches, and 51 explicit errors; 26 of 50 repositories passed every check. The 54-case distinct-routine curation stage contributed 40 agreements, 12 mismatches, and two explicit target-side errors; the two-case Cmathtuts closure contributed two agreements. These figures diagnose the archived target and are not a claim of whole-repository equivalence.

## Distinct-routine curation

After the five-probe minimum was reached, a third outcome-neutral rule targeted functional concentration. At the 505-probe checkpoint, 390 direct checks covered only 103 repository-routine pairs and 27 repositories obtained all direct evidence from one pinned routine. One new deterministic routine and two whole-execution cases were predeclared for each repository before target execution. The initial source/API pass recorded `Cmathtuts` as infeasible and added two supplemental `wavelets:CFFTB` cases rather than manufacturing a correspondence.

The initial phase selected 54 direct cases and 27 routine pairs, yielding 559 probes, 444 direct cases, and 130 repository-routine pairs. A later source-level review identified a defensible mapping from pinned `Cmathtuts:pythagoras` to the generated target's returned Euclidean `l2_norm` metric. Two whole-execution inputs, `(3,4)` and `(-5,12)`, were recorded before execution and retained after both agreed. The stable result is 561 probes, 446 direct cases, 131 repository-routine pairs, and at least two routines in all 50 repositories. Array outputs remain one probe per execution, so they count as one probe per input rather than per-element inflation. The complete frozen routine/input ledger and the superseded feasibility decision are in `direct-source-curation-protocol.md`.

The replay retained every newly exposed disagreement. Fourteen new cases were non-passing across 11 repositories: 12 behavioral mismatches and two target-side broadcasting errors in Packmol. Other findings include false-branch handling in test-drive, unsupported schemes in FOODIE, zero-Ritz convergence in ARPACK, unknown-element behavior in Atomsk, head-layout behavior in neural-fortran, derivative parity in Incompact3d, and dynamic-relaxation state in MPM3D-F90. None was used to change selection, shapes, or tolerances.

## Five-direct-probe curation

After the all-repository milestone, a second rule was frozen before any new migration outcome was executed: add exactly enough deterministic boundary, representation, or ordinary cases to bring each repository below five direct probes up to five. This selected 25 repositories and 44 additions. All 44 compile a pinned upstream file through the existing driver; no weaker case was relabelled in this phase.

The added cases include geometric boundaries (`ABAQUS`), scheme spelling and empty inputs (`FOODIE`), public constants (`forpy` and `hdf5`), sort positions and numerical invariants (`stdlib`, `packmol`, `bspline-fortran`, `Cmathtuts`, `dftd4`, and the Astrodynamics Toolkit), time/string extrema (`toml-f`, `M_strings`, `M_time`, and `M_args-main`), parser/serializer cases (`WPS`, `IO-Fortran-Library`, `coretran`, and `atomsk`), additional element symbols (`crest` and `xtb`), and boundary inputs for the remaining numerical routines. The complete IDs, source locators, and comparison rules are in the two manifests.

The target replay retained the newly exposed disagreements: FOODIE rejects uppercase and empty scheme names while the migrated factory accepts them; the generated M_strings target overflows on the minimum 32-bit integer; the B-spline target violates the source-derived partition check for this case; and the generated forpy analyzer omits `EXCEPTION_ERROR`. These outcomes were not used to revise selection or tolerances.

## Final 17-repository curation stage

This curation stage supplied direct coverage for all repositories that were still uncovered at the 412-probe checkpoint. The table names the pinned behavior used; full paths and line ranges are recorded per probe in `manifests/source_information.csv`.

| Tier | Repository | Pinned behavior executed | Direct probes after curation |
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

`scripts/validate.py` and `tests/test_manifests.py` enforce the 561-row join, the exact four-category totals, all 50 directly covered repositories, at least five direct probes per repository, 131 repository-routine pairs, and all 50 repositories with at least two distinct direct routines. The reference runner refuses to emit a report whose result count differs from the fixed 561-probe manifest. All 561 source-information rows contain a provenance note and include upstream locators whenever direct or extracted source is claimed.

This documentation therefore records repository breadth, functional breadth, and oracle provenance. It does not claim that 561 targeted contracts validate all 6.57 million physical lines; that limitation remains explicit in the dataset card and coverage analysis.
