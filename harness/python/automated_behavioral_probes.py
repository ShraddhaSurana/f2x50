"""Automated Fortran-vs-Python behavioral probes for shared routine candidates."""

from __future__ import annotations

import importlib.util
import inspect
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

FORTRAN_CORPUS_ROOT = Path(
    os.environ.get(
        "F2X_FORTRAN_CORPUS_ROOT",
        str(Path(__file__).resolve().parents[2] / "external" / "fortran_corpus"),
    )
)
TARGET_ROOT = Path(
    os.environ.get(
        "F2X_TARGET_ROOT",
        str(Path(__file__).resolve().parents[2] / "external" / "targets" / "python"),
    )
)
GENERATED_PYTHON_SUBDIR = os.environ.get("F2X_GENERATED_PYTHON_SUBDIR", "generated_python")

BLAS1_ROUTINES = {"dcopy", "dscal", "daxpy", "ddot", "dnrm2", "dasum", "enorm"}

STRING_FORTRAN_TEMPLATES = {
    "upcase": """
program probe
  character(len=32) :: out
  out = upcase('AbC! z9')
  write(*,'(A)') trim(out)
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
end program probe
""",
    "lowcase": """
program probe
  character(len=32) :: out
  out = lowcase('AbC! z9')
  write(*,'(A)') trim(out)
contains
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
end program probe
""",
    "blank": """
program probe
  logical :: a, b
  a = blank('   ')
  b = blank(' a ')
  write(*,'(L1)') a
  write(*,'(L1)') b
contains
  logical function blank(string)
    character(*), intent(in) :: string
    integer :: i
    do i = 1, len(string)
      if (iachar(string(i:i)) /= 32 .and. iachar(string(i:i)) /= 9) exit
    end do
    blank = (i > len(string))
  end function blank
end program probe
""",
    "lowercase_string": """
program probe
  write(*,'(A)') trim(lowercase_string('AbC/De~F'))
contains
  pure function lowercase_string(str) result(s_lower)
    character(len=*), intent(in) :: str
    character(len=len(str)) :: s_lower
    integer :: i, j
    character(len=*), parameter :: upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    character(len=*), parameter :: lower = 'abcdefghijklmnopqrstuvwxyz'
    s_lower = str
    do i = 1, len_trim(str)
      j = index(upper, s_lower(i:i))
      if (j > 0) s_lower(i:i) = lower(j:j)
    end do
  end function lowercase_string
end program probe
""",
}


@dataclass
class ProbeOutcome:
    routine: str
    status: str
    comparison: str
    max_abs: float | None
    max_rel: float | None
    note: str
    probe_type: str


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _compile_fortran(name: str, source: str) -> Path:
    temp_root = Path(tempfile.mkdtemp(prefix=f"auto-behavior-{name}-"))
    source_path = temp_root / f"{name}.f90"
    source_path.write_text(source, encoding="utf-8")
    exe_path = temp_root / name
    _run(
        [
            "gfortran",
            "-O0",
            "-ffree-line-length-none",
            "-o",
            str(exe_path),
            str(source_path),
        ]
    )
    return exe_path


def _compile_fortran_files(name: str, driver: str, fortran_files: list[Path]) -> Path:
    temp_root = Path(tempfile.mkdtemp(prefix=f"auto-behavior-{name}-"))
    driver_path = temp_root / "driver.f90"
    driver_path.write_text(driver, encoding="utf-8")
    sources = [driver_path, *fortran_files]
    exe_path = temp_root / name
    _run(
        [
            "gfortran",
            "-O0",
            "-ffree-line-length-none",
            "-ffixed-line-length-none",
            "-o",
            str(exe_path),
            *[str(path) for path in sources],
        ]
    )
    return exe_path


def _parse_float_line(line: str) -> np.ndarray:
    return np.array([float(part) for part in line.strip().split()], dtype=np.float64)


def _max_rel(diff: np.ndarray, baseline: np.ndarray) -> float:
    denom = np.maximum(np.abs(baseline), 1.0e-30)
    return float(np.max(diff / denom)) if diff.size else 0.0


def _numeric_compare(
    routine: str,
    fortran_value: Any,
    python_value: Any,
    *,
    atol: float,
    rtol: float,
    probe_type: str,
    note: str = "",
) -> ProbeOutcome:
    f_value = np.asarray(fortran_value, dtype=np.float64)
    p_value = np.asarray(python_value, dtype=np.float64)
    if f_value.shape != p_value.shape:
        return ProbeOutcome(
            routine,
            "fail",
            "numeric",
            None,
            None,
            f"shape mismatch Fortran {f_value.shape} Python {p_value.shape}",
            probe_type,
        )
    diff = np.abs(f_value - p_value)
    max_abs = float(np.max(diff)) if diff.size else 0.0
    max_rel = _max_rel(diff, f_value) if diff.size else 0.0
    status = "pass" if np.allclose(f_value, p_value, atol=atol, rtol=rtol) else "fail"
    return ProbeOutcome(routine, status, "numeric", max_abs, max_rel, note, probe_type)


def _exact_compare(
    routine: str,
    fortran_value: Any,
    python_value: Any,
    *,
    probe_type: str,
    note: str = "",
) -> ProbeOutcome:
    status = "pass" if fortran_value == python_value else "fail"
    return ProbeOutcome(
        routine,
        status,
        "exact",
        0.0 if status == "pass" else None,
        0.0 if status == "pass" else None,
        note,
        probe_type,
    )


def _load_python_callable(
    tier: str,
    repo: str,
    python_relative: str,
    routine: str,
    *,
    patches: list[tuple[str, str]] | None = None,
) -> Callable[..., Any]:
    normalized_relative = python_relative.strip().replace("\\", "/").removeprefix("src/")
    path = TARGET_ROOT / tier / repo / GENERATED_PYTHON_SUBDIR / "src" / normalized_relative
    source = path.read_text(encoding="utf-8")
    for old, new in patches or []:
        source = source.replace(old, new)
    if "Tuple" in source and "from typing import" in source and "Tuple" not in source.split("from typing import", 1)[1].split("\n", 1)[0]:
        source = source.replace(
            "from typing import",
            "from typing import Tuple, ",
            1,
        )
    module_name = f"auto_{repo}_{routine}".replace("-", "_")
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader(module_name, loader=None)
    )
    module.__file__ = str(path)
    sys.modules[module_name] = module
    exec(compile(source, str(path), "exec"), module.__dict__)
    if not hasattr(module, routine):
        raise AttributeError(f"{routine} missing in {python_relative}")
    return getattr(module, routine)


def extract_fortran_function(path: Path, routine: str) -> str | None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    patterns = [
        rf"(?ims)^\s*(?:pure\s+|elemental\s+|recursive\s+)*function\s+{re.escape(routine)}\s*\("
        rf".*?^\s*end\s+function\s+{re.escape(routine)}\s*",
        rf"(?ims)^\s*(?:pure\s+|elemental\s+|recursive\s+)*function\s+{re.escape(routine)}\b.*?^\s*end\s+function\b",
        rf"(?ims)^\s*[\w\*]+\s+function\s+{re.escape(routine)}\s*\("
        rf".*?^\s*end\s+function\s+{re.escape(routine)}\s*",
        rf"(?ims)^\s*[\w\*]+\s+function\s+{re.escape(routine)}\b.*?^\s*end\s+function\b",
    ]
    match = None
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            break
    if not match:
        return None
    body = match.group(0)
    if re.search(r"(?im)^\s*use\s+mpi\b", body):
        return None
    return body


def _python_callable_accepts(python_callable, arg_count: int) -> bool:
    try:
        signature = inspect.signature(python_callable)
    except (TypeError, ValueError):
        return False
    params = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]
    return len(params) == arg_count


def candidate_score(name: str, fortran_files: tuple[str, ...]) -> int:
    if name in BLAS1_ROUTINES and any(path.endswith(".f") for path in fortran_files):
        return 100
    if name in STRING_FORTRAN_TEMPLATES:
        return 90
    if any(path.endswith((".f", ".f90")) for path in fortran_files):
        return 60
    return 10


def probe_string_template(
    *,
    tier: str,
    repo: str,
    routine: str,
    python_relative: str,
) -> ProbeOutcome:
    template = STRING_FORTRAN_TEMPLATES[routine]
    exe = _compile_fortran(f"{repo}_{routine}", template)
    output = _run([str(exe)]).stdout.strip().splitlines()
    python_callable = _load_python_callable(tier, repo, python_relative, routine)
    if routine == "blank":
        py_a = bool(python_callable("   "))
        py_b = bool(python_callable(" a "))
        fo_a = output[0].strip().upper().startswith("T")
        fo_b = output[1].strip().upper().startswith("T")
        status = "pass" if py_a == fo_a and py_b == fo_b else "fail"
        return ProbeOutcome(routine, status, "exact-bool", None, None, "", "string_template")
    if routine == "lowercase_string":
        return _exact_compare(
            routine,
            output[0].strip(),
            python_callable("AbC/De~F"),
            probe_type="string_template",
        )
    if routine == "upcase":
        return _exact_compare(
            routine,
            output[0].strip(),
            python_callable("AbC! z9"),
            probe_type="string_template",
        )
    return _exact_compare(
        routine,
        output[0].strip(),
        python_callable("AbC! z9"),
        probe_type="string_template",
    )


def probe_blas1(
    *,
    tier: str,
    repo: str,
    routine: str,
    python_relative: str,
    fortran_relative: str,
    fortran_repo_path: Path,
) -> ProbeOutcome:
    fortran_file = fortran_repo_path / fortran_relative
    python_callable = _load_python_callable(tier, repo, python_relative, routine)
    if routine == "dcopy":
        driver = """
program probe
  implicit none
  integer :: n, incx, incy
  double precision :: x(4), y(4)
  x = (/1.d0, 2.d0, 3.d0, 4.d0/)
  y = 0.d0
  n = 4; incx = 1; incy = 1
  call dcopy(n, x, incx, y, incy)
  write(*,'(4(ES24.16E3,1X))') y
end program probe
"""
    elif routine == "dscal":
        driver = """
program probe
  implicit none
  integer :: n, incx
  double precision :: alpha, x(3)
  x = (/1.d0, 2.d0, 3.d0/)
  n = 3; alpha = 2.d0; incx = 1
  call dscal(n, alpha, x, incx)
  write(*,'(3(ES24.16E3,1X))') x
end program probe
"""
    elif routine == "daxpy":
        driver = """
program probe
  implicit none
  integer :: n, incx, incy
  double precision :: alpha, x(3), y(3)
  x = (/1.d0, 2.d0, 3.d0/)
  y = (/1.d0, -2.d0, 3.5d0/)
  n = 3; alpha = 2.d0; incx = 1; incy = 1
  call daxpy(n, alpha, x, incx, y, incy)
  write(*,'(3(ES24.16E3,1X))') y
end program probe
"""
    elif routine == "ddot":
        driver = """
program probe
  implicit none
  integer :: n, incx, incy
  double precision :: x(4), y(4), result
  x = (/1.d0, -2.d0, 3.5d0, -4.5d0/)
  y = (/0.5d0, 2.d0, -1.d0, 8.d0/)
  n = 4; incx = 1; incy = 1
  result = ddot(n, x, incx, y, incy)
  write(*,'(ES24.16E3)') result
end program probe
"""
    elif routine == "dnrm2":
        driver = """
program probe
  implicit none
  integer :: n, incx
  double precision :: x(4), result
  x = (/1.d0, -2.d0, 3.5d0, -4.5d0/)
  n = 4; incx = 1
  result = dnrm2(n, x, incx)
  write(*,'(ES24.16E3)') result
end program probe
"""
    elif routine == "dasum":
        driver = """
program probe
  implicit none
  integer :: n, incx
  double precision :: x(4), result
  x = (/1.d0, -2.d0, 3.5d0, -4.5d0/)
  n = 4; incx = 1
  result = dasum(n, x, incx)
  write(*,'(ES24.16E3)') result
end program probe
"""
    elif routine == "enorm":
        return ProbeOutcome(routine, "skip", "unsupported", None, None, "Use curated minpack probe for enorm", "blas1")
    else:
        return ProbeOutcome(routine, "skip", "unsupported", None, None, "unsupported BLAS routine", "blas1")

    exe = _compile_fortran_files(f"{repo}_{routine}", driver, [fortran_file])
    output = _run([str(exe)]).stdout.strip().splitlines()

    if routine == "dcopy":
        y = np.zeros(4, dtype=np.float64)
        x = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
        python_callable(4, x.copy(), 1, y, 1)
        return _numeric_compare(routine, _parse_float_line(output[0]), y, atol=0.0, rtol=0.0, probe_type="blas1")
    if routine == "dscal":
        x = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        if routine == "dscal" and python_relative.endswith("blas_lapack.py"):
            python_callable(2.0, x)
        else:
            python_callable(3, 2.0, x, 1)
        return _numeric_compare(routine, _parse_float_line(output[0]), x, atol=0.0, rtol=0.0, probe_type="blas1")
    if routine == "daxpy":
        x = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        y = np.array([1.0, -2.0, 3.5], dtype=np.float64)
        if "blas_lapack.py" in python_relative:
            python_callable(2.0, x, y)
        else:
            python_callable(3, 2.0, x.copy(), 1, y, 1)
        return _numeric_compare(routine, _parse_float_line(output[0]), y, atol=0.0, rtol=0.0, probe_type="blas1")
    if routine == "ddot":
        x = np.array([1.0, -2.0, 3.5, -4.5], dtype=np.float64)
        y = np.array([0.5, 2.0, -1.0, 8.0], dtype=np.float64)
        if len(inspect.signature(python_callable).parameters) == 2:
            py = np.array([python_callable(x, y)], dtype=np.float64)
        else:
            py = np.array([python_callable(4, x, 1, y, 1)], dtype=np.float64)
        return _numeric_compare(routine, _parse_float_line(output[0]), py, atol=1e-12, rtol=1e-12, probe_type="blas1")
    if routine == "dnrm2":
        x = np.array([1.0, -2.0, 3.5, -4.5], dtype=np.float64)
        py = np.array([python_callable(x)], dtype=np.float64)
        return _numeric_compare(routine, _parse_float_line(output[0]), py, atol=1e-12, rtol=1e-12, probe_type="blas1")
    if routine == "dasum":
        x = np.array([1.0, -2.0, 3.5, -4.5], dtype=np.float64)
        py = np.array([python_callable(len(x), x, 1)], dtype=np.float64)
        return _numeric_compare(routine, _parse_float_line(output[0]), py, atol=1e-12, rtol=1e-12, probe_type="blas1")
    return ProbeOutcome(routine, "skip", "unsupported", None, None, "", "blas1")


def probe_extracted_function(
    *,
    tier: str,
    repo: str,
    routine: str,
    python_relative: str,
    fortran_relative: str,
    fortran_repo_path: Path,
) -> ProbeOutcome:
    fortran_path = fortran_repo_path / fortran_relative
    extracted = extract_fortran_function(fortran_path, routine)
    if not extracted:
        return ProbeOutcome(routine, "skip", "no_extract", None, None, "Could not extract standalone Fortran function", "extracted_function")

    if routine == "corr":
        driver = f"""
program probe
  implicit none
  real(8) :: x(4), y(4), result
  x = (/1.d0, 2.d0, 3.d0, 4.d0/)
  y = (/2.d0, 4.d0, 5.d0, 8.d0/)
  result = corr(x, y)
  write(*,'(ES24.16E3)') result
contains
{extracted}
end program probe
"""
        exe = _compile_fortran(f"{repo}_{routine}", driver)
        output = _run([str(exe)]).stdout.strip()
        python_callable = _load_python_callable(tier, repo, python_relative, routine)
        py = python_callable(
            np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64),
            np.array([2.0, 4.0, 5.0, 8.0], dtype=np.float64),
        )
        return _numeric_compare(routine, float(output), float(py), atol=1e-12, rtol=1e-12, probe_type="extracted_function")

    if routine == "det":
        driver = f"""
program probe
  implicit none
  real(8) :: a(2,2), result
  a(1,1)=2.d0; a(1,2)=1.d0; a(2,1)=5.d0; a(2,2)=3.d0
  result = det(a)
  write(*,'(ES24.16E3)') result
contains
{extracted}
end program probe
"""
        exe = _compile_fortran(f"{repo}_{routine}", driver)
        output = _run([str(exe)]).stdout.strip()
        python_callable = _load_python_callable(tier, repo, python_relative, routine)
        matrix = np.array([[2.0, 1.0], [5.0, 3.0]], dtype=np.float64)
        return _numeric_compare(routine, float(output), float(python_callable(matrix)), atol=1e-10, rtol=1e-10, probe_type="extracted_function")

    if routine == "inverse":
        driver = f"""
program probe
  implicit none
  real(8) :: a(2,2), out(2,2)
  a(1,1)=2.d0; a(1,2)=1.d0; a(2,1)=5.d0; a(2,2)=3.d0
  out = inverse(a)
  write(*,'(4(ES24.16E3,1X))') reshape(out, (/4/))
contains
{extracted}
end program probe
"""
        exe = _compile_fortran(f"{repo}_{routine}", driver)
        output = _run([str(exe)]).stdout.strip()
        python_callable = _load_python_callable(tier, repo, python_relative, routine)
        matrix = np.array([[2.0, 1.0], [5.0, 3.0]], dtype=np.float64)
        py = np.ravel(python_callable(matrix), order="F")
        return _numeric_compare(routine, _parse_float_line(output), py, atol=1e-10, rtol=1e-10, probe_type="extracted_function")

    if _python_callable_accepts(_load_python_callable(tier, repo, python_relative, routine), 1):
        blocked_prefixes = ("airy", "bessel", "h5", "hdf", "mpi", "fft", "solver", "print_", "read_", "write_")
        if routine.startswith(blocked_prefixes):
            return ProbeOutcome(routine, "skip", "no_inputs", None, None, "Blocked special-function auto probe", "extracted_function")
        driver = f"""
program probe
  implicit none
  real(8) :: x(4), result
  x = (/1.d0, 2.d0, 3.d0, 4.d0/)
  result = {routine}(x)
  write(*,'(ES24.16E3)') result
contains
{extracted}
end program probe
"""
        try:
            exe = _compile_fortran(f"{repo}_{routine}", driver)
            output = _run([str(exe)]).stdout.strip()
            python_callable = _load_python_callable(tier, repo, python_relative, routine)
            py = python_callable(np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64))
            return _numeric_compare(routine, float(output), float(np.asarray(py)), atol=1e-8, rtol=1e-8, probe_type="extracted_function")
        except subprocess.CalledProcessError:
            pass

    return ProbeOutcome(routine, "skip", "no_inputs", None, None, "No default inputs for extracted function", "extracted_function")


def probe_candidate(
    *,
    tier: str,
    repo: str,
    routine: str,
    python_files: tuple[str, ...],
    fortran_files: tuple[str, ...],
    fortran_repo_path: Path,
) -> ProbeOutcome:
    if not python_files:
        return ProbeOutcome(routine, "skip", "missing_python", None, None, "No generated Python mapping", "none")
    python_relative = python_files[0]
    if routine in STRING_FORTRAN_TEMPLATES:
        return probe_string_template(tier=tier, repo=repo, routine=routine, python_relative=python_relative)
    if routine in BLAS1_ROUTINES:
        fortran_relative = next((path for path in fortran_files if path.endswith(".f")), fortran_files[0])
        return probe_blas1(
            tier=tier,
            repo=repo,
            routine=routine,
            python_relative=python_relative,
            fortran_relative=fortran_relative,
            fortran_repo_path=fortran_repo_path,
        )
    if routine in {"corr", "det", "inverse"}:
        fortran_relative = fortran_files[0]
        return probe_extracted_function(
            tier=tier,
            repo=repo,
            routine=routine,
            python_relative=python_relative,
            fortran_relative=fortran_relative,
            fortran_repo_path=fortran_repo_path,
        )
    for fortran_relative in fortran_files:
        outcome = probe_extracted_function(
            tier=tier,
            repo=repo,
            routine=routine,
            python_relative=python_relative,
            fortran_relative=fortran_relative,
            fortran_repo_path=fortran_repo_path,
        )
        if outcome.status != "skip":
            return outcome
    return ProbeOutcome(
        routine,
        "skip",
        "unsupported",
        None,
        None,
        "No automated Fortran driver for this routine",
        "none",
    )
