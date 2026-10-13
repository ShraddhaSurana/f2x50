# Direct-source expansion plan for the version 0.2 release candidate

Implementation status: complete. The audit is recorded in [`direct-source-expansion-audit.md`](direct-source-expansion-audit.md). All 50 repositories have at least five direct checks, the 559-probe manifest contains 444 direct checks spanning 130 repository-routine pairs, and 49 repositories execute at least two distinct pinned routines. `Cmathtuts` is the sole documented source/target feasibility exclusion.

Status: predeclared before implementation and before inspecting any migration-target outcomes
Public comparison baseline: `ea69976` (382-probe version 0.1 release candidate)
Declared: 2026-09-20

## Objective

The current version 0.2 release candidate has 134 `original-file-plus-driver` probes, but they are concentrated in 12 of the 50 repositories. This expansion targets the 38 repositories without that evidence. Each must receive at least two checks whose expected values are produced by executing an exact file from the pinned upstream revision with a small driver.

The target is 76 additional or converted direct-source checks: 24 in low-tier repositories, 36 in medium-tier repositories, and 16 in complex-tier repositories. Probe quantity is secondary to repository coverage. Existing weak checks are converted where a verified upstream procedure match already exists; new checks are added only when the current checks are synthetic or have no resolvable upstream procedure.

## Outcome-neutral selection protocol

No migration pass/fail result, error magnitude, or target output may be consulted when selecting or implementing these checks.

1. For a repository with verified inline checks that map to an upstream procedure, select the first two eligible probe IDs in manifest order.
2. An eligible conversion must execute the exact pinned upstream file. Other exact pinned files may satisfy dependencies. Minimal interface or constant stubs are permitted only for dependencies not exercised by the selected procedure; the value under comparison must be computed by the selected upstream procedure body.
3. For a repository without two eligible conversions, inspect Git-tracked Fortran files in lexicographic path order and procedures in source order. Select the first deterministic public procedure that:
   - accepts a small scalar, string, or array input;
   - returns or emits a deterministic value without network access, interactive input, or nondeterministic parallel state; and
   - can be compiled with a small driver on the release toolchain.
4. Use two fixed cases for that procedure, preferably one ordinary and one boundary/sign/empty case. Prefer a second distinct procedure when it is available without pulling in a substantially larger dependency closure.
5. If a candidate cannot be compiled because of an unavailable external dependency or requires application-scale state, record the path, symbol, and reason in the implementation audit, then advance to the next candidate. This feasibility decision must not use target behavior.
6. Convert an existing weak probe instead of adding a probe whenever the observable behavior is the same. New probe IDs are permitted only when no current case represents the selected upstream behavior.
7. Tolerances must follow the precision of the pinned routine and must be justified from source kinds or measured compiler-level rounding, never widened in response to a migration target.
8. Regenerate source information from the exact 50-repository corpus. The validator must enforce both the final category totals and at least two `original-file-plus-driver` probes per repository.

## Frozen conversion set

The following 32 existing probes are selected for conversion.

| Tier | Repository | Existing probes selected |
|---|---|---|
| Low | ABAQUS | `f2x50-low-abaqus-001`, `f2x50-low-abaqus-002` |
| Low | CaNS | `f2x50-low-cans-001`, `f2x50-low-cans-002` |
| Medium | Fortran-Astrodynamics-Toolkit | `f2x50-medium-fortran-astrodynamics-toolkit-001`, `f2x50-medium-fortran-astrodynamics-toolkit-002` |
| Low | M_args-main | `f2x50-low-m-args-main-001`, `f2x50-low-m-args-main-002` |
| Low | M_time | `f2x50-low-m-time-001`, `f2x50-low-m-time-002` |
| Medium | SISSO | `f2x50-medium-sisso-001`, `f2x50-medium-sisso-002` |
| Complex | ccpp-physics | `f2x50-complex-ccpp-physics-001`, `f2x50-complex-ccpp-physics-002` |
| Complex | cp2k | `f2x50-complex-cp2k-001`, `f2x50-complex-cp2k-002` |
| Medium | crest | `f2x50-medium-crest-001`, `f2x50-medium-crest-002` |
| Complex | elmerfem | `f2x50-complex-elmerfem-001`, `f2x50-complex-elmerfem-002` |
| Low | fortran-utils | `f2x50-low-fortran-utils-001`, `f2x50-low-fortran-utils-002` |
| Complex | fpm | `f2x50-complex-fpm-001`, `f2x50-complex-fpm-002` |
| Medium | json-fortran | `f2x50-medium-json-fortran-001`, `f2x50-medium-json-fortran-002` |
| Low | test-drive | `f2x50-low-test-drive-001`, `f2x50-low-test-drive-002` |
| Low | toml-f | `f2x50-low-toml-f-007`, `f2x50-low-toml-f-008` |
| Low | tsunami | `f2x50-low-tsunami-003`, `f2x50-low-tsunami-004` |

## Repositories requiring new direct-source cases

Two cases will be selected by the source-order protocol above for each repository below. These 44 cases are additions unless an exact current behavior can be converted during source inspection.

| Tier | Repositories |
|---|---|
| Low | IO-Fortran-Library; bspline-fortran; forpy; fortranlib |
| Medium | Cmathtuts; FOODIE; Incompact3d; MPM3D-F90; WPS; arpack-ng; atomsk; coretran; dftd4; neural-fortran; packmol; stdlib; xtb |
| Complex | hdf5; lapack; minpack; openfast; petsc |

## Completion criteria

- All 50 repositories have at least two original-file-plus-driver probes.
- Every selected upstream path is at the recorded Git revision and is present in `source_information.csv`.
- The complete manifest, source-information audit, unit tests, and standard validator pass.
- All new or converted direct-source programs compile and execute from the exact corpus on the release toolchain.
- Any deviation from the frozen set is recorded with a source-level feasibility reason and no target-result information.

## Recorded implementation outcome

The source-order feasibility pass found callable matches for the 17 repositories that remained uncovered after the first expansion stage. Some exact case counts differ from the provisional two-per-repository target because array-valued routines yield multiple independently registered scalar/element contracts. In particular, ElmerFEM's selected nearest-neighbour fixtures did not correspond to the pinned solver routines; the implementation advanced to `GaussPointsTriangle` in `fem/src/Integration.F90` and registered its deterministic 1-, 3-, and 4-point outputs. Similar callable alternatives are recorded in the audit for the other repositories. These choices were made from source/API feasibility before target outcomes were inspected.

The final manifest adds 49 cases relative to the 412-probe candidate and upgrades 46 existing weaker cases. Validation enforces 461 probes, 346 `original-file-plus-driver` rows, all 50 repositories directly covered, and a minimum of two direct checks per repository.

## Predeclared five-direct-probe expansion

Declared on 2026-09-20 before executing any new target cases. To strengthen routine/input depth without selecting cases from observed migration outcomes, version 0.2 will raise the minimum direct-source allocation from two to five probes per repository. Only the 25 repositories below five direct cases are eligible. For each, add exactly enough deterministic cases to reach five, producing 44 additional cases and a planned denominator of 505.

Case selection uses the already compiled pinned routine. Inputs are chosen from source/API domains in this order: an unrepresented boundary or empty/zero case, an unrepresented sign/case/format variant, then an additional ordinary value. Array-valued routines may register an additional independently compared element. Selection, tolerances, and expected output shapes are frozen before the migrated target is executed. Failures and errors remain in the denominator. No existing weak contract is relabelled by this phase.

The eligible repositories are `ABAQUS`, `FOODIE`, `forpy`, `packmol`, `petsc`, `stdlib`, `toml-f`, `WPS`, `coretran`, `hdf5`, `xtb`, `atomsk`, `bspline-fortran`, `Cmathtuts`, `crest`, `dftd4`, `Fortran-Astrodynamics-Toolkit`, `fortran2018-examples`, `fortranlib`, `fpm`, `IO-Fortran-Library`, `M_args-main`, `M_strings`, `M_time`, and `SISSO`. The first eight receive three cases, the next three receive two, and the remaining fourteen receive one, for 44 additions total.

Implementation outcome: all 44 cases compiled and remained in the fixed denominator. The resulting manifest has 505 probes, including 390 original-file-plus-driver cases; every repository has at least five. The archived-target replay classified the additions as 39 agreements, four behavioral mismatches, and one explicit error.

## Predeclared distinct-function expansion

Declared on 2026-09-21 after the 505-probe source-information audit and before executing any newly selected migration-target case. The audit found that 390 direct checks represented only 103 repository-symbol pairs; 27 repositories still obtained every direct check from one pinned symbol. This phase prioritizes functional breadth rather than increasing the number of observations of an already-covered routine.

For each of those 27 repositories, select one additional deterministic upstream routine. Prefer the first public routine in source order within the already compiled module or dependency closure that has a corresponding callable behavior in the archived target. If none is feasible, inspect pinned files in lexicographic order and procedures in source order. Selection may use names, signatures, and documentation from the target, but not target outputs, pass/fail results, or error magnitudes. Record a source-level feasibility reason before advancing past a candidate.

Each selected routine receives exactly two registered cases: one ordinary case and one boundary, zero, sign, empty, or error-relevant case dictated by its source contract. An array-valued result counts as one probe per input case, not one probe per element. Derived invariants of an already registered execution are ineligible. Existing cases are not relabelled. The minimum planned addition is therefore 54 probes and 27 newly executed upstream routines, producing at least 559 total probes if every repository has a feasible callable match.

The eligible repositories are `ABAQUS`, `atomsk`, `bspline-fortran`, `Cmathtuts`, `coretran`, `crest`, `dftd4`, `FOODIE`, `fortran2018-examples`, `fpm`, `Incompact3d`, `IO-Fortran-Library`, `M_args-main`, `M_strings`, `M_time`, `packmol`, `petsc`, `toml-f`, `WPS`, `xtb`, `MPM3D-F90`, `arpack-ng`, `neural-fortran`, `test-drive`, `wavelets`, `openfast`, and `elmerfem`.

### Frozen routine and input ledger

Entries are added to this ledger before the corresponding migrated Python
function is executed.  `ordinary` and `boundary` identify whole function
executions: an array result remains one registered probe.

| Repository | New pinned routine | Ordinary input | Boundary input | Selection basis |
|---|---|---|---|---|
| fortran2018-examples | `isclose_32` | `1.0_sp, 1.000001_sp, rtol=1e-5_sp` | `0.0_sp, 1e-7_sp, atol=1e-6_sp` | The single-precision overload is the first untested public procedure in the already compiled module and maps to the generated `assert_close` behavior. |
| test-drive | `check_logical` | true expression | false expression | First untested public scalar check in the compiled `testdrive` module; the two inputs exercise its no-error and allocated-error branches. |
| neural-fortran | `combine_heads` | two heads containing `1..8` | two all-zero heads | First callable routine after the covered head split in the same compiled attention module; maps directly to `combine_attention_heads`. |
| petsc | `fillK` | pressure stencil `[-1, 0, 1]` | all-zero pressure stencil | Next routine in the already compiled `App.f90`; maps directly to the generated `fillK` stencil implementation. |
| coretran | `countEntries` | `"alpha   beta gamma"` | single token `"x"` | First scalar query before the covered `compact` routine in the same module; compared with token counts from the generated parser operation. |
| dftd4 | `get_functional_id` | supported key `"pbe"` | unknown key `"not-a-functional"` | Deterministic public lookup in the compiled parameter module; compared with membership in the generated supported-functional API. |
| xtb | `toNumber` | symbol `"Fe"` | lowest supported symbol `"H"` | Reverse conversion adjacent to the covered `toSymbol` routine; compared with atomic numbers produced by the generated XYZ reader. |
| MPM3D-F90 | `dynamicRelaxationDamping` | step 1 with decreasing kinetic energy | step 0 early-return boundary | Next public routine after initialization in the compiled particle module; both control-flow branches are compared with the generated damping function. |
| M_strings | `atoi_int64` via public `aton` generic | `"5000000000"` (outside int32) | `"0"` | Exact generated API match for a distinct pinned int64 parser; cases cover widened range and zero. |
| M_args-main | `longest_command_argument` | arguments `"a", "longest-value"` | no arguments | Exact public generated API match in the compiled module; cases cover iteration and the empty-command-line boundary. |
| M_time | `d2w` | `2024-06-15` | ISO year boundary `2021-01-01` | Public date-to-ISO-week routine in the compiled module; its week result maps to the generated week-of-year callable. |
| FOODIE | `integrator_euler_explicit%initialize` | supported `"euler_explicit"` | unsupported `"bogus"` with non-severe failure | Exact generated initializer counterpart; cases observe initialized descriptions for accepted and rejected schemes. |
| Incompact3d | `derx_11` | five-point ramp with `npaire=1` | same ramp with `npaire=0` | Next x-derivative routine in the already compiled source; the parity/boundary branches are compared with the generated spatial-derivative API. |
| ABAQUS | `UEL` in `UEL_bodyforce.for` | triangular element at nonzero angular speed | zero-time/zero-angular-speed boundary | `UMAT_linear_elastic.for` was rejected before target execution because its hybrid fixed/free layout does not compile unchanged with GNU Fortran; the next source-ordered generated counterpart, the rotational-body-force UEL, compiles exactly. |
| wavelets | `CFFTF` | four complex samples with nonzero real and imaginary parts | one complex sample (`N=1`) | The generated target exposes FFTPACK forward transformation directly; `CFFTF` is a distinct pinned routine from the covered chi-square CDF and the two cases exercise its normal transform and documented early-return boundary. |
| crest | `rdxmol` | three-atom H/C/O XYZ with signed coordinates | one-atom He XYZ at the origin | Public pinned Xmol reader corresponding exactly to the generated `read_xyz_file`; whole atomic-number and coordinate arrays cover normal iteration and the minimum nonempty structure. |
| bspline-fortran | `db1ink_default` through public `db1ink` | four quadratic samples with fixed order-3 knots | three constant samples with fixed order-2 knots | Exact coefficient-construction counterpart to the generated API and a distinct operation from the covered `db1val`; cases exercise nontrivial coefficient solving and the smallest practical linear spline. |
| packmol | `v_in_box` | two 3D positions containing negative and over-box coordinates | one position exactly on the three upper box faces | Elemental pinned periodic-wrap routine maps directly to the generated PBC API; whole arrays exercise modulo wrapping and the exact-boundary-to-zero rule. |
| IO-Fortran-Library | `count_substring_chars` through `String%count` | count `"module"` in a parsed module fixture | count absent `"contains"` in a parsed subroutine fixture | Distinct pinned string-search routine within the already compiled library; compared with occurrences preserved in the generated parser's returned source lines, covering multiple matches and zero matches. |
| arpack-ng | `dsconv` | two nonzero Ritz values with one converged bound | zero Ritz values with exact-zero and small nonzero bounds | Pinned symmetric-Arnoldi convergence test maps to the generated convergence assessment; cases cover ordinary relative testing and the source's machine-epsilon floor at zero. |
| toml-f | `compare_datetime` through `operator(==)` | identical local date-times | same clock fields with local versus UTC zone | Distinct pinned datetime comparator mapped to equality of values returned by the generated datetime conversion; cases cover equality and the allocated-zone distinction. |
| openfast | `Mean` | three varying 3D velocities with equal positive radii | two velocities with all radii zero | Pinned NWTC numeric mean is the aggregation used by the generated disk-averaged-velocity behavior when weights are uniform; whole vectors cover the ordinary equal-weight path and the target's zero-radius fallback. |
| elmerfem | `GaussPoints1D` | two-node length-2 element with varying diffusion and source | unit element with constant diffusion and zero source | Distinct pinned line-quadrature routine used to assemble complete stiffness/force outputs corresponding to the generated 1D Poisson element assembler; cases cover nonuniform fields and the zero-load boundary. |
| atomsk | `ATOMSPECIES` | atomic numbers 1, 6, and 26 | out-of-range atomic number 999 | Pinned atomic-number-to-symbol routine is the exact lookup behavior exercised by the generated XYZ serializer; cases cover common one-/two-letter symbols and the unknown-element fallback. |
| fpm | `new_version_from_string` through public `new_version` | `12.34.56` | leading-zero form `01.002.0003` | Exact pinned version parser corresponding to generated `parse_version_string`; normalized numeric components cover a normal semantic version and integer normalization at each component. |
| WPS | `get_path` | nested absolute `GEOGRID.TBL` path | separator-free relative `METGRID.TBL` path | Pinned path extraction is compared with the directories of table paths returned by the generated WPS configuration parser; cases cover nested paths and its documented `./` fallback. |
| wavelets (supplemental) | `CFFTB` | four complex frequency samples with nonzero real and imaginary parts | one complex sample (`N=1`) | Exact inverse-FFT counterpart exposed by the generated target; added after the Cmathtuts feasibility exclusion so the expansion still reaches 54 genuine cases without manufacturing a source/target match. |

### Recorded source-level feasibility exclusion

`Cmathtuts` has no defensible second source/target routine pair in the pinned
snapshot.  Its `matrix_multiply` procedure is already covered and is the only
pinned routine corresponding to the generated BLAS behavior.  The remaining
small deterministic routines (`ffunction`, `ADD`, and `tstfunc`) are unrelated
C-interoperability demonstrations with no generated callable counterpart, while
`ranvec` is nondeterministic.  This exclusion was recorded without executing a
new Cmathtuts target case.  Two supplemental `CFFTB` cases preserve the planned
54-case addition while keeping every new probe behaviorally grounded.

### Recorded distinct-function outcome

All 54 predeclared cases compile and execute their pinned source routines, remain in the fixed denominator, and have verified source locators. The source-information audit reports 444 `original-file-plus-driver`, 8 `extracted-source`, 73 `inline-reimplementation`, and 34 `synthetic-fixture` rows across 559 probes. The direct cases span 130 repository-routine pairs. Twenty-six of the 27 previously one-routine repositories gained a second routine; the frozen `Cmathtuts` exclusion leaves it as the only one-routine repository.

The archived-target replay reported 40 agreements, 12 behavioral mismatches, and two explicit errors among the 54 additions. Across the complete fixed denominator it reported 434 agreements, 74 mismatches, and 51 errors. These outcomes were observed only after selection and were not used to alter inputs, tolerances, expected shapes, or the feasibility decision.
