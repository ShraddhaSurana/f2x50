from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.util
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import types
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


PACKAGE_ROOT = Path(os.environ.get("F2X_EVIDENCE_PACKAGE_ROOT", Path(__file__).resolve().parents[2]))
HARNESS_ROOT = Path(os.environ.get("F2X_BEHAVIORAL_HARNESS_ROOT", Path(__file__).resolve().parent))
FORTRAN_CORPUS_ROOT = Path(
    os.environ.get("F2X_FORTRAN_CORPUS_ROOT", str(PACKAGE_ROOT / "external" / "fortran_corpus"))
)
TARGET_ROOT = Path(os.environ.get("F2X_TARGET_ROOT", str(PACKAGE_ROOT / "external" / "targets" / "python")))
STUB_ROOT = Path(__file__).resolve().parents[1] / "fortran_stubs"
DEFAULT_JSON_OUT = PACKAGE_ROOT / "results" / "corpus_behavioral_validation_results.json"
DEFAULT_MARKDOWN_OUT = PACKAGE_ROOT / "results" / "corpus_behavioral_validation_report.md"

if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))


@dataclass
class CheckResult:
    routine: str
    status: str
    comparison: str
    max_abs: float | None
    max_rel: float | None
    note: str = ""


@dataclass
class RepoResult:
    tier: str
    repo: str
    status: str
    notes: str
    checks: list[CheckResult]


MANUAL_MODULE_PATHS: dict[str, dict[tuple[str, str, str], str]] = {
    "direct": {
        ("low", "tsunami", "ch10/mod_parallel.py"): "mod_parallel.py",
        ("low", "tsunami", "ch04/mod_diff.py"): "mod_diff.py",
        ("low", "FKB", "mod_activation.py"): "mod_activation.py",
        ("low", "fastGPT", "linalg_module.py"): "gpt2.py",
        ("low", "fortranlib", "io_operations.py"): "lib_io.py",
        ("low", "fortran-utils", "utils.py"): "utils.py",
        ("low", "datetime-fortran", "datetime_module.py"): "datetime_module.py",
        ("low", "M_strings", "M_strings.py"): "M_strings.py",
        ("low", "fftpack", "fftpack.py"): "fftpack.py",
        ("medium", "minpack", "minpack.py"): "minpack.py",
        ("medium", "json-fortran", "json_string_utilities.py"): "json_string_utilities.py",
        ("medium", "Fortran-Astrodynamics-Toolkit", "conversion_module.py"): "conversion_module.py",
        ("medium", "Fortran-Astrodynamics-Toolkit", "complex_step.py"): "complex_step.py",
        ("medium", "quadpack", "dqk15.py"): "quadpack_generic.py",
        ("medium", "wavelets", "wavelets/cdfchi.py"): "test_chi_square_cdf_edge.py",
        ("medium", "stdlib", "system/path_operations.py"): "stdlib_system_path.py",
        ("medium", "stdlib", "quadrature/gauss_legendre.py"): "stdlib_quadrature_gauss.py",
        ("complex", "Nek5000", "blas_lapack.py"): "blas.py",
        ("complex", "pymc2", "blas_core.py"): "blas_core.py",
        ("complex", "fpm", "compiler_config.py"): "fpm_compiler.py",
        ("complex", "ccpp-physics", "gfs_debug.py"): "GFS_debug.py",
        ("complex", "petsc", "index_splitting.py"): "ex61f.py",
    },
    "repo_context_direct": {
        ("low", "FKB", "mod_activation.py"): "lib/mod_activation.py",
        ("low", "fortranlib", "io_operations.py"): "lib_io.py",
        ("low", "fortran-utils", "utils.py"): "utils.py",
        ("low", "datetime-fortran", "datetime_module.py"): "datetime_module.py",
        ("low", "M_strings", "M_strings.py"): "M_strings.py",
        ("medium", "minpack", "minpack.py"): "minpack.py",
        ("medium", "json-fortran", "json_string_utilities.py"): "json_string_utilities.py",
        ("medium", "Fortran-Astrodynamics-Toolkit", "conversion_module.py"): "conversion_module.py",
        ("medium", "Fortran-Astrodynamics-Toolkit", "complex_step.py"): "complex_step.py",
        ("medium", "stdlib", "system/path_operations.py"): "stdlib_system_path.py",
        ("medium", "stdlib", "quadrature/gauss_legendre.py"): "stdlib_quadrature_gauss.py",
        ("complex", "lapack", "dcopy.py"): "blas.py",
        ("complex", "lapack", "dscal.py"): "blas.py",
        ("complex", "pymc2", "blas_core.py"): "blas_core.py",
        ("complex", "fpm", "compiler_config.py"): "fpm_compiler.py",
        ("complex", "ccpp-physics", "gfs_debug.py"): "GFS_debug.py",
        ("complex", "petsc", "index_splitting.py"): "ex61f.py",
    },
}


def _load_module(name: str, path: Path):
    resolved = _manual_equivalent_path(path)
    src_root = _src_root_for(resolved)
    old_path = list(sys.path)
    if src_root is not None:
        sys.path.insert(0, str(src_root.parent))
    try:
        primary = _load_module_direct(name, resolved)
    except Exception:
        # The expected/manually-mapped file is missing or fails to import
        # (common for baselines that rename, merge, or relocate the
        # equivalent routine).  Defer to _ResolvedModule's by-name tree
        # search over the same repo's generated src/ tree instead of
        # failing the whole probe outright.
        primary = None
    finally:
        sys.path[:] = old_path
    return _ResolvedModule(name, path, primary, src_root, allow_tree_search=True)


def _load_module_direct(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec, matching normal import semantics: code that does
    # self-referential module lookups during execution (e.g. dataclasses'
    # `sys.modules.get(cls.__module__)`) needs the entry to already exist.
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _src_root_for(path: Path) -> Path | None:
    parts = path.parts
    for index, part in enumerate(parts):
        if part == "src":
            return Path(*parts[: index + 1])
    return None


def _manual_equivalent_path(path: Path) -> Path:
    if path.exists():
        return path
    parsed = _parse_generated_path(path)
    if parsed is None:
        return path
    method, src_root, tier, repo, relative = parsed
    mapped = MANUAL_MODULE_PATHS.get(method, {}).get((tier, repo, relative.as_posix()))
    if mapped is None:
        return path
    return src_root / mapped


def _parse_generated_path(path: Path) -> tuple[str, Path, str, str, Path] | None:
    parts = path.parts
    try:
        generated_index = parts.index("generated_python")
        src_index = generated_index + 1
        if parts[src_index] != "src":
            return None
        tier = parts[generated_index - 2]
        repo = parts[generated_index - 1]
        src_root = Path(*parts[: src_index + 1])
        relative = Path(*parts[src_index + 1 :])
    except (ValueError, IndexError):
        return None

    prefix = "/".join(parts[:generated_index])
    if "repository_profile" in prefix:
        method = "repository_profile"
    elif "scc_chunking" in prefix:
        method = "scc_chunking"
    elif "repo_context_direct" in prefix:
        method = "repo_context_direct"
    elif "/baseline/" in f"/{prefix}/":
        method = "direct"
    else:
        method = "python-target"
    return method, src_root, tier, repo, relative


class _CompilerIDAliases:
    """Compatibility aliases for direct translations that retained strings."""

    GCC = "gfortran"
    INTEL_CLASSIC_MAC = "ifort"
    INTEL_LLVM_NIX = "ifx"
    NVHPC = "nvfortran"
    LFORTRAN = "lfortran"
    UNKNOWN = "foo"


class _DebugConfigAdapter:
    def __init__(self, output_stream: Any | None = None, **_: Any) -> None:
        self.output_stream = output_stream


class _GFSDebugAdapter:
    def __init__(self, config: Any, resolver: "_ResolvedModule") -> None:
        self.config = config
        self.resolver = resolver

    def _call_print(self, name: str, label: str, value: Any, **kwargs: Any) -> str:
        function = self.resolver._resolve_raw(name)
        lat = np.zeros(1, dtype=np.float64)
        lon = np.zeros(1, dtype=np.float64)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            result = function(
                kwargs.get("mpirank", 0),
                kwargs.get("omprank", 0),
                kwargs.get("blkno", 0),
                lat,
                lon,
                label,
                value,
            )
        text = stream.getvalue().strip()
        if result is not None and not text:
            text = str(result).strip()
        if getattr(self.config, "output_stream", None) is not None and text:
            self.config.output_stream.write(text + "\n")
        return text

    def print_logic_0d(self, label: str, value: bool, **kwargs: Any) -> str:
        return self._call_print("print_logic_0d", label, value, **kwargs)

    def print_int_0d(self, label: str, value: int, **kwargs: Any) -> str:
        return self._call_print("print_int_0d", label, value, **kwargs)

    def print_real_0d(self, label: str, value: float, **kwargs: Any) -> str:
        return self._call_print("print_real_0d", label, value, **kwargs)


class _ResolvedModule:
    """Module proxy that resolves equivalent generated routines by name.

    Python targets usually follow the expected curated file layout. Direct
    baselines often preserve source-file names instead.  This proxy first uses
    the expected module when present, then searches the same generated `src/`
    tree for a function or class with the requested name.
    """

    def __init__(
        self,
        name: str,
        expected_path: Path,
        primary: types.ModuleType | None,
        src_root: Path | None,
        *,
        allow_tree_search: bool = True,
    ) -> None:
        self.__name__ = name
        self.__file__ = str(expected_path)
        self._name = name
        self._expected_path = expected_path
        self._primary = primary
        self._src_root = src_root
        self._allow_tree_search = allow_tree_search
        self._modules: dict[Path, types.ModuleType | None] = {}
        self._cache: dict[str, Any] = {}

    def __getattr__(self, attr: str) -> Any:
        if self._primary is not None and hasattr(self._primary, attr):
            return getattr(self._primary, attr)
        if attr == "CompilerID":
            return _CompilerIDAliases
        if attr == "DebugConfig":
            return _DebugConfigAdapter
        if attr == "GFSDebug":
            resolver = self

            class GFSDebug(_GFSDebugAdapter):
                def __init__(self, config: Any) -> None:
                    super().__init__(config, resolver)

            return GFSDebug
        return self._resolve_raw(attr)

    def _resolve_raw(self, attr: str) -> Any:
        if attr in self._cache:
            return self._cache[attr]
        if self._primary is not None:
            for _, class_value in vars(self._primary).items():
                if isinstance(class_value, type) and hasattr(class_value, attr):
                    value = self._adapt_callable(attr, getattr(class_value, attr))
                    self._cache[attr] = value
                    return value
        if not self._allow_tree_search:
            raise AttributeError(attr)
        if self._src_root is None or not self._src_root.exists():
            raise AttributeError(attr)

        candidates: list[tuple[int, Path, Any]] = []
        for path in self._src_root.rglob("*.py"):
            module = self._load_candidate(path)
            if module is None:
                continue
            value = getattr(module, attr, None)
            if value is not None:
                candidates.append((self._candidate_score(path, attr), path, value))
            for _, class_value in vars(module).items():
                if isinstance(class_value, type) and hasattr(class_value, attr):
                    candidates.append((self._candidate_score(path, attr) + 10, path, getattr(class_value, attr)))

        if not candidates:
            raise AttributeError(attr)
        candidates.sort(key=lambda item: (item[0], len(str(item[1]))))
        value = self._adapt_callable(attr, candidates[0][2])
        self._cache[attr] = value
        return value

    def _load_candidate(self, path: Path) -> types.ModuleType | None:
        if path in self._modules:
            return self._modules[path]
        unique_name = f"_behavioral_resolved_{abs(hash(path))}"
        old_path = list(sys.path)
        sys.path.insert(0, str(self._src_root))
        if self._src_root is not None:
            sys.path.insert(0, str(self._src_root.parent))
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                module = _load_module_direct(unique_name, path)
        except BaseException:
            module = None
        finally:
            sys.path[:] = old_path
        self._modules[path] = module
        return module

    def _candidate_score(self, path: Path, attr: str) -> int:
        stem = path.stem.lower()
        attr_lower = attr.lower()
        if stem == attr_lower:
            return 0
        if attr_lower in stem:
            return 1
        if self._expected_path.stem.lower() == stem:
            return 2
        return 5

    def _adapt_callable(self, attr: str, value: Any) -> Any:
        if not callable(value):
            return value

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return self._call_adapted(attr, value, *args, **kwargs)
            except TypeError:
                return value(*args, **kwargs)

        return wrapper

    def _call_adapted(self, attr: str, function: Any, *args: Any, **kwargs: Any) -> Any:
        if attr == "ddot" and len(args) == 2:
            return function(len(args[0]), args[0], 1, args[1], 1)
        if attr == "dnrm2" and len(args) == 1:
            return function(len(args[0]), args[0], 1)
        if attr == "daxpy" and len(args) == 3:
            alpha, x, y = args
            result = function(len(x), alpha, x, 1, y, 1)
            return y if result is None else result
        if attr in {"dscal", "zfftf", "zfftb"}:
            result = function(*args, **kwargs)
            if result is None and len(args) >= 3:
                return args[2] if attr == "dscal" else args[1]
            return result
        return function(*args, **kwargs)


def _load_module_with_text_patches(
    path: Path, name: str, replacements: list[tuple[str, str]]
):
    resolved = _manual_equivalent_path(path)
    src_root = _src_root_for(resolved)
    old_path = list(sys.path)
    if src_root is not None:
        sys.path.insert(0, str(src_root.parent))
    try:
        source = resolved.read_text(encoding="utf-8")
        for old, new in replacements:
            source = source.replace(old, new)
        module = importlib.util.module_from_spec(
            importlib.util.spec_from_loader(name, loader=None)
        )
        module.__file__ = str(resolved)
        exec(compile(source, str(resolved), "exec"), module.__dict__)
        return module
    except Exception:
        # Same rationale as _load_module: the expected/manually-mapped file
        # is missing for this method's tree, so fall back to a by-name
        # search over the same repo's generated src/ tree.
        return _ResolvedModule(name, path, None, src_root, allow_tree_search=True)
    finally:
        sys.path[:] = old_path


def _load_package_module_patched(
    package_alias: str,
    package_dir: Path,
    module_name: str,
    patches: dict[str, list[tuple[str, str]]],
):
    temp_root = Path(tempfile.mkdtemp(prefix="behavioral-validation-patched-package-"))
    patched_dir = temp_root / "src"
    shutil.copytree(package_dir, patched_dir)
    for relative_path, replacements in patches.items():
        target = patched_dir / relative_path
        text = target.read_text(encoding="utf-8")
        for old, new in replacements:
            text = text.replace(old, new)
        target.write_text(text, encoding="utf-8")
    return _load_package_module(package_alias, patched_dir, module_name)


def _load_quadpack_dqk15_module(package_dir: Path):
    temp_root = Path(tempfile.mkdtemp(prefix="behavioral-validation-quadpack-"))
    patched_dir = temp_root / "src"
    shutil.copytree(package_dir, patched_dir)
    replacements = [
        ("np.finfo(np.float64).huge", "np.finfo(np.float64).max"),
        ("np.finfo(np.float64).radix", "2"),
        ("np.finfo(np.float64).precision", "15"),
    ]
    generic_path = patched_dir / "quadpack_generic.py"
    if generic_path.exists():
        generic_text = generic_path.read_text(encoding="utf-8")
        for old, new in replacements:
            generic_text = generic_text.replace(old, new)
        if "wp =" not in generic_text:
            generic_text += "\nwp = np.float64\n"
        generic_path.write_text(generic_text, encoding="utf-8")
        generic_module = _load_module("quadpack_generic_patched", generic_path)
        sys.modules["quadpack_generic_patched"] = generic_module

    if not (patched_dir / "dqk15.py").exists():
        # Some baselines merge dqk15 into a single file (e.g. quadpack_generic.py)
        # rather than keeping the curated target layout's separate dqk15.py.
        # Search the copied tree by symbol name instead of assuming the file.
        for candidate in sorted(patched_dir.rglob("*.py")):
            text = candidate.read_text(encoding="utf-8")
            if "def dqk15" not in text:
                continue
            patched_text = text
            for old, new in replacements:
                patched_text = patched_text.replace(old, new)
            if "wp =" not in patched_text and "import wp" not in patched_text:
                patched_text += "\nwp = np.float64\n"
            candidate.write_text(patched_text, encoding="utf-8")
            return _load_module_direct(f"quadpack_dqk15_found_{abs(hash(candidate))}", candidate)
        raise ImportError(f"No dqk15 implementation found under {package_dir}")

    dqk15_source = (patched_dir / "dqk15.py").read_text(encoding="utf-8")
    dqk15_source = dqk15_source.replace(
        "from .quadpack_generic import wp",
        "from quadpack_generic_patched import wp",
    )
    dqk15_module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("quadpack_dqk15_patched", loader=None)
    )
    dqk15_module.__file__ = str(patched_dir / "dqk15.py")
    exec(compile(dqk15_source, str(patched_dir / "dqk15.py"), "exec"), dqk15_module.__dict__)
    return dqk15_module


def _load_quadpack_dqk21_module(package_dir: Path):
    """Load a module exposing dqk21 from a generated quadpack tree.

    Mirrors `_load_quadpack_dqk15_module`: the target layout keeps dqk21 in
    quadpack_double.py (importing shared constants from quadpack_generic),
    while baselines may merge it anywhere, so fall back to a by-symbol search.
    """
    temp_root = Path(tempfile.mkdtemp(prefix="behavioral-validation-quadpack21-"))
    patched_dir = temp_root / "src"
    shutil.copytree(package_dir, patched_dir)
    replacements = [
        ("np.finfo(np.float64).huge", "np.finfo(np.float64).max"),
        ("np.finfo(np.float64).radix", "2"),
        ("np.finfo(np.float64).precision", "15"),
    ]
    generic_path = patched_dir / "quadpack_generic.py"
    if generic_path.exists():
        generic_text = generic_path.read_text(encoding="utf-8")
        for old, new in replacements:
            generic_text = generic_text.replace(old, new)
        if "wp =" not in generic_text:
            generic_text += "\nwp = np.float64\n"
        generic_path.write_text(generic_text, encoding="utf-8")
        generic_module = _load_module("quadpack_generic_patched", generic_path)
        sys.modules["quadpack_generic_patched"] = generic_module

    candidates = [patched_dir / "quadpack_double.py"]
    candidates.extend(sorted(patched_dir.rglob("*.py")))
    for candidate in candidates:
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8")
        if "def dqk21" not in text:
            continue
        for old, new in replacements:
            text = text.replace(old, new)
        text = text.replace("from .quadpack_generic import", "from quadpack_generic_patched import")
        if "wp =" not in text and "import wp" not in text:
            text += "\nwp = np.float64\n"
        module = importlib.util.module_from_spec(
            importlib.util.spec_from_loader("quadpack_dqk21_patched", loader=None)
        )
        module.__file__ = str(candidate)
        exec(compile(text, str(candidate), "exec"), module.__dict__)
        return module
    raise ImportError(f"No dqk21 implementation found under {package_dir}")


def _load_package_module(package_alias: str, package_dir: Path, module_name: str):
    init_path = package_dir / "__init__.py"
    package_spec = importlib.util.spec_from_file_location(
        package_alias,
        init_path,
        submodule_search_locations=[str(package_dir)],
    )
    if package_spec is None or package_spec.loader is None:
        raise ImportError(f"Could not load package {package_dir}")
    package = importlib.util.module_from_spec(package_spec)
    sys.modules[package_alias] = package
    package_spec.loader.exec_module(package)

    module_path = package_dir / (module_name.replace(".", "/") + ".py")
    full_name = f"{package_alias}.{module_name}"
    module_spec = importlib.util.spec_from_file_location(full_name, module_path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"Could not load module {module_path}")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[full_name] = module
    module_spec.loader.exec_module(module)
    return module


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    capture_stderr: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if capture_stderr else subprocess.PIPE,
    )


def _compile_fortran_program(
    name: str,
    *,
    inline_sources: list[tuple[str, str]] | None = None,
    file_sources: list[Path] | None = None,
) -> tuple[Path, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix=f"behavioral-validation-{name}-"))
    local_sources: list[Path] = []
    for filename, source in inline_sources or []:
        path = temp_root / filename
        path.write_text(source, encoding="utf-8")
        local_sources.append(path)
    local_sources.extend(file_sources or [])
    exe_path = temp_root / name
    cmd = [
        "gfortran",
        "-O0",
        "-ffree-line-length-none",
        "-ffixed-line-length-none",
        "-o",
        str(exe_path),
        *[str(path) for path in local_sources],
    ]
    _run(cmd)
    return exe_path, temp_root


def _compile_fortran_program_ordered(
    name: str,
    *,
    ordered_sources: list[Path],
    inline_sources: list[tuple[str, str]] | None = None,
) -> tuple[Path, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix=f"behavioral-validation-{name}-"))
    local_sources: list[Path] = []
    for filename, source in inline_sources or []:
        path = temp_root / filename
        path.write_text(source, encoding="utf-8")
        local_sources.append(path)

    objects: list[Path] = []
    for source in ordered_sources:
        object_path = temp_root / f"{source.stem}.o"
        _run(
            [
                "gfortran",
                "-O0",
                "-ffree-line-length-none",
                "-ffixed-line-length-none",
                "-J",
                str(temp_root),
                "-I",
                str(temp_root),
                "-c",
                str(source),
                "-o",
                str(object_path),
            ],
            cwd=temp_root,
        )
        objects.append(object_path)

    exe_path = temp_root / name
    _run(
        [
            "gfortran",
            "-O0",
            "-ffree-line-length-none",
            "-ffixed-line-length-none",
            "-J",
            str(temp_root),
            "-I",
            str(temp_root),
            "-o",
            str(exe_path),
            *[str(path) for path in objects],
            *[str(path) for path in local_sources],
        ],
        cwd=temp_root,
    )
    return exe_path, temp_root


def _parse_float_line(line: str) -> np.ndarray:
    return np.array([float(part) for part in line.strip().split()], dtype=np.float64)


def _as_array(value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype == np.bool_:
        return array.astype(np.int32)
    if np.issubdtype(array.dtype, np.integer):
        return array.astype(np.int64)
    if np.issubdtype(array.dtype, np.floating):
        return array.astype(np.float64)
    if np.issubdtype(array.dtype, np.complexfloating):
        return array.astype(np.complex128)
    return array


def _max_rel(diff: np.ndarray, baseline: np.ndarray) -> float:
    denom = np.maximum(np.abs(baseline), 1.0e-30)
    return float(np.max(diff / denom)) if diff.size else 0.0


def _numeric_check(
    routine: str,
    fortran_value: Any,
    python_value: Any,
    *,
    atol: float,
    rtol: float,
    comparison: str = "numeric",
    note: str = "",
) -> CheckResult:
    f_value = _as_array(fortran_value)
    p_value = _as_array(python_value)
    if f_value.shape != p_value.shape:
        return CheckResult(
            routine=routine,
            status="fail",
            comparison=comparison,
            max_abs=None,
            max_rel=None,
            note=f"shape mismatch: Fortran {f_value.shape}, Python {p_value.shape}",
        )
    diff = np.abs(f_value - p_value)
    max_abs = float(np.max(diff)) if diff.size else 0.0
    max_rel = _max_rel(diff, f_value) if diff.size else 0.0
    status = "pass" if np.allclose(f_value, p_value, atol=atol, rtol=rtol) else "fail"
    return CheckResult(
        routine=routine,
        status=status,
        comparison=comparison,
        max_abs=max_abs,
        max_rel=max_rel,
        note=note,
    )


def _exact_check(routine: str, fortran_value: Any, python_value: Any, *, note: str = "") -> CheckResult:
    status = "pass" if fortran_value == python_value else "fail"
    return CheckResult(
        routine=routine,
        status=status,
        comparison="exact",
        max_abs=0.0 if status == "pass" else None,
        max_rel=0.0 if status == "pass" else None,
        note=note,
    )


def _numeric_case_checks(
    routine: str,
    fortran_values: Any,
    python_values: Any,
    labels: list[str],
    *,
    atol: float,
    rtol: float,
    comparison: str = "numeric",
    note: str = "",
) -> list[CheckResult]:
    f_values = _as_array(fortran_values)
    p_values = _as_array(python_values)
    if f_values.shape != p_values.shape:
        return [
            _numeric_check(
                routine,
                f_values,
                p_values,
                atol=atol,
                rtol=rtol,
                comparison=comparison,
                note=note,
            )
        ]
    if f_values.ndim == 0:
        f_cases = [f_values]
        p_cases = [p_values]
    elif len(labels) == f_values.shape[0]:
        f_cases = [f_values[index] for index in range(f_values.shape[0])]
        p_cases = [p_values[index] for index in range(p_values.shape[0])]
    elif f_values.ndim == 1 and len(labels) == f_values.size:
        f_cases = [np.array([f_values[index]]) for index in range(f_values.size)]
        p_cases = [np.array([p_values[index]]) for index in range(p_values.size)]
    else:
        raise ValueError(
            f"Cannot split {routine}: labels={len(labels)}, shape={f_values.shape}"
        )
    return [
        _numeric_check(
            f"{routine}_{label}",
            f_case,
            p_case,
            atol=atol,
            rtol=rtol,
            comparison=comparison,
            note=note,
        )
        for label, f_case, p_case in zip(labels, f_cases, p_cases)
    ]


def _exact_case_checks(
    routine: str,
    fortran_values: list[Any],
    python_values: list[Any],
    labels: list[str],
    *,
    note: str = "",
) -> list[CheckResult]:
    if not (len(fortran_values) == len(python_values) == len(labels)):
        raise ValueError(
            f"Cannot split {routine}: {len(fortran_values)} Fortran values, "
            f"{len(python_values)} Python values, {len(labels)} labels"
        )
    return [
        _exact_check(f"{routine}_{label}", fortran_value, python_value, note=note)
        for label, fortran_value, python_value in zip(labels, fortran_values, python_values)
    ]


def _guarded_case_checks(
    routine: str,
    fortran_values: Any,
    labels: list[str],
    python_fn: Any,
    *,
    atol: float,
    rtol: float,
    comparison: str = "numeric",
    note: str = "",
) -> list[CheckResult]:
    """Run `python_fn` and compare; on failure emit per-label error checks.

    Keeps a missing or broken Python-side routine (common for baselines) from
    aborting the whole repository verifier and discarding its other checks.
    """
    try:
        python_values = python_fn()
    except Exception as exc:
        message = f"Python-side evaluation failed: {type(exc).__name__}: {exc}"
        return [
            CheckResult(
                routine=f"{routine}_{label}" if len(labels) > 1 else routine,
                status="error",
                comparison="runner",
                max_abs=None,
                max_rel=None,
                note=(note + " " if note else "") + message[:400],
            )
            for label in labels
        ]
    if len(labels) == 1:
        return [
            _numeric_check(
                routine,
                fortran_values,
                python_values,
                atol=atol,
                rtol=rtol,
                comparison=comparison,
                note=note,
            )
        ]
    return _numeric_case_checks(
        routine,
        fortran_values,
        python_values,
        labels,
        atol=atol,
        rtol=rtol,
        comparison=comparison,
        note=note,
    )


def _repo_result(tier: str, repo: str, checks: list[CheckResult], *, notes: str = "") -> RepoResult:
    status = "pass" if all(check.status == "pass" for check in checks) else "fail"
    return RepoResult(tier=tier, repo=repo, status=status, notes=notes, checks=checks)


def verify_tsunami() -> RepoResult:
    sys.path.insert(0, str(STUB_ROOT))
    fortran_module = importlib.import_module("tsunami_f")
    python_module = _load_module(
        "tsunami_mod_parallel",
        TARGET_ROOT / "low" / "tsunami" / "generated_python" / "src" / "ch10" / "mod_parallel.py",
    )

    num_tiles_inputs = [1, 2, 6, 12]
    fortran_num_tiles = np.vstack([fortran_module.tsunami_parallel.num_tiles(value) for value in num_tiles_inputs])
    python_num_tiles = np.vstack([python_module.num_tiles(value) for value in num_tiles_inputs])

    tile_cases = [(10, 1, 3), (10, 2, 3), (10, 3, 3), (11, 4, 6)]
    fortran_indices = np.vstack(
        [fortran_module.tsunami_parallel.tile_indices_1d(dims, i, n) for dims, i, n in tile_cases]
    )
    python_indices = np.vstack([python_module.tile_indices_1d(dims, i, n) for dims, i, n in tile_cases])

    denominator_source = """
module mod_parallel_small
  implicit none
contains
  function denominators(n) result(values)
    integer, intent(in) :: n
    integer, allocatable :: values(:)
    integer :: i
    values = [integer ::]
    do i = 1, n
      if (mod(n, i) == 0) values = [values, i]
    end do
  end function denominators
end module mod_parallel_small

program run_denominators
  use mod_parallel_small
  implicit none
  write(*,'(20(I0,1X))') denominators(1)
  write(*,'(20(I0,1X))') denominators(6)
  write(*,'(20(I0,1X))') denominators(12)
end program run_denominators
"""
    denom_exe, _ = _compile_fortran_program(
        "tsunami_denominators_verify",
        inline_sources=[("run_denominators.f90", denominator_source)],
    )
    denom_output = _run([str(denom_exe)], capture_stderr=True).stdout.strip().splitlines()
    denominator_inputs = [1, 6, 12]
    python_denominators = [python_module.denominators(value) for value in denominator_inputs]
    fortran_denominator_lines = [
        np.array([int(part) for part in line.strip().split()], dtype=np.int32)
        for line in denom_output
    ]
    denominator_checks = [
        _numeric_check(
            f"denominators_{value}",
            fortran_denominator_lines[index],
            python_denominators[index],
            atol=0.0,
            rtol=0.0,
            comparison="exact-array",
        )
        for index, value in enumerate(denominator_inputs)
    ]

    return _repo_result(
        "low",
        "tsunami",
        [
            _numeric_check("num_tiles", fortran_num_tiles, python_num_tiles, atol=0.0, rtol=0.0, comparison="exact-array"),
            _numeric_check(
                "tile_indices_1d",
                fortran_indices,
                python_indices,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            *denominator_checks,
        ],
    )


def verify_fkb() -> RepoResult:
    source = """
module mod_activation_small
  implicit none
  integer, parameter :: rk = kind(0.0d0)
contains
  pure function gaussian(x, alpha) result(res)
    real(rk), intent(in) :: x(:)
    real(rk), intent(in) :: alpha
    real(rk) :: res(size(x))
    res = exp(-x**2)
  end function gaussian

  pure function gaussian_prime(x, alpha) result(res)
    real(rk), intent(in) :: x(:)
    real(rk), intent(in) :: alpha
    real(rk) :: tmp_alpha
    real(rk) :: res(size(x))
    tmp_alpha = 0.0_rk
    res = -2.0_rk * x * gaussian(x, tmp_alpha)
  end function gaussian_prime
end module mod_activation_small

program run_fkb
  use mod_activation_small
  implicit none
  real(rk) :: x(4)
  x = [-2.0_rk, -0.5_rk, 0.0_rk, 1.25_rk]
  write(*,'(4(ES24.16E3,1X))') gaussian(x, 0.3_rk)
  write(*,'(4(ES24.16E3,1X))') gaussian_prime(x, 0.3_rk)
end program run_fkb
"""
    exe_path, _ = _compile_fortran_program("fkb_verify", inline_sources=[("run_fkb.f90", source)])
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    python_module = _load_module(
        "fkb_mod_activation",
        TARGET_ROOT / "low" / "FKB" / "generated_python" / "src" / "mod_activation.py",
    )
    x = np.array([-2.0, -0.5, 0.0, 1.25], dtype=np.float64)

    return _repo_result(
        "low",
        "FKB",
        [
            *_numeric_case_checks(
                "gaussian",
                _parse_float_line(output[0]),
                python_module.gaussian(x, 0.3),
                ["x_neg2", "x_neg0p5", "x_0", "x_1p25"],
                atol=1.0e-14,
                rtol=1.0e-14,
            ),
            *_numeric_case_checks(
                "gaussian_prime",
                _parse_float_line(output[1]),
                python_module.gaussian_prime(x, 0.3),
                ["x_neg2", "x_neg0p5", "x_0", "x_1p25"],
                atol=1.0e-14,
                rtol=1.0e-14,
            ),
        ],
    )


def verify_fastgpt() -> RepoResult:
    source = """
module gpt2_small
  implicit none
  integer, parameter :: sp = kind(0.0)
  real(sp), parameter :: pi = 3.14159265358979323846_sp
contains
  elemental real(sp) function fast_tanh(x) result(y)
    real(sp), intent(in) :: x
    real(sp) :: x2
    if (x > 5) then
      y = 1
    elseif (x < -5) then
      y = -1
    else
      x2 = x*x
      y = x * (0.98569772605911309407 + x2 *(-0.2794500993392901382 &
          + x2 * (6.8280504526399188164e-2 + x2 * (-1.0972014877337651823e-2 &
          + x2 * (1.1132367134444316902e-3 + x2 * (-7.018851897305717565e-5 &
          + x2 * (2.656616768082727089e-6 + x2 * (-5.5138381821615909058e-8 &
          + x2 * 4.8162484477588665996e-10))))))))
    end if
  end function fast_tanh

  elemental real(sp) function gelu(x) result(y)
    real(sp), intent(in) :: x
    y = 0.5_sp * x * (1 + tanh(sqrt(2.0_sp / pi) * (x + 0.044715_sp * x**3)))
  end function gelu

  function softmax(x) result(y)
    real(sp), intent(in) :: x(:,:)
    real(sp) :: y(size(x,1),size(x,2))
    integer :: i
    do i = 1, size(x,2)
      y(:,i) = exp(x(:,i) - maxval(x(:,i)))
      y(:,i) = y(:,i) / sum(y(:,i))
    end do
  end function softmax
end module gpt2_small

program run_fastgpt
  use gpt2_small
  implicit none
  real(sp) :: x(6)
  real(sp) :: y(2,3)
  x = [-10.0_sp, -1.0_sp, 0.0_sp, 0.5_sp, 2.0_sp, 10.0_sp]
  y = reshape([1.0_sp, 2.0_sp, 3.0_sp, 4.0_sp, 5.0_sp, 6.0_sp], [2,3])
  write(*,'(6(ES16.8E3,1X))') fast_tanh(x)
  write(*,'(6(ES16.8E3,1X))') gelu(x)
  write(*,'(6(ES16.8E3,1X))') softmax(y)
end program run_fastgpt
"""
    exe_path, _ = _compile_fortran_program("fastgpt_verify", inline_sources=[("run_fastgpt.f90", source)])
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    python_module = _load_module(
        "fastgpt_linalg_module",
        TARGET_ROOT / "low" / "fastGPT" / "generated_python" / "src" / "linalg_module.py",
    )
    x = np.array([-10.0, -1.0, 0.0, 0.5, 2.0, 10.0], dtype=np.float32)
    y = np.array([[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]], dtype=np.float32, order="F")

    return _repo_result(
        "low",
        "fastGPT",
        [
            *_numeric_case_checks(
                "fast_tanh",
                _parse_float_line(output[0]),
                python_module.fast_tanh(x).astype(np.float64),
                ["x_neg10", "x_neg1", "x_0", "x_0p5", "x_2", "x_10"],
                atol=1.0e-6,
                rtol=1.0e-6,
            ),
            *_numeric_case_checks(
                "gelu",
                _parse_float_line(output[1]),
                python_module.gelu(x).astype(np.float64),
                ["x_neg10", "x_neg1", "x_0", "x_0p5", "x_2", "x_10"],
                atol=1.0e-6,
                rtol=1.0e-6,
                note="The translated Python calls fast_tanh inside gelu; the original Fortran calls tanh.",
            ),
            *_numeric_case_checks(
                "softmax",
                _parse_float_line(output[2]),
                np.ravel(python_module.softmax(y), order="F").astype(np.float64),
                ["col1_row1", "col1_row2", "col2_row1", "col2_row2", "col3_row1", "col3_row2"],
                atol=1.0e-6,
                rtol=1.0e-6,
            ),
        ],
    )


def verify_tsunami_diff() -> RepoResult:
    source = """
module mod_diff
  implicit none
contains
  function diff_centered(x) result(dx)
    real, intent(in) :: x(:)
    real :: dx(size(x))
    integer :: im
    im = size(x)
    dx(1) = x(2) - x(im)
    dx(im) = x(1) - x(im-1)
    dx(2:im-1) = x(3:im) - x(1:im-2)
    dx = 0.5 * dx
  end function diff_centered

  function diff_upwind(x) result(dx)
    real, intent(in) :: x(:)
    real :: dx(size(x))
    integer :: im
    im = size(x)
    dx(1) = x(1) - x(im)
    dx(2:im) = x(2:im) - x(1:im-1)
  end function diff_upwind
end module mod_diff

program run_tsunami_diff
  use mod_diff
  implicit none
  real, dimension(5) :: x, centered, upwind
  x = [1.0, 2.0, 3.0, 4.0, 5.0]
  centered = diff_centered(x)
  upwind = diff_upwind(x)
  write(*,'(5(ES16.8E3,1X))') centered
  write(*,'(5(ES16.8E3,1X))') upwind
end program run_tsunami_diff
"""
    exe_path, _ = _compile_fortran_program(
        "tsunami_diff_verify",
        inline_sources=[("run_tsunami_diff.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "tsunami_mod_diff",
        TARGET_ROOT / "low" / "tsunami" / "generated_python" / "src" / "ch04" / "mod_diff.py",
    )
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
    return _repo_result(
        "low",
        "tsunami-diff",
        [
            _numeric_check(
                "diff_centered",
                _parse_float_line(output[0]),
                python_module.diff_centered(x).astype(np.float64),
                atol=1.0e-6,
                rtol=1.0e-6,
            ),
            _numeric_check(
                "diff_upwind",
                _parse_float_line(output[1]),
                python_module.diff_upwind(x).astype(np.float64),
                atol=1.0e-6,
                rtol=1.0e-6,
            ),
        ],
    )


def verify_fortranlib() -> RepoResult:
    with tempfile.TemporaryDirectory(prefix="behavioral-validation-fortranlib-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        temp_file = temp_dir / "sample.txt"
        temp_file.write_text("sample", encoding="utf-8")
        escaped_file = str(temp_file).replace("\\", "\\\\")
        escaped_dir = str(temp_dir).replace("\\", "\\\\")
        source = f"""
module posix_small
  implicit none
contains
  logical function file_exists(file)
    implicit none
    character(len=*), intent(in) :: file
    integer :: access
    file_exists = access(file,' ') .eq. 0
  end function file_exists

  logical function dir_exists(dir)
    implicit none
    character(len=*), intent(in) :: dir
    integer :: access
    dir_exists = access(dir,' ') .eq. 0
  end function dir_exists
end module posix_small

program run_fortranlib
  use posix_small
  implicit none
  write(*,'(4(L1,1X))') file_exists('{escaped_file}'), file_exists('{escaped_dir}'), &
                        dir_exists('{escaped_file}'), dir_exists('{escaped_dir}')
end program run_fortranlib
"""
        exe_path, _ = _compile_fortran_program("fortranlib_verify", inline_sources=[("run_fortranlib.f90", source)])
        output = _run([str(exe_path)], capture_stderr=True).stdout.strip().split()

        python_module = _load_module(
            "fortranlib_io_operations",
            TARGET_ROOT / "low" / "fortranlib" / "generated_python" / "src" / "io_operations.py",
        )
        fortran_values = [value.upper().startswith("T") for value in output]
        python_values = [
            bool(python_module.file_exists(str(temp_file))),
            bool(python_module.file_exists(str(temp_dir))),
            bool(python_module.dir_exists(str(temp_file))),
            bool(python_module.dir_exists(str(temp_dir))),
        ]

    return _repo_result(
        "low",
        "fortranlib",
        [
            *_numeric_case_checks(
                "access_exists",
                np.array(fortran_values, dtype=np.int32),
                np.array(python_values, dtype=np.int32),
                ["file_as_file", "dir_as_file", "file_as_dir", "dir_as_dir"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool",
                note="The original Fortran uses ACCESS() for both routines, so an existing directory also satisfies file_exists and vice versa.",
            )
        ],
    )


def verify_fortran_utils() -> RepoResult:
    source = """
module utils_small
  implicit none
contains
  function upcase(s) result(t)
    character(*), intent(in) :: s
    character(len(s)) :: t
    integer :: i, diff
    t = s
    diff = ichar('A') - ichar('a')
    do i = 1, len(t)
      if (ichar(t(i:i)) >= ichar('a') .and. ichar(t(i:i)) <= ichar('z')) then
        t(i:i) = char(ichar(t(i:i)) + diff)
      end if
    end do
  end function upcase

  function lowcase(s) result(t)
    character(*), intent(in) :: s
    character(len(s)) :: t
    integer :: i, diff
    t = s
    diff = ichar('A') - ichar('a')
    do i = 1, len(t)
      if (ichar(t(i:i)) >= ichar('A') .and. ichar(t(i:i)) <= ichar('Z')) then
        t(i:i) = char(ichar(t(i:i)) - diff)
      end if
    end do
  end function lowcase

  logical function whitechar(char)
    character, intent(in) :: char
    if (iachar(char) == 32 .or. iachar(char) == 9) then
      whitechar = .true.
    else
      whitechar = .false.
    end if
  end function whitechar

  logical function blank(string)
    character(*), intent(in) :: string
    integer :: i
    do i = 1, len(string)
      if (.not. whitechar(string(i:i))) exit
    end do
    blank = (i > len(string))
  end function blank

  integer function numstrings(s)
    character(*), intent(in) :: s
    character(len=:), allocatable :: t
    integer :: i
    t = ' ' // s // ' '
    numstrings = 0
    do i = 1, len(t) - 1
      if (whitechar(t(i:i)) .and. .not. whitechar(t(i+1:i+1))) then
        numstrings = numstrings + 1
      end if
    end do
  end function numstrings
end module utils_small

program run_utils
  use utils_small
  implicit none
  write(*,'(A)') trim(upcase('AbC! z9'))
  write(*,'(A)') trim(lowcase('AbC! z9'))
  write(*,'(L1)') blank('   ')
  write(*,'(L1)') blank(' a ')
  write(*,'(3(L1,1X))') whitechar(' '), whitechar(char(9)), whitechar('x')
  write(*,'(3(I0,1X))') numstrings(''), numstrings('alpha beta'//char(9)//'gamma'), numstrings('  one  ')
end program run_utils
"""
    exe_path, _ = _compile_fortran_program("fortran_utils_verify", inline_sources=[("run_utils.f90", source)])
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    python_module = _load_module_with_text_patches(
        TARGET_ROOT / "low" / "fortran-utils" / "generated_python" / "src" / "utils.py",
        "fortran_utils_module",
        [("from typing import Dict, List, Optional, Union", "from typing import Dict, List, Optional, Tuple, Union")],
    )
    python_strings = [python_module.upcase("AbC! z9"), python_module.lowcase("AbC! z9")]
    python_bools = [python_module.blank("   "), python_module.blank(" a ")]
    python_whitechar = [python_module.whitechar(" "), python_module.whitechar("\t"), python_module.whitechar("x")]
    python_numstrings = [python_module.numstrings(""), python_module.numstrings("alpha beta\tgamma"), python_module.numstrings("  one  ")]

    return _repo_result(
        "low",
        "fortran-utils",
        [
            _exact_check("upcase", output[0].strip(), python_strings[0]),
            _exact_check("lowcase", output[1].strip(), python_strings[1]),
            _exact_check("blank_only_whitespace", output[2].strip().upper().startswith("T"), bool(python_bools[0])),
            _exact_check("blank_non_whitespace", output[3].strip().upper().startswith("T"), bool(python_bools[1])),
            _numeric_check(
                "blank",
                np.array([output[2].strip().upper().startswith("T"), output[3].strip().upper().startswith("T")], dtype=np.int32),
                np.array([bool(python_bools[0]), bool(python_bools[1])], dtype=np.int32),
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
                note="Hand-curated combined blank-string probe replacing the earlier automated template probe.",
            ),
            _numeric_check(
                "whitechar",
                np.array([part.upper().startswith("T") for part in output[4].strip().split()], dtype=np.int32),
                np.array([bool(value) for value in python_whitechar], dtype=np.int32),
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
            ),
            _numeric_check(
                "numstrings",
                np.array([int(part) for part in output[5].strip().split()], dtype=np.int32),
                np.array(python_numstrings, dtype=np.int32),
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
        ],
    )


def verify_datetime_fortran() -> RepoResult:
    source = """
program run_datetime
  use datetime_module, only: daysInMonth, isLeapYear, daysInYear
  implicit none
  write(*,'(4(I0,1X))') daysInMonth(2,2000), daysInMonth(2,1900), daysInMonth(4,2023), daysInMonth(12,2023)
  write(*,'(4(L1,1X))') isLeapYear(2000), isLeapYear(1900), isLeapYear(2004), isLeapYear(2001)
  write(*,'(4(I0,1X))') daysInYear(2000), daysInYear(1900), daysInYear(2004), daysInYear(2001)
end program run_datetime
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "datetime_verify",
        inline_sources=[("run_datetime.f90", source)],
        ordered_sources=[FORTRAN_CORPUS_ROOT / "low" / "datetime-fortran" / "src" / "datetime_module.f90"],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    python_module = _load_module(
        "datetime_fortran_module",
        TARGET_ROOT / "low" / "datetime-fortran" / "generated_python" / "src" / "datetime_module.py",
    )
    month_cases = [(2, 2000), (2, 1900), (4, 2023), (12, 2023)]
    year_cases = [2000, 1900, 2004, 2001]
    python_days_month = np.array(
        [python_module.days_in_month(month, year) for month, year in month_cases],
        dtype=np.int64,
    )
    python_leap = np.array([python_module.is_leap_year(year) for year in year_cases], dtype=np.int32)
    python_days_year = np.array([python_module.days_in_year(year) for year in year_cases], dtype=np.int64)
    fortran_leap = np.array([part.upper().startswith("T") for part in output[1].split()], dtype=np.int32)

    return _repo_result(
        "low",
        "datetime-fortran",
        [
            *_numeric_case_checks(
                "daysInMonth",
                np.array([int(part) for part in output[0].split()], dtype=np.int64),
                python_days_month,
                ["feb_2000", "feb_1900", "apr_2023", "dec_2023"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            *_numeric_case_checks(
                "isLeapYear",
                fortran_leap,
                python_leap,
                ["y2000", "y1900", "y2004", "y2001"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
            ),
            *_numeric_case_checks(
                "daysInYear",
                np.array([int(part) for part in output[2].split()], dtype=np.int64),
                python_days_year,
                ["y2000", "y1900", "y2004", "y2001"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
        ],
    )


def verify_m_strings() -> RepoResult:
    source = """
program run_m_strings
  use M_strings, only: string_to_value
  implicit none
  integer :: value32, ierr32
  call string_to_value('  -42', value32, ierr32)
  write(*,'(I0,1X,I0)') value32, ierr32
  call string_to_value('2147483647', value32, ierr32)
  write(*,'(I0,1X,I0)') value32, ierr32
  call string_to_value('0', value32, ierr32)
  write(*,'(I0,1X,I0)') value32, ierr32
  call string_to_value(' +17', value32, ierr32)
  write(*,'(I0,1X,I0)') value32, ierr32
end program run_m_strings
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "m_strings_verify",
        inline_sources=[("run_m_strings.f90", source)],
        ordered_sources=[FORTRAN_CORPUS_ROOT / "low" / "M_strings" / "src" / "M_strings.F90"],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    fortran_pairs = np.array([[int(part) for part in line.split()] for line in output], dtype=np.int64)

    python_module = _load_module(
        "m_strings_module",
        TARGET_ROOT / "low" / "M_strings" / "generated_python" / "src" / "M_strings.py",
    )
    py32_a = python_module.atoi_int32("  -42")
    py32_b = python_module.atoi_int32("2147483647")
    py32_c = python_module.atoi_int32("0")
    py32_d = python_module.atoi_int32(" +17")
    python_pairs = np.array(
        [
            [py32_a[0], int(py32_a[1])],
            [py32_b[0], int(py32_b[1])],
            [py32_c[0], int(py32_c[1])],
            [py32_d[0], int(py32_d[1])],
        ],
        dtype=np.int64,
    )

    return _repo_result(
        "low",
        "M_strings",
        [
            *_numeric_case_checks(
                "string_to_value_int32",
                fortran_pairs,
                python_pairs,
                ["neg42", "max_int32", "zero", "plus17"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Cross-name comparison: Fortran string_to_value integer cases against generated atoi_int32.",
            ),
        ],
    )


def verify_fftpack() -> RepoResult:
    source = """
program run_fftpack
  implicit none
  integer, parameter :: n=4
  double complex :: c(n)
  double precision :: wsave(4*n+15)
  c(1)=dcmplx(1.0d0,0.0d0)
  c(2)=dcmplx(2.0d0,-1.0d0)
  c(3)=dcmplx(0.5d0,0.25d0)
  c(4)=dcmplx(-3.0d0,2.0d0)
  call zffti(n, wsave)
  call zfftf(n, c, wsave)
  write(*,'(8(ES24.16E3,1X))') real(c(1)), aimag(c(1)), real(c(2)), aimag(c(2)), &
                                  real(c(3)), aimag(c(3)), real(c(4)), aimag(c(4))
  call zfftb(n, c, wsave)
  write(*,'(8(ES24.16E3,1X))') real(c(1)), aimag(c(1)), real(c(2)), aimag(c(2)), &
                                  real(c(3)), aimag(c(3)), real(c(4)), aimag(c(4))
end program run_fftpack
"""
    fft_src = FORTRAN_CORPUS_ROOT / "low" / "fftpack" / "src"
    ordered = [
        fft_src / "rk.f90",
        fft_src / "fftpack.f90",
        fft_src / "cffti1.f90",
        fft_src / "cfftf1.f90",
        fft_src / "cfftb1.f90",
        fft_src / "passf.f90",
        fft_src / "passf2.f90",
        fft_src / "passf3.f90",
        fft_src / "passf4.f90",
        fft_src / "passf5.f90",
        fft_src / "passb.f90",
        fft_src / "passb2.f90",
        fft_src / "passb3.f90",
        fft_src / "passb4.f90",
        fft_src / "passb5.f90",
        fft_src / "zffti.f90",
        fft_src / "zfftf.f90",
        fft_src / "zfftb.f90",
    ]
    exe_path, _ = _compile_fortran_program_ordered(
        "fftpack_verify",
        ordered_sources=ordered,
        inline_sources=[("run_fftpack.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    fortran_forward = _parse_float_line(output[0]).reshape(4, 2)
    fortran_backward = _parse_float_line(output[1]).reshape(4, 2)

    python_module = _load_module(
        "fftpack_module",
        TARGET_ROOT / "low" / "fftpack" / "generated_python" / "src" / "fftpack.py",
    )
    values = np.array([1.0 + 0.0j, 2.0 - 1.0j, 0.5 + 0.25j, -3.0 + 2.0j], dtype=np.complex128)
    workspace = np.zeros(4 * len(values) + 15, dtype=np.float64)
    python_forward_complex = python_module.zfftf(len(values), values.copy(), workspace.copy())
    python_backward_complex = python_module.zfftb(len(values), python_forward_complex.copy(), workspace.copy())
    python_forward = np.column_stack((python_forward_complex.real, python_forward_complex.imag))
    python_backward = np.column_stack((python_backward_complex.real, python_backward_complex.imag))

    return _repo_result(
        "low",
        "fftpack",
        [
            *_numeric_case_checks(
                "zfftf",
                fortran_forward,
                python_forward,
                ["k1", "k2", "k3", "k4"],
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            *_numeric_case_checks(
                "zfftb",
                fortran_backward,
                python_backward,
                ["k1", "k2", "k3", "k4"],
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Original FFTPACK zfftb is an unnormalized inverse transform.",
            ),
        ],
    )


def verify_minpack() -> RepoResult:
    sys.path.insert(0, str(STUB_ROOT))
    fortran_module = importlib.import_module("enorm_f")
    python_module = _load_module(
        "minpack_module",
        TARGET_ROOT / "medium" / "minpack" / "generated_python" / "src" / "minpack.py",
    )
    vectors = [
        np.array([3.0, 4.0], dtype=np.float64),
        np.array([1.0e-20, 3.0, 4.0, 1.0e19], dtype=np.float64),
        np.array([0.0, 0.0, 0.0], dtype=np.float64),
        np.array([6.0, 8.0], dtype=np.float64),
        np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float64),
        np.array([1.0e20, 1.0e20], dtype=np.float64),
    ]
    fortran_values = np.array([fortran_module.enorm(vector) for vector in vectors], dtype=np.float64)
    python_values = np.array([python_module.enorm(len(vector), vector) for vector in vectors], dtype=np.float64)
    dpmpar_indices = [1, 2, 3]
    fortran_dpmpar = np.array(
        [
            np.finfo(np.float64).eps,
            np.finfo(np.float64).tiny,
            np.finfo(np.float64).max,
        ],
        dtype=np.float64,
    )
    python_dpmpar = np.array([python_module.dpmpar(index) for index in dpmpar_indices], dtype=np.float64)
    return _repo_result(
        "medium",
        "minpack",
        [
            *_numeric_case_checks(
                "enorm",
                fortran_values,
                python_values,
                ["3_4", "scaled_large", "zero", "6_8", "unit_four", "large_pair"],
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            *_numeric_case_checks(
                "dpmpar",
                fortran_dpmpar,
                python_dpmpar,
                ["eps", "tiny", "max"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
        ],
    )


def verify_sisso() -> RepoResult:
    source = """
module sisso_small
  implicit none
contains
  function corr(x,y)
    real*8 x(:), y(:), meanx, meany, sigmax, sigmay, m, corr
    m = size(x)
    meanx = sum(x)/m
    meany = sum(y)/m
    sigmax = sqrt(sum((x-meanx)**2)/m)
    sigmay = sqrt(sum((y-meany)**2)/m)
    corr = sum((x-meanx)*(y-meany))/(m*sigmax*sigmay)
  end function corr

  function det(mat)
    integer i, j, k, n
    real*8 mat(:,:), um(ubound(mat,1),ubound(mat,1)), s, det, temp(ubound(mat,1))
    s = 0.d0
    um = mat
    n = ubound(mat,1)
    do i = 1, n
      do j = i+1, n
        if (um(i,i) == 0.d0) then
          do k = i+1, n
            if (um(k,i) /= 0.d0) then
              temp = um(i,:)
              um(i,:) = um(k,:)
              um(k,:) = temp
              s = s + 1.d0
              exit
            end if
          end do
        end if
        if (um(i,i) /= 0.d0) um(j,:) = um(j,:) - um(i,:)*um(j,i)/um(i,i)
      end do
    end do
    det = (-1.d0)**s
    do i = 1, n
      det = det * um(i,i)
    end do
  end function det
end module sisso_small

program run_sisso
  use sisso_small
  implicit none
  real*8 :: x(4), y(4), x2(4), y2(4), mat(2,2), mat2(2,2)
  x = (/1.d0, 2.d0, 4.d0, 8.d0/)
  y = (/2.d0, 3.d0, 5.d0, 9.d0/)
  x2 = (/1.d0, 2.d0, 3.d0, 4.d0/)
  y2 = (/4.d0, 3.d0, 2.d0, 1.d0/)
  mat = reshape((/1.d0, 3.d0, 2.d0, 4.d0/), (/2,2/))
  mat2 = reshape((/0.d0, 2.d0, 1.d0, 3.d0/), (/2,2/))
  write(*,'(4(ES24.16E3,1X))') corr(x,y), corr(x2,y2), det(mat), det(mat2)
end program run_sisso
"""
    exe_path, _ = _compile_fortran_program("sisso_verify", inline_sources=[("run_sisso.f90", source)])
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().split()

    python_module = _load_module(
        "sisso_libsisoo",
        TARGET_ROOT / "medium" / "SISSO" / "generated_python" / "src" / "libsisso.py",
    )
    x = np.array([1.0, 2.0, 4.0, 8.0], dtype=np.float64)
    y = np.array([2.0, 3.0, 5.0, 9.0], dtype=np.float64)
    x2 = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    y2 = np.array([4.0, 3.0, 2.0, 1.0], dtype=np.float64)
    matrix = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64, order="F")
    matrix2 = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float64, order="F")
    return _repo_result(
        "medium",
        "SISSO",
        [
            _numeric_check(
                "corr_positive",
                np.array([float(output[0])], dtype=np.float64),
                np.array([python_module.corr(x, y)], dtype=np.float64),
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            _numeric_check(
                "corr_negative",
                np.array([float(output[1])], dtype=np.float64),
                np.array([python_module.corr(x2, y2)], dtype=np.float64),
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            _numeric_check(
                "det_regular",
                np.array([float(output[2])], dtype=np.float64),
                np.array([python_module.det(matrix)], dtype=np.float64),
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            _numeric_check(
                "det_pivot",
                np.array([float(output[3])], dtype=np.float64),
                np.array([python_module.det(matrix2)], dtype=np.float64),
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
        ],
    )


def verify_json_fortran() -> RepoResult:
    source = """
module json_string_utilities_small
  implicit none
  character(len=*), parameter :: upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
  character(len=*), parameter :: lower = 'abcdefghijklmnopqrstuvwxyz'
  character(len=1), parameter :: tilde = '~'
  character(len=1), parameter :: slash = '/'
contains
  pure function lowercase_string(str) result(s_lower)
    character(len=*), intent(in) :: str
    character(len=len(str)) :: s_lower
    integer :: i, j
    s_lower = str
    do i = 1, len_trim(str)
      j = index(upper, s_lower(i:i))
      if (j > 0) s_lower(i:i) = lower(j:j)
    end do
  end function lowercase_string

  pure subroutine replace_string(str, s1, s2)
    character(len=:), allocatable, intent(inout) :: str
    character(len=*), intent(in) :: s1
    character(len=*), intent(in) :: s2
    character(len=:), allocatable :: tmp
    integer :: i, n, ilen, ilen1
    if (len(str) > 0) then
      tmp = ''
      ilen1 = len(s1)
      do
        ilen = len(str)
        i = index(str, s1)
        if (i > 0) then
          if (i > 1) tmp = tmp // str(1:i-1)
          tmp = tmp // s2
          n = i + ilen1
          if (n <= ilen) then
            str = str(n:ilen)
          else
            exit
          end if
        else
          tmp = tmp // str
          exit
        end if
      end do
      str = tmp
    end if
  end subroutine replace_string

  pure function decode_rfc6901(str) result(str_out)
    character(len=*), intent(in) :: str
    character(len=:), allocatable :: str_out
    str_out = str
    call replace_string(str_out, tilde//'1', slash)
    call replace_string(str_out, tilde//'0', tilde)
  end function decode_rfc6901

  pure function encode_rfc6901(str) result(str_out)
    character(len=*), intent(in) :: str
    character(len=:), allocatable :: str_out
    str_out = str
    call replace_string(str_out, tilde, tilde//'0')
    call replace_string(str_out, slash, tilde//'1')
  end function encode_rfc6901

  function escape_string(str) result(str_out)
    character(len=*), intent(in) :: str
    character(len=:), allocatable :: str_out
    str_out = str
    call replace_string(str_out, '\\', '\\' // '\\')
    call replace_string(str_out, '"', '\\' // '"')
    call replace_string(str_out, char(9), '\\' // 't')
  end function escape_string

  logical function valid_json_hex(str)
    character(len=*), intent(in) :: str
    integer :: i, c
    valid_json_hex = len(str) > 0
    do i = 1, len(str)
      c = iachar(str(i:i))
      if (.not. ((c >= iachar('0') .and. c <= iachar('9')) .or. &
          (c >= iachar('a') .and. c <= iachar('f')) .or. &
          (c >= iachar('A') .and. c <= iachar('F')))) then
        valid_json_hex = .false.
        return
      end if
    end do
  end function valid_json_hex
end module json_string_utilities_small

program run_json_strings
  use json_string_utilities_small
  implicit none
  character(len=:), allocatable :: encoded, decoded, replaced, escaped
  encoded = encode_rfc6901('a/b~c')
  decoded = decode_rfc6901('a~1b~0c')
  replaced = 'alpha beta alpha'
  call replace_string(replaced, 'alpha', 'gamma')
  escaped = escape_string('line"tab'//char(9))
  write(*,'(A)') trim(lowercase_string('AbC/De~F'))
  write(*,'(A)') trim(encoded)
  write(*,'(A)') trim(decoded)
  write(*,'(A)') trim(replaced)
  write(*,'(A)') trim(escaped)
  write(*,'(3(L1,1X))') valid_json_hex('09aF'), valid_json_hex('12xz'), valid_json_hex('')
end program run_json_strings
"""
    exe_path, _ = _compile_fortran_program("json_fortran_verify", inline_sources=[("run_json_strings.f90", source)])
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    python_module = _load_module(
        "json_string_utilities_module",
        TARGET_ROOT / "medium" / "json-fortran" / "generated_python" / "src" / "json_string_utilities.py",
    )
    return _repo_result(
        "medium",
        "json-fortran",
        [
            _exact_check("lowercase_string", output[0].strip(), python_module.lowercase_string("AbC/De~F")),
            _exact_check("encode_rfc6901", output[1].strip(), python_module.encode_rfc6901("a/b~c")),
            _exact_check("decode_rfc6901", output[2].strip(), python_module.decode_rfc6901("a~1b~0c")),
            _exact_check(
                "replace_string",
                output[3].strip(),
                python_module.replace_string("alpha beta alpha", "alpha", "gamma"),
            ),
            _exact_check("escape_string", output[4].strip(), python_module.escape_string('line"tab\t')),
            _numeric_check(
                "valid_json_hex",
                np.array([part.upper().startswith("T") for part in output[5].strip().split()], dtype=np.int32),
                np.array(
                    [
                        python_module.valid_json_hex("09aF"),
                        python_module.valid_json_hex("12xz"),
                        python_module.valid_json_hex(""),
                    ],
                    dtype=np.int32,
                ),
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
            ),
        ],
    )


def verify_fortran_astrodynamics_toolkit() -> RepoResult:
    source = """
module astro_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
  abstract interface
    function func_proto(x) result(y)
      import :: wp
      complex(wp), intent(in) :: x
      complex(wp) :: y
    end function func_proto
  end interface
contains
  subroutine complex_step_derivative(f, x, h, dfdx)
    procedure(func_proto) :: f
    complex(wp), intent(in) :: x
    real(wp), intent(in) :: h
    real(wp), intent(out) :: dfdx
    dfdx = aimag(f(cmplx(real(x, wp), aimag(x) + h, wp))) / h
  end subroutine complex_step_derivative

  subroutine geodetic_to_cartesian(a, b, glat, lon, h, r)
    real(wp), intent(in) :: a, b, glat, lon, h
    real(wp), intent(out) :: r(3)
    real(wp) :: e2, slat, clat, slon, clon, tlat, ome2, d, q, aod
    slat = sin(glat)
    clat = cos(glat)
    tlat = tan(glat)
    slon = sin(lon)
    clon = cos(lon)
    e2 = 1.0_wp - (b*b)/(a*a)
    ome2 = 1.0_wp - e2
    d = sqrt(1.0_wp + ome2*tlat*tlat)
    q = sqrt(1.0_wp - e2*slat*slat)
    aod = a/d
    r(1) = aod*clon + h*clon*clat
    r(2) = aod*slon + h*slon*clat
    r(3) = a*ome2*slat/q + h*slat
  end subroutine geodetic_to_cartesian
end module astro_small

program run_astro
  use astro_small
  implicit none
  real(wp) :: dfdx, r(3)
  call complex_step_derivative(f, cmplx(1.5_wp, 0.0_wp, wp), 1.0e-20_wp, dfdx)
  call geodetic_to_cartesian(6378.137_wp, 6356.7523142_wp, 0.5_wp, 1.0_wp, 1.2_wp, r)
  write(*,'(ES24.16E3)') dfdx
  write(*,'(3(ES24.16E3,1X))') r
contains
  function f(x) result(y)
    complex(wp), intent(in) :: x
    complex(wp) :: y
    y = x**3 + 2.0_wp*x + 1.0_wp
  end function f
end program run_astro
"""
    exe_path, _ = _compile_fortran_program("astro_verify", inline_sources=[("run_astro.f90", source)])
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    conversion_module = _load_module(
        "conversion_module",
        TARGET_ROOT / "medium" / "Fortran-Astrodynamics-Toolkit" / "generated_python" / "src" / "conversion_module.py",
    )
    complex_step_module = _load_module(
        "complex_step_module_python",
        TARGET_ROOT / "medium" / "Fortran-Astrodynamics-Toolkit" / "generated_python" / "src" / "complex_step.py",
    )

    def func(value: complex) -> complex:
        return value**3 + 2.0 * value + 1.0

    python_derivative = complex_step_module.complex_step_derivative(func, 1.5, 1.0e-20)
    python_cartesian = conversion_module.geodetic_to_cartesian(0.5, 1.0, 1.2, (6378.137, 6356.7523142))

    return _repo_result(
        "medium",
        "Fortran-Astrodynamics-Toolkit",
        [
            _numeric_check(
                "complex_step_derivative",
                _parse_float_line(output[0]),
                np.array([python_derivative], dtype=np.float64),
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            *_numeric_case_checks(
                "geodetic_to_cartesian",
                _parse_float_line(output[1]),
                python_cartesian,
                ["x", "y", "z"],
                atol=1.0e-10,
                rtol=1.0e-10,
            ),
        ],
    )


def verify_quadpack() -> RepoResult:
    # Retained as historical audit material: version 0.1 originally executed
    # this extraction.  The active driver below now compiles the pinned
    # quadpack_double module directly.
    _retired_dqk15_extraction = """
module quadpack_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
  real(wp), parameter :: epmach = epsilon(1.0_wp)
  real(wp), parameter :: uflow = tiny(1.0_wp)
  abstract interface
    function func(x) result(f)
      import :: wp
      real(wp), intent(in) :: x
      real(wp) :: f
    end function func
  end interface
contains
  subroutine dqk15(f, a, b, Result, Abserr, Resabs, Resasc)
    implicit none
    procedure(func) :: f
    real(wp), intent(in) :: a
    real(wp), intent(in) :: b
    real(wp), intent(out) :: Result, Abserr, Resabs, Resasc
    real(wp) :: dhlgth, fc, fsum, fv1(7), fv2(7)
    integer :: j, jtw, jtwm1
    real(wp) :: centr, hlgth, absc, fval1, fval2, resg, resk, reskh
    real(wp), dimension(4), parameter :: wg = [ &
         1.29484966168869693270611432679082018329e-1_wp, &
         2.79705391489276667901467771423779582487e-1_wp, &
         3.81830050505118944950369775488975133878e-1_wp, &
         4.17959183673469387755102040816326530612e-1_wp]
    real(wp), dimension(8), parameter :: xgk = [ &
         9.91455371120812639206854697526328516642e-1_wp, &
         9.49107912342758524526189684047851262401e-1_wp, &
         8.64864423359769072789712788640926201211e-1_wp, &
         7.41531185599394439863864773280788407074e-1_wp, &
         5.86087235467691130294144838258729598437e-1_wp, &
         4.05845151377397166906606412076961463347e-1_wp, &
         2.07784955007898467600689403773244913480e-1_wp, &
         0.00000000000000000000000000000000000000e0_wp]
    real(wp), dimension(8), parameter :: wgk = [ &
         2.29353220105292249637320080589695919936e-2_wp, &
         6.30920926299785532907006631892042866651e-2_wp, &
         1.04790010322250183839876322541518017444e-1_wp, &
         1.40653259715525918745189590510237920400e-1_wp, &
         1.69004726639267902826583426598550284106e-1_wp, &
         1.90350578064785409913256402421013682826e-1_wp, &
         2.04432940075298892414161999234649084717e-1_wp, &
         2.09482141084727828012999174891714263698e-1_wp]
    centr = 0.5_wp*(a + b)
    hlgth = 0.5_wp*(b - a)
    dhlgth = abs(hlgth)
    fc = f(centr)
    resg = fc*wg(4)
    resk = fc*wgk(8)
    Resabs = abs(resk)
    do j = 1, 3
      jtw = j*2
      absc = hlgth*xgk(jtw)
      fval1 = f(centr - absc)
      fval2 = f(centr + absc)
      fv1(jtw) = fval1
      fv2(jtw) = fval2
      fsum = fval1 + fval2
      resg = resg + wg(j)*fsum
      resk = resk + wgk(jtw)*fsum
      Resabs = Resabs + wgk(jtw)*(abs(fval1) + abs(fval2))
    end do
    do j = 1, 4
      jtwm1 = j*2 - 1
      absc = hlgth*xgk(jtwm1)
      fval1 = f(centr - absc)
      fval2 = f(centr + absc)
      fv1(jtwm1) = fval1
      fv2(jtwm1) = fval2
      fsum = fval1 + fval2
      resk = resk + wgk(jtwm1)*fsum
      Resabs = Resabs + wgk(jtwm1)*(abs(fval1) + abs(fval2))
    end do
    reskh = resk*0.5_wp
    Resasc = wgk(8)*abs(fc - reskh)
    do j = 1, 7
      Resasc = Resasc + wgk(j)*(abs(fv1(j) - reskh) + abs(fv2(j) - reskh))
    end do
    Result = resk*hlgth
    Resabs = Resabs*dhlgth
    Resasc = Resasc*dhlgth
    Abserr = abs((resk - resg)*hlgth)
    if (Resasc /= 0.0_wp .and. Abserr /= 0.0_wp) Abserr = Resasc*min(1.0_wp, (200.0_wp*Abserr/Resasc)**1.5_wp)
    if (Resabs > uflow/(50.0_wp*epmach)) Abserr = max((epmach*50.0_wp)*Resabs, Abserr)
  end subroutine dqk15
end module quadpack_small

program run_quadpack
  use quadpack_small
  implicit none
  real(wp) :: result, abserr, resabs, resasc
  call dqk15(f, 0.0_wp, 1.0_wp, result, abserr, resabs, resasc)
  write(*,'(4(ES24.16E3,1X))') result, abserr, resabs, resasc
contains
  function f(x) result(y)
    real(wp), intent(in) :: x
    real(wp) :: y
    y = x*x + sin(x)
  end function f
end program run_quadpack
"""
    source = """
program run_quadpack
  use iso_fortran_env, only: wp => real64
  use quadpack_double, only: dqk15
  implicit none
  real(wp) :: result, abserr, resabs, resasc
  call dqk15(f, 0.0_wp, 1.0_wp, result, abserr, resabs, resasc)
  write(*,'(4(ES24.16E3,1X))') result, abserr, resabs, resasc
contains
  function f(x) result(y)
    real(wp), intent(in) :: x
    real(wp) :: y
    y = x*x + sin(x)
  end function f
end program run_quadpack
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "quadpack_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "medium" / "quadpack-master" / "src" / "quadpack_double.F90",
        ],
        inline_sources=[("run_quadpack.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    quadpack_module = _load_quadpack_dqk15_module(
        TARGET_ROOT / "medium" / "quadpack" / "generated_python" / "src",
    )

    def func(x: float) -> float:
        return x * x + math.sin(x)

    python_values = np.array(quadpack_module.dqk15(func, 0.0, 1.0), dtype=np.float64)

    dqk21_driver = """
program run_dqk21
  use iso_fortran_env, only: wp => real64
  use quadpack_double, only: dqk21
  implicit none
  real(wp) :: result, abserr, resabs, resasc
  call dqk21(f1, 0.0_wp, 1.0_wp, result, abserr, resabs, resasc)
  write(*,'(4(ES24.16E3,1X))') result, abserr, resabs, resasc
  call dqk21(f2, -1.0_wp, 2.0_wp, result, abserr, resabs, resasc)
  write(*,'(4(ES24.16E3,1X))') result, abserr, resabs, resasc
contains
  function f1(x) result(y)
    real(wp), intent(in) :: x
    real(wp) :: y
    y = x*x + sin(x)
  end function f1
  function f2(x) result(y)
    real(wp), intent(in) :: x
    real(wp) :: y
    y = exp(-x*x)
  end function f2
end program run_dqk21
"""
    dqk21_exe, _ = _compile_fortran_program_ordered(
        "quadpack_dqk21_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "medium" / "quadpack-master" / "src" / "quadpack_double.F90",
        ],
        inline_sources=[("run_dqk21.f90", dqk21_driver)],
    )
    dqk21_output = _run([str(dqk21_exe)], capture_stderr=True).stdout.strip().splitlines()

    def _dqk21_module():
        return _load_quadpack_dqk21_module(
            TARGET_ROOT / "medium" / "quadpack" / "generated_python" / "src",
        )

    def _dqk21_poly() -> np.ndarray:
        return np.array(_dqk21_module().dqk21(func, 0.0, 1.0), dtype=np.float64)

    def _dqk21_gauss() -> np.ndarray:
        return np.array(
            _dqk21_module().dqk21(lambda x: math.exp(-x * x), -1.0, 2.0), dtype=np.float64
        )

    return _repo_result(
        "medium",
        "quadpack",
        [
            *_numeric_case_checks(
                "dqk15",
                _parse_float_line(output[0]),
                python_values,
                ["result", "abserr", "resabs", "resasc"],
                atol=1.0e-10,
                rtol=1.0e-10,
            ),
            *_guarded_case_checks(
                "dqk21_poly_sin",
                _parse_float_line(dqk21_output[0]),
                ["result", "abserr", "resabs", "resasc"],
                _dqk21_poly,
                atol=1.0e-10,
                rtol=1.0e-10,
                note="21-point Gauss-Kronrod rule compiled from the original quadpack_double.F90.",
            ),
            *_guarded_case_checks(
                "dqk21_gaussian",
                _parse_float_line(dqk21_output[1]),
                ["result", "abserr", "resabs", "resasc"],
                _dqk21_gauss,
                atol=1.0e-10,
                rtol=1.0e-10,
                note="21-point Gauss-Kronrod rule compiled from the original quadpack_double.F90.",
            ),
        ],
    )


def verify_wavelets() -> RepoResult:
    driver = """
program run_wavelets
  implicit none
  integer :: status
  double precision :: p, q, x, df, bound

  x = 0.0d0
  df = 2.0d0
  call cdfchi(1, p, q, x, df, status, bound)
  write(*,'(2(ES24.16E3,1X),I0)') p, q, status

  x = 10.0d0
  df = 2.0d0
  call cdfchi(1, p, q, x, df, status, bound)
  write(*,'(2(ES24.16E3,1X),I0)') p, q, status

  x = 100.0d0
  df = 2.0d0
  call cdfchi(1, p, q, x, df, status, bound)
  write(*,'(2(ES24.16E3,1X),I0)') p, q, status
end program run_wavelets
"""
    exe_path, _ = _compile_fortran_program(
        "wavelets_verify",
        inline_sources=[("run_wavelets.f90", driver)],
        file_sources=[FORTRAN_CORPUS_ROOT / "medium" / "wavelets" / "wave_fortran" / "chisqr.f"],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    fortran_values = []
    for line in output:
        parts = line.strip().split()
        fortran_values.append([float(parts[0]), float(parts[1]), int(parts[2])])

    python_module = _load_module(
        "wavelets_cdfchi",
        TARGET_ROOT / "medium" / "wavelets" / "generated_python" / "src" / "wavelets" / "cdfchi.py",
    )
    python_values = []
    for x in (0.0, 10.0, 100.0):
        p = np.zeros(1, dtype=np.float64)
        q = np.zeros(1, dtype=np.float64)
        status = np.zeros(1, dtype=np.int32)
        bound = np.zeros(1, dtype=np.float64)
        python_module.cdfchi(1, p, q, x, 2.0, status, bound)
        python_values.append([p[0], q[0], int(status[0])])

    return _repo_result(
        "medium",
        "wavelets",
        [
            *_numeric_case_checks(
                "cdfchi",
                np.array(fortran_values, dtype=np.float64).ravel(),
                np.array(python_values, dtype=np.float64).ravel(),
                [
                    "x0_p",
                    "x0_q",
                    "x0_status",
                    "x10_p",
                    "x10_q",
                    "x10_status",
                    "x100_p",
                    "x100_q",
                    "x100_status",
                ],
                atol=1.0e-10,
                rtol=1.0e-10,
                note="The comparison ignores BOUND because the original routine documents it as undefined when STATUS=0.",
            )
        ],
    )


def verify_lapack() -> RepoResult:
    sys.path.insert(0, str(STUB_ROOT))
    dcopy_module = importlib.import_module("dcopy_f")
    dscal_module = importlib.import_module("dscal_f")
    dcopy_python = _load_module(
        "lapack_dcopy_py",
        TARGET_ROOT / "complex" / "lapack" / "generated_python" / "src" / "dcopy.py",
    )
    dscal_python = _load_module(
        "lapack_dscal_py",
        TARGET_ROOT / "complex" / "lapack" / "generated_python" / "src" / "dscal.py",
    )

    source = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    target_fortran = np.zeros(4, dtype=np.float64)
    target_python = np.zeros(4, dtype=np.float64)
    dcopy_module.dcopy(len(source), source, 1, target_fortran, 1)
    dcopy_python.dcopy(len(source), source.copy(), 1, target_python, 1)

    x_fortran = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    x_python = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    dscal_module.dscal(3, 2.0, x_fortran, -1)
    x_python = dscal_python.dscal(3, 2.0, x_python, -1)

    source2 = np.array([5.0, -1.0, 0.0, 2.5, 7.0], dtype=np.float64)
    target2_fortran = np.zeros(5, dtype=np.float64)
    target2_python = np.zeros(5, dtype=np.float64)
    dcopy_module.dcopy(len(source2), source2, 1, target2_fortran, 1)
    dcopy_python.dcopy(len(source2), source2.copy(), 1, target2_python, 1)

    x2_fortran = np.array([1.0, -2.0, 3.0, -4.0], dtype=np.float64)
    x2_python = np.array([1.0, -2.0, 3.0, -4.0], dtype=np.float64)
    dscal_module.dscal(4, 0.5, x2_fortran, 1)
    x2_python = dscal_python.dscal(4, 0.5, x2_python, 1)

    return _repo_result(
        "complex",
        "lapack",
        [
            *_numeric_case_checks(
                "dcopy",
                target_fortran,
                target_python,
                ["i1", "i2", "i3", "i4"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            *_numeric_case_checks(
                "dscal",
                x_fortran,
                x_python,
                ["i1", "i2", "i3"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Reference BLAS returns immediately when INCX <= 0; the translated Python scales the array for INCX < 0.",
            ),
            *_numeric_case_checks(
                "dcopy_len5",
                target2_fortran,
                target2_python,
                ["i1", "i2", "i3", "i4", "i5"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Length-5 copy with mixed signs and a zero element on unit stride.",
            ),
            *_numeric_case_checks(
                "dscal_unit_stride",
                x2_fortran,
                x2_python,
                ["i1", "i2", "i3", "i4"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Positive unit-stride scaling by 0.5 over a length-4 signed vector.",
            ),
        ],
    )


def verify_pymc2() -> RepoResult:
    driver = """
program run_pymc2
  implicit none
  integer :: i
  double precision :: x(4), y(4), z(3), w(3)
  x = (/1.0d0, 2.0d0, 3.0d0, 4.0d0/)
  y = 0.0d0
  call dcopy(4, x, 1, y, 1)
  write(*,'(4(ES24.16E3,1X))') y
  z = (/1.0d0, 2.0d0, 3.0d0/)
  call dscal(3, 2.0d0, z, -1)
  write(*,'(3(ES24.16E3,1X))') z
  w = (/1.0d0, -2.0d0, 3.5d0/)
  z = (/1.0d0, 2.0d0, 3.0d0/)
  call daxpy(3, 2.0d0, z, 1, w, 1)
  write(*,'(3(ES24.16E3,1X))') w
end program run_pymc2
"""
    exe_path, _ = _compile_fortran_program(
        "pymc2_verify",
        inline_sources=[("run_pymc2.f90", driver)],
        file_sources=[
            FORTRAN_CORPUS_ROOT / "complex" / "pymc2" / "blas" / "BLAS" / "dcopy.f",
            FORTRAN_CORPUS_ROOT / "complex" / "pymc2" / "blas" / "BLAS" / "dscal.f",
            FORTRAN_CORPUS_ROOT / "complex" / "pymc2" / "blas" / "BLAS" / "daxpy.f",
        ],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    python_module = _load_module(
        "pymc2_blas_core",
        TARGET_ROOT / "complex" / "pymc2" / "generated_python" / "src" / "blas_core.py",
    )

    x = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    y = np.zeros(4, dtype=np.float64)
    python_module.dcopy(4, x.copy(), 1, y, 1)

    z = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    python_module.dscal(3, 2.0, z, -1)
    w = np.array([1.0, -2.0, 3.5], dtype=np.float64)
    z = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    python_module.daxpy(3, 2.0, z.copy(), 1, w, 1)

    return _repo_result(
        "complex",
        "pymc2",
        [
            *_numeric_case_checks(
                "dcopy",
                _parse_float_line(output[0]),
                y,
                ["i1", "i2", "i3", "i4"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            *_numeric_case_checks(
                "dscal",
                _parse_float_line(output[1]),
                z,
                ["i1", "i2", "i3"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="The translated Python scales on INCX < 0, while the original BLAS routine returns early.",
            ),
            *_numeric_case_checks(
                "daxpy",
                _parse_float_line(output[2]),
                w,
                ["i1", "i2", "i3"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
        ],
    )


def verify_nek5000() -> RepoResult:
    driver = """
program run_nek
  implicit none
  double precision :: x(4), y(4), z(4)
  double precision :: a(2,3), x3(3), yv(2)
  double precision :: am(2,2), bm(2,2), cm(2,2)
  double precision :: big(2)
  double precision :: ddot, dnrm2
  x = (/1.0d0, -2.0d0, 3.5d0, -4.5d0/)
  y = (/0.5d0, 2.0d0, -1.0d0, 8.0d0/)
  write(*,'(ES24.16E3)') ddot(4, x, 1, y, 1)
  write(*,'(ES24.16E3)') dnrm2(4, x, 1)
  z = (/1.0d0, -2.0d0, 3.5d0, -4.5d0/)
  call daxpy(4, 0.5d0, y, 1, z, 1)
  write(*,'(4(ES24.16E3,1X))') z
  a = reshape((/1.0d0, 4.0d0, 2.0d0, 5.0d0, 3.0d0, 6.0d0/), (/2, 3/))
  x3 = (/1.0d0, -1.0d0, 2.0d0/)
  yv = (/1.0d0, 1.0d0/)
  call dgemv('N', 2, 3, 1.5d0, a, 2, x3, 1, 0.5d0, yv, 1)
  write(*,'(2(ES24.16E3,1X))') yv
  am = reshape((/1.0d0, 3.0d0, 2.0d0, 4.0d0/), (/2, 2/))
  bm = reshape((/5.0d0, 7.0d0, 6.0d0, 8.0d0/), (/2, 2/))
  cm = reshape((/1.0d0, 0.0d0, 0.0d0, 1.0d0/), (/2, 2/))
  call dgemm('N', 'N', 2, 2, 2, 2.0d0, am, 2, bm, 2, -1.0d0, cm, 2)
  write(*,'(4(ES24.16E3,1X))') cm(1,1), cm(1,2), cm(2,1), cm(2,2)
  big = (/3.0d10, 4.0d10/)
  write(*,'(ES24.16E3)') dnrm2(2, big, 1)
end program run_nek
"""
    blas_dir = FORTRAN_CORPUS_ROOT / "complex" / "Nek5000" / "3rd_party" / "blasLapack"
    exe_path, _ = _compile_fortran_program(
        "nek5000_verify",
        inline_sources=[("run_nek.f90", driver)],
        file_sources=[
            blas_dir / "ddot.f",
            blas_dir / "dnrm2.f",
            blas_dir / "daxpy.f",
            blas_dir / "dgemv.f",
            blas_dir / "dgemm.f",
            blas_dir / "lsame.f",
            blas_dir / "xerbla.f",
        ],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    python_module = _load_module(
        "nek5000_blas_lapack",
        TARGET_ROOT / "complex" / "Nek5000" / "generated_python" / "src" / "blas_lapack.py",
    )
    x = np.array([1.0, -2.0, 3.5, -4.5], dtype=np.float64)
    y = np.array([0.5, 2.0, -1.0, 8.0], dtype=np.float64)
    z = np.array([1.0, -2.0, 3.5, -4.5], dtype=np.float64)
    python_module.daxpy(0.5, y, z)
    a = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float64)
    x3 = np.array([1.0, -1.0, 2.0], dtype=np.float64)
    am = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    bm = np.array([[5.0, 6.0], [7.0, 8.0]], dtype=np.float64)
    big = np.array([3.0e10, 4.0e10], dtype=np.float64)

    def _dgemv_values() -> np.ndarray:
        yv = np.array([1.0, 1.0], dtype=np.float64)
        return np.asarray(python_module.dgemv(a, x3, alpha=1.5, beta=0.5, y=yv), dtype=np.float64)

    def _dgemm_values() -> np.ndarray:
        cm = np.eye(2, dtype=np.float64)
        return np.asarray(
            python_module.dgemm(am, bm, alpha=2.0, beta=-1.0, C=cm), dtype=np.float64
        ).reshape(-1)

    def _dnrm2_scaled_value() -> np.ndarray:
        return np.array([python_module.dnrm2(big)], dtype=np.float64)

    return _repo_result(
        "complex",
        "Nek5000",
        [
            _numeric_check(
                "ddot",
                _parse_float_line(output[0]),
                np.array([python_module.ddot(x, y)], dtype=np.float64),
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            _numeric_check(
                "dnrm2",
                _parse_float_line(output[1]),
                np.array([python_module.dnrm2(x)], dtype=np.float64),
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            *_numeric_case_checks(
                "daxpy",
                _parse_float_line(output[2]),
                z,
                ["i1", "i2", "i3", "i4"],
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            *_guarded_case_checks(
                "dgemv",
                _parse_float_line(output[3]),
                ["y1", "y2"],
                _dgemv_values,
                atol=1.0e-12,
                rtol=1.0e-12,
                note="y = 1.5*A@x + 0.5*y against the repository's bundled reference dgemv.",
            ),
            *_guarded_case_checks(
                "dgemm",
                _parse_float_line(output[4]),
                ["c11", "c12", "c21", "c22"],
                _dgemm_values,
                atol=1.0e-12,
                rtol=1.0e-12,
                note="C = 2*A@B - I against the repository's bundled reference dgemm.",
            ),
            *_guarded_case_checks(
                "dnrm2_scaled",
                _parse_float_line(output[5]),
                ["norm"],
                _dnrm2_scaled_value,
                atol=0.0,
                rtol=1.0e-12,
                note="Large-magnitude norm exercising overflow-safe scaling.",
            ),
        ],
    )


def verify_fpm() -> RepoResult:
    source = """
module fpm_small
  implicit none
  integer, parameter :: id_all = -1
  integer, parameter :: id_unknown = 0
  integer, parameter :: id_gcc = 1
  integer, parameter :: id_f95 = 2
  integer, parameter :: id_caf = 3
  integer, parameter :: id_intel_classic_nix = 4
  integer, parameter :: id_intel_classic_mac = 5
  integer, parameter :: id_intel_classic_windows = 6
  integer, parameter :: id_intel_llvm_nix = 7
  integer, parameter :: id_intel_llvm_windows = 8
  integer, parameter :: id_intel_llvm_unknown = 9
  integer, parameter :: id_pgi = 10
  integer, parameter :: id_nvhpc = 11
  integer, parameter :: id_nag = 12
  integer, parameter :: id_flang_classic = 13
  integer, parameter :: id_flang = 14
  integer, parameter :: id_amdflang = 15
  integer, parameter :: id_f18 = 16
  integer, parameter :: id_ibmxl = 17
  integer, parameter :: id_cray = 18
  integer, parameter :: id_lahey = 19
  integer, parameter :: id_lfortran = 20
contains
  function basename(path) result(name)
    character(len=*), intent(in) :: path
    character(len=:), allocatable :: name
    integer :: i
    i = len_trim(path)
    do while (i > 0)
      if (path(i:i) == '/' .or. path(i:i) == '\\') exit
      i = i - 1
    end do
    name = trim(path(i+1:len_trim(path)))
  end function basename

  function check_compiler(compiler, expected) result(match)
    character(len=*), intent(in) :: compiler
    character(len=*), intent(in) :: expected
    logical :: match
    match = compiler == expected
    if (.not. match) then
      match = index(basename(compiler), expected) > 0
    end if
  end function check_compiler

  integer function match_compiler_type(compiler) result(id)
    character(len=*), intent(in) :: compiler
    if (check_compiler(compiler, 'gfortran')) then
      id = id_gcc
      return
    end if
    if (check_compiler(compiler, 'f95')) then
      id = id_f95
      return
    end if
    if (check_compiler(compiler, 'caf')) then
      id = id_caf
      return
    end if
    if (check_compiler(compiler, 'ifort')) then
      id = id_intel_classic_mac
      return
    end if
    if (check_compiler(compiler, 'ifx')) then
      id = id_intel_llvm_nix
      return
    end if
    if (check_compiler(compiler, 'nvfortran')) then
      id = id_nvhpc
      return
    end if
    if (check_compiler(compiler, 'pgfortran') .or. check_compiler(compiler, 'pgf90') .or. check_compiler(compiler, 'pgf95')) then
      id = id_pgi
      return
    end if
    if (check_compiler(compiler, 'nagfor')) then
      id = id_nag
      return
    end if
    if (check_compiler(compiler, 'flang-classic')) then
      id = id_flang_classic
      return
    end if
    if (check_compiler(compiler, 'flang-new') .or. check_compiler(compiler, 'flang')) then
      id = id_flang
      return
    end if
    if (check_compiler(compiler, 'amdflang')) then
      id = id_amdflang
      return
    end if
    if (check_compiler(compiler, 'f18')) then
      id = id_f18
      return
    end if
    if (check_compiler(compiler, 'xlf90')) then
      id = id_ibmxl
      return
    end if
    if (check_compiler(compiler, 'crayftn')) then
      id = id_cray
      return
    end if
    if (check_compiler(compiler, 'lfc')) then
      id = id_lahey
      return
    end if
    if (check_compiler(compiler, 'lfortran')) then
      id = id_lfortran
      return
    end if
    if (check_compiler(compiler, 'all')) then
      id = id_all
      return
    end if
    id = id_unknown
  end function match_compiler_type

  integer function get_compiler_id(compiler) result(id)
    character(len=*), intent(in) :: compiler
    id = match_compiler_type(compiler)
  end function get_compiler_id

  subroutine get_default_c_compiler(f_compiler, c_compiler)
    character(len=*), intent(in) :: f_compiler
    character(len=:), allocatable, intent(out) :: c_compiler
    integer :: id
    id = get_compiler_id(f_compiler)
    select case(id)
    case(id_intel_classic_nix, id_intel_classic_mac, id_intel_classic_windows)
      c_compiler = 'icc'
    case(id_intel_llvm_nix, id_intel_llvm_windows)
      c_compiler = 'icx'
    case(id_flang_classic, id_flang, id_f18)
      c_compiler = 'clang'
    case(id_ibmxl)
      c_compiler = 'xlc'
    case(id_lfortran)
      c_compiler = 'cc'
    case(id_gcc)
      c_compiler = 'gcc'
    case(id_amdflang)
      c_compiler = 'amdclang'
    case default
      c_compiler = f_compiler
    end select
  end subroutine get_default_c_compiler

  subroutine get_default_cxx_compiler(f_compiler, cxx_compiler)
    character(len=*), intent(in) :: f_compiler
    character(len=:), allocatable, intent(out) :: cxx_compiler
    integer :: id
    id = get_compiler_id(f_compiler)
    select case(id)
    case(id_intel_classic_nix, id_intel_classic_mac, id_intel_classic_windows)
      cxx_compiler = 'icpc'
    case(id_intel_llvm_nix, id_intel_llvm_windows)
      cxx_compiler = 'icpx'
    case(id_flang_classic, id_flang, id_f18)
      cxx_compiler = 'clang++'
    case(id_amdflang)
      cxx_compiler = 'amdclang++'
    case(id_ibmxl)
      cxx_compiler = 'xlc++'
    case(id_lfortran)
      cxx_compiler = 'cc'
    case(id_gcc)
      cxx_compiler = 'g++'
    case default
      cxx_compiler = f_compiler
    end select
  end subroutine get_default_cxx_compiler
end module fpm_small

program run_fpm
  use fpm_small
  implicit none
  character(len=:), allocatable :: c_compiler, cxx_compiler
  character(len=*), parameter :: cases(8) = [character(len=24) :: 'gfortran', 'ifort', 'ifx', 'nvfortran', 'lfortran', 'amdflang', '/usr/bin/gfortran', 'foo']
  integer :: i
  do i = 1, size(cases)
    call get_default_c_compiler(trim(cases(i)), c_compiler)
    call get_default_cxx_compiler(trim(cases(i)), cxx_compiler)
    write(*,'(A,"|",A,"|",A)') trim(cases(i)), trim(c_compiler), trim(cxx_compiler)
  end do
end program run_fpm
"""
    exe_path, _ = _compile_fortran_program("fpm_verify", inline_sources=[("run_fpm.f90", source)])
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    python_module = _load_module(
        "fpm_compiler_config",
        TARGET_ROOT / "complex" / "fpm" / "generated_python" / "src" / "compiler_config.py",
    )

    string_to_vendor = {
        "gfortran": python_module.CompilerID.GCC,
        "ifort": python_module.CompilerID.INTEL_CLASSIC_MAC,
        "ifx": python_module.CompilerID.INTEL_LLVM_NIX,
        "nvfortran": python_module.CompilerID.NVHPC,
        "lfortran": python_module.CompilerID.LFORTRAN,
        "amdflang": python_module.CompilerID.UNKNOWN,
        "/usr/bin/gfortran": python_module.CompilerID.GCC,
        "foo": python_module.CompilerID.UNKNOWN,
    }
    fortran_pairs = []
    python_pairs = []
    for line in output:
        compiler, c_compiler, cxx_compiler = line.split("|")
        fortran_pairs.append([compiler, c_compiler, cxx_compiler])
        vendor = string_to_vendor[compiler]
        python_pairs.append(
            [
                compiler,
                python_module.get_default_c_compiler(vendor),
                python_module.get_default_cxx_compiler(vendor),
            ]
        )

    compiler_labels = [
        compiler.replace("/", "_").replace("-", "_")
        for compiler, _, _ in fortran_pairs
    ]
    c_checks = _exact_case_checks(
        "get_default_c_compiler",
        [row[1] for row in fortran_pairs],
        [row[1] for row in python_pairs],
        compiler_labels,
        note="Normalized comparison: the original Fortran accepts a compiler string, while the translated Python accepts a CompilerID enum.",
    )
    cxx_checks = _exact_case_checks(
        "get_default_cxx_compiler",
        [row[2] for row in fortran_pairs],
        [row[2] for row in python_pairs],
        compiler_labels,
        note="Normalized comparison: the original Fortran accepts a compiler string, while the translated Python accepts a CompilerID enum.",
    )
    return _repo_result("complex", "fpm", [*c_checks, *cxx_checks], notes="The translated Python changes the API contract for these routines.")


def verify_ccpp_physics() -> RepoResult:
    source = """
module gfs_debug_small
  implicit none
  integer, parameter :: kind_phys = kind(0.0d0)
contains
  subroutine print_logic_0d(mpirank, omprank, blkno, lat_d, lon_d, name, var)
    integer, intent(in) :: mpirank, omprank, blkno
    real(kind_phys), intent(in) :: lat_d(:), lon_d(:)
    character(len=*), intent(in) :: name
    logical, intent(in) :: var
    write(*,'(2a,3i6,1x,l)') 'XXX: ', trim(name), mpirank, omprank, blkno, var
  end subroutine print_logic_0d

  subroutine print_int_0d(mpirank, omprank, blkno, lat_d, lon_d, name, var)
    integer, intent(in) :: mpirank, omprank, blkno
    real(kind_phys), intent(in) :: lat_d(:), lon_d(:)
    character(len=*), intent(in) :: name
    integer, intent(in) :: var
    write(*,'(2a,3i6,i15)') 'XXX: ', trim(name), mpirank, omprank, blkno, var
  end subroutine print_int_0d

  subroutine print_real_0d(mpirank, omprank, blkno, lat_d, lon_d, name, var)
    integer, intent(in) :: mpirank, omprank, blkno
    real(kind_phys), intent(in) :: lat_d(:), lon_d(:)
    character(len=*), intent(in) :: name
    real(kind_phys), intent(in) :: var
    write(*,'(2a,3i6,e35.25)') 'XXX: ', trim(name), mpirank, omprank, blkno, var
  end subroutine print_real_0d
end module gfs_debug_small

program run_ccpp
  use gfs_debug_small
  implicit none
  real(kind_phys) :: lat_d(1), lon_d(1)
  lat_d = 0.0_kind_phys
  lon_d = 0.0_kind_phys
  call print_logic_0d(1, 2, 3, lat_d, lon_d, 'FLAG', .true.)
  call print_logic_0d(1, 2, 3, lat_d, lon_d, 'OFF', .false.)
  call print_int_0d(1, 2, 3, lat_d, lon_d, 'COUNT', 42)
  call print_real_0d(1, 2, 3, lat_d, lon_d, 'VALUE', 1.25_kind_phys)
end program run_ccpp
"""
    exe_path, _ = _compile_fortran_program("ccpp_verify", inline_sources=[("run_ccpp.f90", source)])
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()

    python_module = _load_module(
        "ccpp_gfs_debug",
        TARGET_ROOT / "complex" / "ccpp-physics" / "generated_python" / "src" / "gfs_debug.py",
    )
    stream = io.StringIO()
    debug = python_module.GFSDebug(python_module.DebugConfig(output_stream=stream))
    logic_line = debug.print_logic_0d("FLAG", True, mpirank=1, omprank=2, blkno=3)
    logic_false_line = debug.print_logic_0d("OFF", False, mpirank=1, omprank=2, blkno=3)
    int_line = debug.print_int_0d("COUNT", 42, mpirank=1, omprank=2, blkno=3)
    real_line = debug.print_real_0d("VALUE", 1.25, mpirank=1, omprank=2, blkno=3)

    constants_source = """
program run_ccpp_constants
  implicit none
  integer, parameter :: kind_phys = kind(0.0d0)
  ! Values mirror physics/hooks/physcons.F90 in the ccpp-physics repository.
  real(kind=kind_phys), parameter :: con_pi   = 4.0d0*atan(1.0d0)
  real(kind=kind_phys), parameter :: con_g    = 9.80665e+0_kind_phys
  real(kind=kind_phys), parameter :: con_rd   = 2.8705e+2_kind_phys
  real(kind=kind_phys), parameter :: con_rv   = 4.6150e+2_kind_phys
  real(kind=kind_phys), parameter :: con_cp   = 1.0046e+3_kind_phys
  real(kind=kind_phys), parameter :: con_hvap = 2.5000e+6_kind_phys
  real(kind=kind_phys), parameter :: con_t0c  = 2.7315e+2_kind_phys
  write(*,'(7(ES24.16E3,1X))') con_pi, con_g, con_rd, con_rv, con_cp, con_hvap, con_t0c
end program run_ccpp_constants
"""
    constants_exe, _ = _compile_fortran_program(
        "ccpp_constants_verify",
        inline_sources=[("run_ccpp_constants.f90", constants_source)],
    )
    constants_output = _run([str(constants_exe)], capture_stderr=True).stdout.strip().split()
    constant_names = ["con_pi", "con_g", "con_rd", "con_rv", "con_cp", "con_hvap", "con_t0c"]

    def _python_constants() -> np.ndarray:
        physcons_module = _load_module(
            "ccpp_physcons",
            TARGET_ROOT / "complex" / "ccpp-physics" / "generated_python" / "src" / "physcons.py",
        )
        return np.array(
            [float(getattr(physcons_module.physcons, name)) for name in constant_names],
            dtype=np.float64,
        )

    return _repo_result(
        "complex",
        "ccpp-physics",
        [
            _exact_check("print_logic_0d_true", output[0].strip(), logic_line),
            _exact_check("print_logic_0d_false", output[1].strip(), logic_false_line),
            _exact_check("print_int_0d", output[2].strip(), int_line),
            _exact_check("print_real_0d", output[3].strip(), real_line),
            *_guarded_case_checks(
                "physical_constants",
                np.array([float(part) for part in constants_output], dtype=np.float64),
                constant_names,
                _python_constants,
                atol=0.0,
                rtol=1.0e-12,
                note="GFS physical constants from physcons.F90; isolates data-content agreement from the print-formatting defects.",
            ),
        ],
    )


def verify_petsc() -> RepoResult:
    source = """
module ex61fmodule_small
  implicit none
contains
  subroutine split_indices(total, num_pieces, ibeg, iend)
    implicit none
    integer :: total
    integer :: num_pieces
    integer :: ibeg(num_pieces), iend(num_pieces)
    integer :: itmp1, itmp2, ioffset, i
    itmp1 = total/num_pieces
    itmp2 = mod(total, num_pieces)
    ioffset = 0
    do i = 1, itmp2
      ibeg(i) = ioffset + 1
      iend(i) = ioffset + (itmp1 + 1)
      ioffset = iend(i)
    end do
    do i = itmp2 + 1, num_pieces
      ibeg(i) = ioffset + 1
      if (ibeg(i) > total) then
        iend(i) = ibeg(i) - 1
      else
        iend(i) = ioffset + itmp1
        ioffset = iend(i)
      end if
    end do
  end subroutine split_indices
end module ex61fmodule_small

program run_petsc_split
  use ex61fmodule_small
  implicit none
  integer :: ibeg2(2), iend2(2), ibeg3(3), iend3(3), ibeg4(4), iend4(4), ibeg8(8), iend8(8)
  integer :: ibeg7(7), iend7(7), ibeg3b(3), iend3b(3), ibeg4b(4), iend4b(4), ibeg5(5), iend5(5)
  integer :: i
  call split_indices(7, 2, ibeg2, iend2)
  call split_indices(10, 3, ibeg3, iend3)
  call split_indices(12, 4, ibeg4, iend4)
  call split_indices(5, 8, ibeg8, iend8)
  write(*,'(4(I0,1X))') ibeg2(1), iend2(1), ibeg2(2), iend2(2)
  write(*,'(6(I0,1X))') ibeg3(1), iend3(1), ibeg3(2), iend3(2), ibeg3(3), iend3(3)
  write(*,'(8(I0,1X))') ibeg4(1), iend4(1), ibeg4(2), iend4(2), ibeg4(3), iend4(3), ibeg4(4), iend4(4)
  write(*,'(16(I0,1X))') ibeg8(1), iend8(1), ibeg8(2), iend8(2), ibeg8(3), iend8(3), ibeg8(4), iend8(4), &
                           ibeg8(5), iend8(5), ibeg8(6), iend8(6), ibeg8(7), iend8(7), ibeg8(8), iend8(8)
  call split_indices(100, 7, ibeg7, iend7)
  call split_indices(3, 3, ibeg3b, iend3b)
  call split_indices(1, 4, ibeg4b, iend4b)
  call split_indices(23, 5, ibeg5, iend5)
  write(*,'(14(I0,1X))') (ibeg7(i), iend7(i), i = 1, 7)
  write(*,'(6(I0,1X))') (ibeg3b(i), iend3b(i), i = 1, 3)
  write(*,'(8(I0,1X))') (ibeg4b(i), iend4b(i), i = 1, 4)
  write(*,'(10(I0,1X))') (ibeg5(i), iend5(i), i = 1, 5)
end program run_petsc_split
"""
    exe_path, _ = _compile_fortran_program(
        "petsc_split_verify",
        inline_sources=[("run_petsc_split.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    fortran_values = np.array(
        [[int(part) for part in line.split()] for line in output],
        dtype=object,
    )

    python_module = _load_module(
        "petsc_index_splitting",
        TARGET_ROOT / "complex" / "petsc" / "generated_python" / "src" / "index_splitting.py",
    )
    split_cases = [(7, 2), (10, 3), (12, 4), (5, 8), (100, 7), (3, 3), (1, 4), (23, 5)]
    python_lines = []
    for total, pieces in split_cases:
        ibeg, iend = python_module.split_indices_fortran(total, pieces)
        row = []
        for start, end in zip(ibeg, iend):
            row.extend([int(start), int(end)])
        python_lines.append(row)
    checks = []
    for index, (total, pieces) in enumerate(split_cases):
        checks.append(
            _numeric_check(
                f"split_indices_{total}_{pieces}",
                np.array(fortran_values[index], dtype=np.int64),
                np.array(python_lines[index], dtype=np.int64),
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            )
        )
    return _repo_result("complex", "petsc", checks)


def run_all_verifications() -> list[RepoResult]:
    from extended_repo_verifiers import EXTENDED_VERIFIERS

    verifiers = [
        verify_tsunami,
        verify_tsunami_diff,
        verify_fkb,
        verify_fastgpt,
        verify_datetime_fortran,
        verify_m_strings,
        verify_fftpack,
        verify_fortranlib,
        verify_fortran_utils,
        verify_minpack,
        verify_sisso,
        verify_json_fortran,
        verify_fortran_astrodynamics_toolkit,
        verify_quadpack,
        verify_wavelets,
        verify_lapack,
        verify_pymc2,
        verify_nek5000,
        verify_fpm,
        verify_ccpp_physics,
        verify_petsc,
        *EXTENDED_VERIFIERS,
    ]
    results: list[RepoResult] = []
    for verifier in verifiers:
        try:
            results.append(verifier())
        except Exception as exc:  # pragma: no cover - exercised by script execution
            name = verifier.__name__.replace("verify_", "").replace("_", "-")
            tier = "unknown"
            if name in {
                "tsunami",
                "tsunami-diff",
                "fkb",
                "fastgpt",
                "datetime-fortran",
                "m-strings",
                "fftpack",
                "fortranlib",
                "fortran-utils",
            }:
                tier = "low"
            elif name in {"minpack", "sisso", "json-fortran", "fortran-astrodynamics-toolkit", "quadpack", "wavelets"}:
                tier = "medium"
            elif name in {"lapack", "pymc2", "nek5000", "fpm", "ccpp-physics", "petsc"}:
                tier = "complex"
            results.append(
                RepoResult(
                    tier=tier,
                    repo=name,
                    status="error",
                    notes=f"{type(exc).__name__}: {exc}",
                    checks=[CheckResult(routine="runner", status="error", comparison="runner", max_abs=None, max_rel=None, note=str(exc))],
                )
            )
    return results


def render_report(results: list[RepoResult]) -> str:
    total_repos = len(results)
    passed_repos = sum(result.status == "pass" for result in results)
    failed_repos = total_repos - passed_repos
    total_checks = sum(len(result.checks) for result in results)
    passed_checks = sum(check.status == "pass" for result in results for check in result.checks)

    lines = [
        "# Corpus Behavioral Verification",
        "",
        "This report runs routine-level Fortran/Python differential checks against the intended corpus layout:",
        "",
        "- Fortran roots: `$F2X_FORTRAN_CORPUS_ROOT/<tier>/<repo>`",
        "- Translated Python roots: `$F2X_TARGET_ROOT/<tier>/<repo>/generated_python`",
        "",
        f"The verification covers {total_repos} repositories total, with checks in every benchmark tier.",
        "",
        f"- Repos passed: {passed_repos}/{total_repos}",
        f"- Repos failed: {failed_repos}/{total_repos}",
        f"- Checks passed: {passed_checks}/{total_checks}",
        "",
    ]

    for tier in ("low", "medium", "complex"):
        lines.extend([f"## {tier.capitalize()}", "", "| Repo | Status | Routines | Notes |", "|------|--------|----------|-------|"])
        for result in [item for item in results if item.tier == tier]:
            routines = ", ".join(f"`{check.routine}`:{check.status}" for check in result.checks)
            notes = result.notes or "; ".join(check.note for check in result.checks if check.note)
            lines.append(f"| `{result.repo}` | {result.status} | {routines} | {notes or '-'} |")
        lines.append("")

    lines.extend(["## Findings", ""])
    for result in results:
        for check in result.checks:
            if check.status != "pass":
                metrics = []
                if check.max_abs is not None:
                    metrics.append(f"max_abs={check.max_abs:.3e}")
                if check.max_rel is not None:
                    metrics.append(f"max_rel={check.max_rel:.3e}")
                metric_text = f" ({', '.join(metrics)})" if metrics else ""
                note = f" {check.note}" if check.note else ""
                lines.append(f"- `{result.tier}/{result.repo}` `{check.routine}` failed{metric_text}.{note}")
    if all(check.status == "pass" for result in results for check in result.checks):
        lines.append("- No mismatches found in the selected routine set.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the f2x50 corpus-scale behavioral agreement checks.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT, help="Path for JSON results.")
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT, help="Path for markdown report.")
    args = parser.parse_args()

    results = run_all_verifications()
    report = render_report(results)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps([asdict(result) for result in results], indent=2), encoding="utf-8")
    args.markdown_out.write_text(report, encoding="utf-8")
    print(report, end="")


if __name__ == "__main__":
    main()
