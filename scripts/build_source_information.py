#!/usr/bin/env python3
"""Build per-probe source information from pinned source trees.

The provenance manifest joins every probe to the verifier that defines it, indexes Fortran
procedures at the exact recorded Git revision, and emits a reviewable manifest.
Name matching is intentionally conservative: unresolved or ambiguous matches
remain visible instead of being guessed.
"""

from __future__ import annotations

import argparse
import ast
import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


FORTRAN_SUFFIXES = {".f", ".for", ".f90", ".f95", ".f03", ".f08"}
FIELDS = (
    "probe_id",
    "oracle_kind",
    "upstream_path",
    "upstream_symbol",
    "upstream_start_line",
    "upstream_end_line",
    "harness_path",
    "harness_start_line",
    "harness_end_line",
    "source_note",
)

# Version 1.0.0's former f2py-backed cases now compile the pinned source files
# with standalone drivers. Keep the category available for future additions,
# but do not assign it to any current probe.
F2PY_CASE_PREFIXES: dict[str, tuple[str, ...]] = {}

# These cases compile the pinned upstream routine with only a small driver.
# This override is needed when the routine is reached through an include file
# (QUADPACK) or when the verifier compiles a list assembled in Python.
ORIGINAL_CASE_PREFIXES = {
    "arpack-ng": ("compute_residual_norm",),
    "ccpp-physics": ("physical_constants",),
    "fftpack": ("zfftf", "zfftb"),
    "hdf5": (
        "get_numpy_dtype_itemsize_int",
        "get_numpy_dtype_itemsize_double",
        "get_numpy_dtype_itemsize_float",
    ),
    "IO-Fortran-Library": ("parse_source_files_line_count",),
    "minpack": ("dpmpar",),
    "quadpack": ("dqk15", "dqk21"),
    "coretran": ("process_strings_parse", "count_entries_direct"),
    "MPM3D-F90": ("dynamic_relaxation_damping_direct",),
    "neural-fortran": ("split_attention_heads_direct",),
    "WPS": ("parse_wps_config_direct", "config_table_path_direct"),
    "xtb": ("symbol_to_number_direct",),
}

# These expectations are deliberately synthetic contracts, not extracted
# upstream procedures. They remain useful, but must not be called compiled
# source oracles in the metadata.
SYNTHETIC_CASE_PREFIXES = {
    "forpy": ("analyze_fortran",),
    "hdf5": ("get_numpy_dtype_itemsize_char", "get_numpy_dtype_itemsize_extended"),
    "MPM3D-F90": ("integrate_momentum",),
    "neural-fortran": ("quadratic",),
    "WPS": ("interpolate_met_fields",),
}

# Case labels include input/output suffixes. Most map by longest procedure-name
# prefix; these aliases cover known public API spelling differences.
SYMBOL_ALIASES = {
    ("ABAQUS", "dload_moving_pressure"): "dload",
    ("ABAQUS", "uel_bodyforce_direct"): "uel",
    ("arpack-ng", "compute_residual_norm"): "pdnorm2",
    ("arpack-ng", "convergence_dsconv_direct"): "dsconv",
    ("atomsk", "xyz_serializer"): "write_xyz",
    ("atomsk", "atomic_species_direct"): "atomspecies",
    ("bspline-fortran", "compute_basis_functions"): "db1val_default",
    ("bspline-fortran", "compute_coefficients_db1ink_direct"): "db1ink_default",
    ("crest", "symbol_to_atomic_number"): "e2i",
    ("crest", "read_xyz_rdxmol_direct"): "rdxmol",
    ("dftd4", "get_rational_damping"): "get_rational_damping_name",
    ("elmerfem", "gauss_quadrature_triangle_direct"): "gausspointstriangle",
    ("elmerfem", "gauss_quadrature_1d_assembly_direct"): "gausspoints1d",
    ("fortran2018-examples", "assert_close"): "isclose_64",
    ("fortran2018-examples", "assert_close_single_precision_direct"): "isclose_32",
    ("fortranlib", "access_exists_dir_as_dir"): "dir_exists",
    ("fortranlib", "access_exists_file_as_dir"): "dir_exists",
    ("fortranlib", "access_exists_dir_as_file"): "file_exists",
    ("fortranlib", "access_exists_file_as_file"): "file_exists",
    ("fortranlib", "access_exists_missing_file"): "file_exists",
    ("functional-fortran", "arange"): "arange_r8",
    ("functional-fortran", "reverse_operation"): "reverse_r8",
    ("FOODIE", "integrator_scheme_support_direct"): "is_supported",
    ("fpm", "fpm_release_direct"): "fpm_version",
    ("fpm", "version_parse_direct"): "new_version_from_string",
    ("IO-Fortran-Library", "parse_source_files_line_count"): "read_file",
    ("Incompact3d", "compute_spatial_derivatives"): "derx_00",
    ("Incompact3d", "compute_spatial_derivatives_derx11_direct"): "derx_11",
    ("M_strings", "string_to_value_int32"): "a2i",
    ("M_strings", "atoi_int64_direct"): "atoi_int64",
    ("openfast", "interpolate_1d"): "interpbinreal",
    ("openfast", "disk_velocity_mean_direct"): "mean",
    ("MPM3D-F90", "init_particle_velocity_direct"): "initparticle",
    ("MPM3D-F90", "dynamic_relaxation_damping_direct"): "dynamicrelaxationdamping",
    ("roots-fortran", "bisection_method"): "bisection",
    ("roots-fortran", "root_scalar_methods"): "root_scalar_by_name",
    ("M_time", "demo_sec2days_duration"): "sec2days",
    ("M_time", "iso_week_d2w_direct"): "d2w",
    ("packmol", "jacobi_eigen"): "jacobi",
    ("packmol", "periodic_wrap_v_in_box_direct"): "v_in_box",
    ("stdlib", "radix_sort_direct_u16_min"): "radix_sort_u16_helper",
    ("stdlib", "radix_sort_direct_u32_max"): "radix_sort_u32_helper",
    ("stdlib", "radix_sort_direct_u16_median"): "radix_sort_u16_helper",
    ("stdlib", "radix_sort_direct_u16_max"): "radix_sort_u16_helper",
    ("stdlib", "radix_sort_direct_u32_min"): "radix_sort_u32_helper",
    ("toml-f", "datetime_roundtrip"): "new_datetime_from_string",
    ("toml-f", "datetime_compare_direct"): "compare_datetime",
    ("neural-fortran", "split_attention_heads_direct"): "split_heads",
    ("neural-fortran", "combine_attention_heads_direct"): "combine_heads",
    ("xtb", "chemical_element_symbol"): "tosymbol",
    ("xtb", "chemical_element_symbol_carbon"): "tosymbol",
    ("xtb", "chemical_element_symbol_unknown"): "tosymbol",
    ("xtb", "symbol_to_number_direct"): "tonumber",
    ("WPS", "parse_wps_config_direct"): "despace",
    ("WPS", "config_table_path_direct"): "get_path",
    ("wavelets", "fft_forward_direct"): "cfftf",
    ("wavelets", "fft_backward_direct"): "cfftb",
    ("Cmathtuts", "execute_blas_level3_operations_gemm"): "matrix_multiply",
    ("Cmathtuts", "validate_computational_results_l2_norm_direct"): "pythagoras",
    ("Nek5000", "dnrm2_scaled"): "dnrm2",
    ("cp2k", "kahan_sum"): "kahan_sum_d1",
    ("cp2k", "kahan_extra_sum"): "kahan_sum_d1",
    ("cp2k", "kahan_dot"): "kahan_dot_product_d1",
    ("cp2k", "kahan_extra_dot"): "kahan_dot_product_d1",
    ("coretran", "process_strings_parse"): "compact",
    ("coretran", "count_entries_direct"): "countentries",
}

# Some pinned repositories contain generated documentation copies, tutorial
# stages, or vendored implementations with the same symbol.  These prefixes
# identify the source tree actually exercised or the canonical source used to
# derive the inline contract.
PREFERRED_PATH_PREFIXES = {
    "fastGPT": ("src/",),
    "fortran2018-examples": ("src/",),
    "fortranlib": ("src/posix_default.f90",),
    "functional-fortran": ("src/functional.f90",),
    "M_args-main": ("src/M_args.f90",),
    "M_strings": ("src/M_strings.F90",),
    "Nek5000": ("3rd_party/blasLapack/",),
    "tsunami": ("src/ch10/mod_parallel.f90", "src/ch04/mod_diff.f90"),
}


@dataclass(frozen=True)
class Procedure:
    path: str
    symbol: str
    start: int
    end: int
    normalized: str


# Explicit source locators for compiled module parameters. These are not
# procedures, so the general procedure index cannot discover them, but their
# values are read by drivers that compile the exact pinned files.
LOCATOR_OVERRIDES = {
    # These drivers deliberately choose one of several duplicate/generated
    # source copies in the pinned repositories.  Record the exact file that is
    # compiled instead of leaving the provenance classification ambiguous.
    ("arpack-ng", "compute_residual_norm"): Procedure(
        "PARPACK/SRC/MPI/pdnorm2.f", "pdnorm2", 20, 89, ""
    ),
    ("IO-Fortran-Library", "parse_source_files_line_count"): Procedure(
        "src/modules/io_fortran_lib_mod.f90", "read_file", 215, 228, ""
    ),
    ("IO-Fortran-Library", "count_substring_chars_direct"): Procedure(
        "src/io_fortran_lib/string_methods_impl.f90", "count_substring_chars", 21, 92, ""
    ),
    ("Cmathtuts", "validate_computational_results_l2_norm_direct"): Procedure(
        "A_fortran/test5/FORSUBS.FOR", "pythagoras", 15, 20, ""
    ),
    ("coretran", "process_strings_parse"): Procedure(
        "src/core/m_strings.f90", "compact", 192, 224, ""
    ),
    ("coretran", "count_entries_direct"): Procedure(
        "src/core/m_strings.f90", "countentries", 168, 177, ""
    ),
    ("neural-fortran", "split_attention_heads_direct"): Procedure(
        "src/nf/nf_multihead_attention_layer_submodule.f90", "split_heads", 137, 142, ""
    ),
    ("neural-fortran", "combine_attention_heads_direct_ordinary"): Procedure(
        "src/nf/nf_multihead_attention_layer_submodule.f90", "combine_heads", 185, 194, ""
    ),
    ("neural-fortran", "combine_attention_heads_direct_zero_boundary"): Procedure(
        "src/nf/nf_multihead_attention_layer_submodule.f90", "combine_heads", 185, 194, ""
    ),
    ("FOODIE", "initialize_integrator_direct_ordinary_supported"): Procedure(
        "src/lib/foodie_integrator_euler_explicit.F90", "initialize", 134, 152, ""
    ),
    ("FOODIE", "initialize_integrator_direct_unsupported_boundary"): Procedure(
        "src/lib/foodie_integrator_euler_explicit.F90", "initialize", 134, 152, ""
    ),
    ("ABAQUS", "uel_bodyforce_direct_rotating_ordinary"): Procedure(
        "UEL_bodyforce.for", "UEL", 8, 194, ""
    ),
    ("ABAQUS", "uel_bodyforce_direct_zero_time_boundary"): Procedure(
        "UEL_bodyforce.for", "UEL", 8, 194, ""
    ),
    ("WPS", "parse_wps_config_direct"): Procedure(
        "ungrib/src/module_stringutil.F", "despace", 51, 80, ""
    ),
    ("WPS", "config_table_path_direct"): Procedure(
        "ungrib/src/module_stringutil.F", "get_path", 13, 42, ""
    ),
    ("forpy", "forpy_public_parameter_direct_no_numpy_error"): Procedure(
        "forpy_mod.F90", "NO_NUMPY_ERROR", 60, 60, ""
    ),
    ("forpy", "forpy_public_parameter_direct_meth_varargs"): Procedure(
        "forpy_mod.F90", "METH_VARARGS", 64, 64, ""
    ),
    ("forpy", "forpy_public_parameter_direct_exception_error"): Procedure(
        "forpy_mod.F90", "EXCEPTION_ERROR", 61, 61, ""
    ),
    ("forpy", "forpy_public_parameter_direct_meth_keywords"): Procedure(
        "forpy_mod.F90", "METH_KEYWORDS", 65, 65, ""
    ),
    ("forpy", "forpy_public_parameter_direct_meth_noargs"): Procedure(
        "forpy_mod.F90", "METH_NOARGS", 66, 66, ""
    ),
    ("hdf5", "get_numpy_dtype_itemsize_declared_direct_fortran_real_c_double"): Procedure(
        "config/toolchain/fortpregen/gfortran/H5fortran_types.F90", "Fortran_REAL_C_DOUBLE", 31, 31, ""
    ),
    ("hdf5", "get_numpy_dtype_itemsize_declared_direct_hsize_t"): Procedure(
        "config/toolchain/fortpregen/gfortran/H5fortran_types.F90", "HSIZE_T", 23, 23, ""
    ),
    ("ccpp-physics", "physical_constants_con_pi"): Procedure(
        "physics/hooks/physcons.F90", "con_pi", 46, 46, ""
    ),
    ("ccpp-physics", "physical_constants_con_g"): Procedure(
        "physics/hooks/physcons.F90", "con_g", 52, 52, ""
    ),
    ("ccpp-physics", "physical_constants_con_rd"): Procedure(
        "physics/hooks/physcons.F90", "con_rd", 64, 64, ""
    ),
    ("ccpp-physics", "physical_constants_con_rv"): Procedure(
        "physics/hooks/physcons.F90", "con_rv", 65, 65, ""
    ),
    ("ccpp-physics", "physical_constants_con_cp"): Procedure(
        "physics/hooks/physcons.F90", "con_cp", 66, 66, ""
    ),
    ("ccpp-physics", "physical_constants_con_hvap"): Procedure(
        "physics/hooks/physcons.F90", "con_hvap", 71, 71, ""
    ),
    ("ccpp-physics", "physical_constants_con_t0c"): Procedure(
        "physics/hooks/physcons.F90", "con_t0c", 76, 76, ""
    ),
    ("minpack", "dpmpar"): Procedure("src/minpack.f90", "dpmpar", 16, 18, ""),
    ("hdf5", "get_numpy_dtype_itemsize_int"): Procedure(
        "config/toolchain/fortpregen/gfortran/H5fortran_types.F90",
        "Fortran_INTEGER",
        28,
        28,
        "",
    ),
    ("hdf5", "get_numpy_dtype_itemsize_double"): Procedure(
        "config/toolchain/fortpregen/gfortran/H5fortran_types.F90",
        "Fortran_DOUBLE",
        36,
        36,
        "",
    ),
    ("hdf5", "get_numpy_dtype_itemsize_float"): Procedure(
        "config/toolchain/fortpregen/gfortran/H5fortran_types.F90",
        "Fortran_REAL_C_FLOAT",
        30,
        30,
        "",
    ),
}


@dataclass(frozen=True)
class Verifier:
    path: str
    start: int
    end: int
    source_basenames: frozenset[str]
    inline_fingerprints: frozenset[str]


PROCEDURE_START = re.compile(
    r"^\s*(?:(?:pure|elemental|recursive|impure|module)\s+)*"
    r"(?:(?:double\s+precision|real|integer|logical|complex|character|"
    r"type\s*\([^)]*\)|class\s*\([^)]*\))[^!]*?\s+)?"
    r"(subroutine|function)\s+([a-z][a-z0-9_]*)\b",
    re.IGNORECASE,
)
PROCEDURE_END = re.compile(r"^\s*end\s*(subroutine|function)\b", re.IGNORECASE)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def literal_repo_result(function: ast.FunctionDef) -> tuple[str, str] | None:
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_repo_result":
            continue
        if len(node.args) < 2:
            continue
        tier, repository = node.args[:2]
        if isinstance(tier, ast.Constant) and isinstance(repository, ast.Constant):
            if isinstance(tier.value, str) and isinstance(repository.value, str):
                return tier.value, repository.value
    return None


def index_verifiers(root: Path) -> dict[str, Verifier]:
    result: dict[str, Verifier] = {}
    for relative in (
        "harness/python/run_corpus_verification.py",
        "harness/python/extended_repo_verifiers.py",
    ):
        path = root / relative
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("verify_"):
                continue
            identity = literal_repo_result(node)
            if identity is None:
                continue
            _, repository = identity
            basenames = {
                Path(value.value).name.casefold()
                for value in ast.walk(node)
                if isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and Path(value.value).suffix.casefold() in FORTRAN_SUFFIXES
                and not Path(value.value).name.casefold().startswith(("run_", "probe_"))
            }
            inline_fingerprints: set[str] = set()
            for value in ast.walk(node):
                if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                    continue
                if not re.search(r"\b(subroutine|function)\b", value.value, re.IGNORECASE):
                    continue
                inline_fingerprints.update(
                    item.normalized
                    for item in index_procedures_in_text("<inline>", value.value)
                    if item.normalized
                )
            result[repository] = Verifier(
                path=relative,
                start=node.lineno,
                end=node.end_lineno or node.lineno,
                source_basenames=frozenset(basenames),
                inline_fingerprints=frozenset(inline_fingerprints),
            )
    return result


def normalize_fortran(lines: list[str]) -> str:
    cleaned = []
    for line in lines:
        code = line.split("!", 1)[0].casefold()
        cleaned.append(re.sub(r"\s+", "", code))
    return "".join(cleaned)


def index_procedures_in_text(path: str, text: str) -> list[Procedure]:
    procedures: list[Procedure] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = PROCEDURE_START.match(line)
        if not match:
            continue
        kind, symbol = match.groups()
        end = index + 1
        for cursor in range(index + 1, len(lines)):
            end_match = PROCEDURE_END.match(lines[cursor])
            if end_match and end_match.group(1).casefold() == kind.casefold():
                end = cursor + 1
                break
        procedures.append(
            Procedure(
                path=path,
                symbol=symbol.casefold(),
                start=index + 1,
                end=end,
                normalized=normalize_fortran(lines[index:end]),
            )
        )
    return procedures


def index_procedures(repository_root: Path) -> list[Procedure]:
    procedures: list[Procedure] = []
    for path in sorted(repository_root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in FORTRAN_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relative = path.relative_to(repository_root).as_posix()
        procedures.extend(index_procedures_in_text(relative, text))
    return procedures


def starts_with_any(value: str, prefixes: tuple[str, ...]) -> bool:
    return any(value == prefix or value.startswith(prefix + "_") for prefix in prefixes)


def desired_symbol(repository: str, case_name: str) -> str | None:
    matches = [
        (prefix, symbol)
        for (repo, prefix), symbol in SYMBOL_ALIASES.items()
        if repository == repo and (case_name == prefix or case_name.startswith(prefix + "_"))
    ]
    if not matches:
        return None
    # A general family alias may be a prefix of a more specific direct-source
    # case (for example assert_close vs. assert_close_single_precision_direct).
    # Select the most specific declared alias rather than relying on mapping
    # insertion order.
    return max(matches, key=lambda item: len(item[0]))[1]


def explicit_locator(repository: str, case_name: str) -> Procedure | None:
    matches = [
        procedure
        for (repo, prefix), procedure in LOCATOR_OVERRIDES.items()
        if repository == repo and (case_name == prefix or case_name.startswith(prefix + "_"))
    ]
    if len(matches) > 1:
        raise RuntimeError(f"ambiguous explicit locators for {repository}:{case_name}")
    return matches[0] if matches else None


def select_procedure(
    repository: str,
    case_name: str,
    procedures: list[Procedure],
    verifier: Verifier,
) -> tuple[Procedure | None, str]:
    alias = desired_symbol(repository, case_name)
    if alias is not None:
        candidates = [item for item in procedures if item.symbol == alias]
    else:
        candidates = [
            item
            for item in procedures
            if case_name.casefold() == item.symbol or case_name.casefold().startswith(item.symbol + "_")
        ]
        if candidates:
            longest = max(len(item.symbol) for item in candidates)
            candidates = [item for item in candidates if len(item.symbol) == longest]
    unique = {(item.path, item.symbol, item.start, item.end): item for item in candidates}
    candidates = list(unique.values())
    # A verifier that compiles an upstream file provides stronger evidence
    # than a name match elsewhere in the repository.
    source_matches = [
        item for item in candidates if Path(item.path).name.casefold() in verifier.source_basenames
    ]
    if source_matches:
        candidates = source_matches
    preferred = PREFERRED_PATH_PREFIXES.get(repository, ())
    preferred_matches = [
        item for item in candidates if any(item.path.startswith(prefix) for prefix in preferred)
    ]
    if preferred_matches:
        candidates = preferred_matches
    exact_file_matches = [
        item for item in candidates if Path(item.path).stem.casefold() == item.symbol
    ]
    if exact_file_matches:
        candidates = exact_file_matches
    if len(candidates) == 1:
        return candidates[0], "verified-symbol-match"
    if len(candidates) > 1:
        summary = "; ".join(f"{item.path}:{item.start}:{item.symbol}" for item in candidates[:6])
        return None, f"ambiguous: {summary}"
    return None, "unresolved: no upstream procedure-name match"


def oracle_kind(repository: str, case_name: str, procedure: Procedure | None, verifier: Verifier) -> str:
    if starts_with_any(case_name, SYNTHETIC_CASE_PREFIXES.get(repository, ())):
        return "synthetic-fixture"
    if starts_with_any(case_name, F2PY_CASE_PREFIXES.get(repository, ())):
        return "f2py-wrapper"
    if starts_with_any(case_name, ORIGINAL_CASE_PREFIXES.get(repository, ())):
        return "original-file-plus-driver"
    if procedure is not None and Path(procedure.path).name.casefold() in verifier.source_basenames:
        return "original-file-plus-driver"
    if procedure is not None and procedure.normalized in verifier.inline_fingerprints:
        return "extracted-source"
    # An inline program may faithfully reproduce a small behavior, but it is
    # not called an extraction unless a text-level comparison has established that.
    # The current release therefore uses the more conservative label.
    return "inline-reimplementation"


def build(root: Path, corpus_root: Path, output: Path) -> None:
    repositories = read_csv(root / "manifests/repositories.csv")
    probes = read_csv(root / "manifests/probes.csv")
    repository_root_by_repo: dict[str, Path] = {}
    for row in repositories:
        flat_root = corpus_root / row["directory"]
        tiered_root = corpus_root / row["tier"] / row["directory"]
        repository_root_by_repo[row["repository"]] = (
            flat_root if flat_root.is_dir() else tiered_root
        )
    verifiers = index_verifiers(root)
    procedure_index = {
        repository: index_procedures(repository_root)
        for repository, repository_root in repository_root_by_repo.items()
    }

    rows: list[dict[str, str]] = []
    for probe in probes:
        repository = probe["repository"]
        verifier = verifiers.get(repository)
        if verifier is None:
            raise RuntimeError(f"no verifier function found for {repository}")
        synthetic = starts_with_any(probe["case_name"], SYNTHETIC_CASE_PREFIXES.get(repository, ()))
        override = explicit_locator(repository, probe["case_name"])
        if synthetic:
            procedure, status = None, "not-applicable-synthetic"
        elif override is not None:
            procedure, status = override, "verified-explicit-locator"
        else:
            procedure, status = select_procedure(
                repository,
                probe["case_name"],
                procedure_index[repository],
                verifier,
            )
        kind = oracle_kind(repository, probe["case_name"], procedure, verifier)
        note = status
        if status == "not-applicable-synthetic":
            note = "Synthetic contract; no upstream procedure is claimed."
        elif procedure is None and kind == "inline-reimplementation":
            note = "Inline reimplementation; no exact upstream procedure is claimed."
        rows.append(
            {
                "probe_id": probe["probe_id"],
                "oracle_kind": kind,
                "upstream_path": procedure.path if procedure else "",
                "upstream_symbol": procedure.symbol if procedure else "",
                "upstream_start_line": str(procedure.start) if procedure else "",
                "upstream_end_line": str(procedure.end) if procedure else "",
                "harness_path": verifier.path,
                "harness_start_line": str(verifier.start),
                "harness_end_line": str(verifier.end),
                "source_note": note,
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    counts: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["oracle_kind"]] += 1
    print(f"wrote {len(rows)} source-information records to {output}")
    print("; ".join(f"{key}={counts[key]}" for key in sorted(counts)))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=root / "manifests/source_information.csv")
    args = parser.parse_args()
    build(root, args.corpus_root, args.output)


if __name__ == "__main__":
    main()
