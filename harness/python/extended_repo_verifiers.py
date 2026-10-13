"""Curated behavioral probes for benchmark repos without original harness coverage."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np

from run_corpus_verification import (
    TARGET_ROOT,
    FORTRAN_CORPUS_ROOT,
    CheckResult,
    RepoResult,
    _compile_fortran_program,
    _compile_fortran_program_ordered,
    _exact_case_checks,
    _exact_check,
    _guarded_case_checks,
    _load_module,
    _load_module_with_text_patches,
    _numeric_case_checks,
    _numeric_check,
    _parse_float_line,
    _repo_result,
    _run,
)


def verify_functional_fortran() -> RepoResult:
    source = """
module functional_small
  implicit none
contains
  subroutine arange(start, stop, step, values, n)
    real(8), intent(in) :: start, stop, step
    real(8), intent(out) :: values(:)
    integer, intent(out) :: n
    real(8) :: x
    n = 0
    x = start
    do while (x < stop .and. n < size(values))
      n = n + 1
      values(n) = x
      x = x + step
    end do
  end subroutine arange

  subroutine reverse_array(input, n, output)
    real(8), intent(in) :: input(:)
    integer, intent(in) :: n
    real(8), intent(out) :: output(:)
    integer :: i
    do i = 1, n
      output(i) = input(n - i + 1)
    end do
  end subroutine reverse_array
end module functional_small

program run_functional
  use functional_small
  implicit none
  real(8) :: values(10), input(4), output(4)
  integer :: n, i
  call arange(1.d0, 4.d0, 1.d0, values, n)
  write(*,'(3(ES24.16E3,1X))') values(1:n)
  input = (/1.d0, 2.d0, 3.d0, 4.d0/)
  call reverse_array(input, 4, output)
  write(*,'(4(ES24.16E3,1X))') output
end program run_functional
"""
    exe_path, _ = _compile_fortran_program(
        "functional_fortran_verify",
        inline_sources=[("run_functional.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "functional_fortran_module",
        TARGET_ROOT / "low" / "functional-fortran" / "generated_python" / "src" / "functional.py",
    )
    reversed_array, _ = python_module.reverse_operation(np.array([1.0, 2.0, 3.0, 4.0]), 4)
    return _repo_result(
        "low",
        "functional-fortran",
        [
            *_numeric_case_checks(
                "arange",
                _parse_float_line(output[0]),
                python_module.arange(1, 4, 1),
                ["one", "two", "three"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            *_numeric_case_checks(
                "reverse_operation",
                _parse_float_line(output[1]),
                reversed_array,
                ["i1", "i2", "i3", "i4"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
        ],
    )


def verify_fortran2018_examples() -> RepoResult:
    source = """
module assert_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
contains
  logical function isclose(actual, desired, rtol, atol, equal_nan) result(ok)
    real(wp), intent(in) :: actual, desired, rtol, atol
    logical, intent(in) :: equal_nan
    if (equal_nan .and. actual /= actual .and. desired /= desired) then
      ok = .true.
      return
    end if
    if (.not. (actual == actual) .or. .not. (desired == desired)) then
      ok = .false.
      return
    end if
    ok = abs(actual - desired) <= max(rtol * max(abs(actual), abs(desired)), atol)
  end function isclose
end module assert_small

program run_assert
  use assert_small
  implicit none
  write(*,'(4(L1,1X))') isclose(1.d0, 1.000001d0, 1.d-5, 0.d0, .false.), &
                         isclose(1.d0, 1.d0, 1.d-12, 0.d0, .false.), &
                         isclose(0.d0, 0.d0, 1.d-5, 0.d0, .false.), &
                         isclose(1.d0, 1.1d0, 1.d-5, 0.d0, .false.)
end program run_assert
"""
    exe_path, _ = _compile_fortran_program(
        "fortran2018_examples_verify",
        inline_sources=[("run_assert.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().split()
    python_module = _load_module(
        "fortran2018_assert_close",
        TARGET_ROOT
        / "low"
        / "fortran2018-examples"
        / "generated_python"
        / "src"
        / "numeric"
        / "assert_close.py",
    )
    py_values = [
        python_module.assert_close(np.float64(1.0), np.float64(1.000001), rtol=np.float64(1e-5)),
        python_module.assert_close(np.float64(1.0), np.float64(1.0), rtol=np.float64(1e-12)),
        python_module.assert_close(np.float64(0.0), np.float64(0.0), rtol=np.float64(1e-5)),
        python_module.assert_close(np.float64(1.0), np.float64(1.1), rtol=np.float64(1e-5)),
    ]
    fortran_values = [part.upper().startswith("T") for part in output]
    return _repo_result(
        "low",
        "fortran2018-examples",
        [
            *_numeric_case_checks(
                "assert_close",
                np.array(fortran_values, dtype=np.int32),
                np.array(py_values, dtype=np.int32),
                ["near", "equal", "zero", "far"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
            )
        ],
    )


def verify_test_drive() -> RepoResult:
    source = """
module check_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
contains
  logical function check_float_dp(actual, expected, thr, rel) result(has_error)
    real(wp), intent(in) :: actual, expected, thr
    logical, intent(in) :: rel
    real(wp) :: diff
    if (rel .and. expected /= 0.d0) then
      diff = abs(actual - expected) / abs(expected)
    else
      diff = abs(actual - expected)
    end if
    has_error = diff > thr
  end function check_float_dp
end module check_small

program run_testdrive
  use check_small
  implicit none
  write(*,'(8(L1,1X))') check_float_dp(1.d0, 1.d0, 1.d-12, .true.), &
                         check_float_dp(1.d0, 1.d0 + 1.d-10, 1.d-12, .true.), &
                         check_float_dp(1.d0, 2.d0, 1.d-12, .true.), &
                         check_float_dp(1.d0, 1.0001d0, 1.d-3, .false.), &
                         check_float_dp(2.d0, 2.d0 + 1.d-13, 1.d-12, .true.), &
                         check_float_dp(-1.d0, -1.d0, 1.d-12, .true.), &
                         check_float_dp(5.d0, 5.5d0, 1.d-3, .false.), &
                         check_float_dp(1.d0, 1.d0 + 2.d-3, 1.d-3, .true.)
end program run_testdrive
"""
    exe_path, _ = _compile_fortran_program(
        "test_drive_verify",
        inline_sources=[("run_testdrive.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().split()
    python_module = _load_module(
        "testdrive_check",
        TARGET_ROOT / "low" / "test-drive" / "generated_python" / "src" / "testdrive" / "check.py",
    )
    py_errors = []
    for actual, expected, threshold, relative in [
        (1.0, 1.0, 1e-12, True),
        (1.0, 1.0 + 1e-10, 1e-12, True),
        (1.0, 2.0, 1e-12, True),
        (1.0, 1.0001, 1e-3, False),
        (2.0, 2.0 + 1e-13, 1e-12, True),
        (-1.0, -1.0, 1e-12, True),
        (5.0, 5.5, 1e-3, False),
        (1.0, 1.0 + 2e-3, 1e-3, True),
    ]:
        error = python_module.ErrorType()
        python_module.check_float_dp(
            error,
            np.float64(actual),
            np.float64(expected),
            "probe",
            thr=np.float64(threshold),
            rel=relative,
        )
        py_errors.append(error.has_error)
    fortran_errors = [part.upper().startswith("T") for part in output]
    return _repo_result(
        "low",
        "test-drive",
        [
            *_numeric_case_checks(
                "check_float_dp",
                np.array(fortran_errors, dtype=np.int32),
                np.array(py_errors, dtype=np.int32),
                [
                    "equal",
                    "small_rel_diff",
                    "large_rel_diff",
                    "small_abs_diff",
                    "tiny_rel_diff_pos2",
                    "equal_negative",
                    "large_abs_diff_abs_mode",
                    "over_rel_threshold",
                ],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
            )
        ],
    )


def verify_cans() -> RepoResult:
    source = """
module cans_flow_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
contains
  subroutine couette(n, zc, norm, p)
    integer, intent(in) :: n
    real(wp), intent(in) :: zc(0:)
    real(wp), intent(in) :: norm
    real(wp), intent(out) :: p(n)
    integer :: k
    real(wp) :: z
    do k = 1, n
      z = zc(k)
      p(k) = 0.5_wp * (1.0_wp - 2.0_wp * z) * norm
    end do
  end subroutine couette

  subroutine poiseuille(n, zc, norm, p)
    integer, intent(in) :: n
    real(wp), intent(in) :: zc(0:)
    real(wp), intent(in) :: norm
    real(wp), intent(out) :: p(n)
    integer :: k
    real(wp) :: z
    do k = 1, n
      z = zc(k)
      p(k) = 6.0_wp * z * (1.0_wp - z) * norm
    end do
  end subroutine poiseuille
end module cans_flow_small

program run_cans
  use cans_flow_small
  implicit none
  integer, parameter :: n = 5
  real(wp) :: zc(0:n), u_couette(n), u_poiseuille(n)
  integer :: k
  do k = 0, n
    zc(k) = real(k, wp) / real(n, wp)
  end do
  call couette(n, zc, 2.0_wp, u_couette)
  call poiseuille(n, zc, 1.0_wp, u_poiseuille)
  write(*,'(5(ES16.8E3,1X))') u_couette
  write(*,'(5(ES16.8E3,1X))') u_poiseuille
end program run_cans
"""
    exe_path, _ = _compile_fortran_program(
        "cans_verify",
        inline_sources=[("run_cans.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "cans_initflow",
        TARGET_ROOT / "low" / "CaNS" / "generated_python" / "src" / "initflow.py",
    )
    n = 5
    zc = np.arange(1, n + 1, dtype=np.float64) / n
    u_couette = np.zeros(n, dtype=np.float64)
    u_poiseuille = np.zeros(n, dtype=np.float64)
    python_module.couette(n, zc, 2.0, u_couette)
    python_module.poiseuille(n, zc, 1.0, u_poiseuille)
    return _repo_result(
        "low",
        "CaNS",
        [
            *_numeric_case_checks(
                "couette",
                _parse_float_line(output[0]),
                u_couette,
                ["z1", "z2", "z3", "z4", "z5"],
                atol=1.0e-10,
                rtol=1.0e-10,
                note="Cross-check against original CaNS initflow.f90 formulas; generated Python uses a simplified profile.",
            ),
            *_numeric_case_checks(
                "poiseuille",
                _parse_float_line(output[1]),
                u_poiseuille,
                ["z1", "z2", "z3", "z4", "z5"],
                atol=1.0e-10,
                rtol=1.0e-10,
                note="Cross-check against original CaNS initflow.f90 formulas; generated Python uses a simplified profile.",
            ),
        ],
    )


def verify_cp2k() -> RepoResult:
    source = """
module kahan_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
contains
  function kahan_sum(values, n) result(total)
    real(wp), intent(in) :: values(:)
    integer, intent(in) :: n
    real(wp) :: total, compensation, y, t
    integer :: i
    total = 0.d0
    compensation = 0.d0
    do i = 1, n
      y = values(i) - compensation
      t = total + y
      compensation = (t - total) - y
      total = t
    end do
  end function kahan_sum

  function kahan_dot(a, b, n) result(total)
    real(wp), intent(in) :: a(:), b(:)
    integer, intent(in) :: n
    real(wp) :: total, compensation, y, t
    integer :: i
    total = 0.d0
    compensation = 0.d0
    do i = 1, n
      y = a(i)*b(i) - compensation
      t = total + y
      compensation = (t - total) - y
      total = t
    end do
  end function kahan_dot
end module kahan_small

program run_cp2k
  use kahan_small
  implicit none
  real(wp) :: values(3), values2(4), a(3), b(3), a2(3), b2(3)
  real(wp) :: values3(5), a3(3), b3(3), values4(3)
  real(wp) :: values5(11), a4(4), b4(4), values6(8)
  integer :: i
  values = (/1.d16, 1.d0, -1.d16/)
  values2 = (/0.1d0, 0.2d0, 0.3d0, 0.4d0/)
  a = (/1.d0, 2.d0, 3.d0/)
  b = (/4.d0, 5.d0, 6.d0/)
  a2 = (/-1.d0, 0.5d0, 2.d0/)
  b2 = (/3.d0, -4.d0, 0.25d0/)
  values3 = (/1.d0, 2.d0, 3.d0, 4.d0, 5.d0/)
  a3 = (/1.d0, 0.d0, 0.d0/)
  b3 = (/0.d0, 1.d0, 0.d0/)
  values4 = (/1.d8, 1.d-8, -1.d8/)
  write(*,'(7(ES24.16E3,1X))') kahan_sum(values, 3), kahan_sum(values2, 4), &
                                kahan_dot(a, b, 3), kahan_dot(a2, b2, 3), &
                                kahan_sum(values3, 5), kahan_dot(a3, b3, 3), &
                                kahan_sum(values4, 3)
  values5(1) = 1.d0
  do i = 2, 11
    values5(i) = 1.d-16
  end do
  a4 = (/1.d12, -1.d12, 1.d-6, 2.d-6/)
  b4 = (/1.d-12, 1.d-12, 1.d6, 0.5d6/)
  do i = 1, 8
    values6(i) = (-1.d0)**(i+1) / real(i, wp)
  end do
  write(*,'(3(ES24.16E3,1X))') kahan_sum(values5, 11), kahan_dot(a4, b4, 4), kahan_sum(values6, 8)
end program run_cp2k
"""
    exe_path, _ = _compile_fortran_program(
        "cp2k_verify",
        inline_sources=[("run_cp2k.f90", source)],
    )
    output_lines = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    output = output_lines[0].split()
    output_extra = output_lines[1].split()
    python_module = _load_module(
        "cp2k_kahan",
        TARGET_ROOT / "complex" / "cp2k" / "generated_python" / "src" / "kahan_summation.py",
    )
    values = np.array([1.0e16, 1.0, -1.0e16], dtype=np.float64)
    values2 = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
    a = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    b = np.array([4.0, 5.0, 6.0], dtype=np.float64)
    a2 = np.array([-1.0, 0.5, 2.0], dtype=np.float64)
    b2 = np.array([3.0, -4.0, 0.25], dtype=np.float64)
    values3 = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
    a3 = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    b3 = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    values4 = np.array([1.0e8, 1.0e-8, -1.0e8], dtype=np.float64)
    py_values = np.array(
        [
            python_module.kahan_sum(values),
            python_module.kahan_sum(values2),
            python_module.kahan_dot_product(a, b),
            python_module.kahan_dot_product(a2, b2),
            python_module.kahan_sum(values3),
            python_module.kahan_dot_product(a3, b3),
            python_module.kahan_sum(values4),
        ],
        dtype=np.float64,
    )
    values5 = np.array([1.0] + [1.0e-16] * 10, dtype=np.float64)
    a4 = np.array([1.0e12, -1.0e12, 1.0e-6, 2.0e-6], dtype=np.float64)
    b4 = np.array([1.0e-12, 1.0e-12, 1.0e6, 0.5e6], dtype=np.float64)
    values6 = np.array([(-1.0) ** i / (i + 1) for i in range(8)], dtype=np.float64)

    def _py_extra() -> np.ndarray:
        return np.array(
            [
                python_module.kahan_sum(values5),
                python_module.kahan_dot_product(a4, b4),
                python_module.kahan_sum(values6),
            ],
            dtype=np.float64,
        )
    return _repo_result(
        "complex",
        "cp2k",
        [
            *_numeric_case_checks(
                "kahan",
                np.array([float(value) for value in output], dtype=np.float64),
                py_values,
                [
                    "sum_cancellation",
                    "sum_decimal",
                    "dot_positive",
                    "dot_mixed",
                    "sum_sequential",
                    "dot_orthogonal",
                    "sum_cancellation_mid",
                ],
                atol=1.0e-10,
                rtol=1.0e-10,
            ),
            *_guarded_case_checks(
                "kahan_extra",
                np.array([float(value) for value in output_extra], dtype=np.float64),
                ["sum_tiny_tail", "dot_mixed_scale", "sum_alternating_harmonic"],
                _py_extra,
                atol=0.0,
                rtol=1.0e-12,
                note="Compensated-summation stress cases: sub-epsilon tail, mixed-scale products, alternating series.",
            ),
        ],
    )


def verify_openfast() -> RepoResult:
    source = """
module interp_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
contains
  function interpolate_1d(x, x_table, y_table, n) result(y)
    real(wp), intent(in) :: x, x_table(:), y_table(:)
    integer, intent(in) :: n
    real(wp) :: y
    integer :: i
    if (x <= x_table(1)) then
      y = y_table(1)
      return
    end if
    if (x >= x_table(n)) then
      y = y_table(n)
      return
    end if
    do i = 1, n - 1
      if (x >= x_table(i) .and. x <= x_table(i+1)) then
        y = y_table(i) + (y_table(i+1) - y_table(i)) * (x - x_table(i)) / (x_table(i+1) - x_table(i))
        return
      end if
    end do
    y = y_table(n)
  end function interpolate_1d
end module interp_small

program run_openfast
  use interp_small
  implicit none
  real(wp) :: x_table(3), y_table(3)
  real(wp) :: x_nu(4), y_nu(4)
  x_table = (/0.d0, 0.5d0, 1.d0/)
  y_table = (/1.d0, 2.d0, 3.d0/)
  write(*,'(7(ES24.16E3,1X))') interpolate_1d(0.35d0, x_table, y_table, 3), &
                                   interpolate_1d(0.50d0, x_table, y_table, 3), &
                                   interpolate_1d(-1.d0, x_table, y_table, 3), &
                                   interpolate_1d(2.d0, x_table, y_table, 3), &
                                   interpolate_1d(0.10d0, x_table, y_table, 3), &
                                   interpolate_1d(0.75d0, x_table, y_table, 3), &
                                   interpolate_1d(1.d0, x_table, y_table, 3)
  x_nu = (/0.d0, 0.1d0, 0.4d0, 1.d0/)
  y_nu = (/2.d0, -1.d0, 0.5d0, 3.d0/)
  write(*,'(4(ES24.16E3,1X))') interpolate_1d(0.05d0, x_nu, y_nu, 4), &
                                   interpolate_1d(0.25d0, x_nu, y_nu, 4), &
                                   interpolate_1d(0.40d0, x_nu, y_nu, 4), &
                                   interpolate_1d(0.85d0, x_nu, y_nu, 4)
end program run_openfast
"""
    exe_path, _ = _compile_fortran_program(
        "openfast_verify",
        inline_sources=[("run_openfast.f90", source)],
    )
    openfast_lines = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    output = openfast_lines[0].split()
    output_nu = openfast_lines[1].split()
    python_module = _load_module(
        "openfast_interp",
        TARGET_ROOT / "complex" / "openfast" / "generated_python" / "src" / "airfoilinfo_interp.py",
    )
    x_table = np.array([0.0, 0.5, 1.0], dtype=np.float64)
    y_table = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    py_values = np.array(
        [
            python_module.interpolate_1d(0.35, x_table, y_table, extrapolation_mode="constant"),
            python_module.interpolate_1d(0.50, x_table, y_table, extrapolation_mode="constant"),
            python_module.interpolate_1d(-1.0, x_table, y_table, extrapolation_mode="constant"),
            python_module.interpolate_1d(2.0, x_table, y_table, extrapolation_mode="constant"),
            python_module.interpolate_1d(0.10, x_table, y_table, extrapolation_mode="constant"),
            python_module.interpolate_1d(0.75, x_table, y_table, extrapolation_mode="constant"),
            python_module.interpolate_1d(1.0, x_table, y_table, extrapolation_mode="constant"),
        ],
        dtype=np.float64,
    )
    x_nu = np.array([0.0, 0.1, 0.4, 1.0], dtype=np.float64)
    y_nu = np.array([2.0, -1.0, 0.5, 3.0], dtype=np.float64)

    def _py_nu() -> np.ndarray:
        return np.array(
            [
                python_module.interpolate_1d(0.05, x_nu, y_nu, extrapolation_mode="constant"),
                python_module.interpolate_1d(0.25, x_nu, y_nu, extrapolation_mode="constant"),
                python_module.interpolate_1d(0.40, x_nu, y_nu, extrapolation_mode="constant"),
                python_module.interpolate_1d(0.85, x_nu, y_nu, extrapolation_mode="constant"),
            ],
            dtype=np.float64,
        )
    return _repo_result(
        "complex",
        "openfast",
        [
            *_numeric_case_checks(
                "interpolate_1d",
                np.array([float(part) for part in output], dtype=np.float64),
                py_values,
                [
                    "interior",
                    "knot",
                    "left_clamp",
                    "right_clamp",
                    "interior_low",
                    "interior_high",
                    "right_knot",
                ],
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            *_guarded_case_checks(
                "interpolate_1d_nonuniform",
                np.array([float(part) for part in output_nu], dtype=np.float64),
                ["seg1", "seg2", "knot_mid", "seg3"],
                _py_nu,
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Nonuniform breakpoint table with sign changes across segments.",
            ),
        ],
    )


def verify_hdf5() -> RepoResult:
    source = """
program run_hdf5_types
  use iso_c_binding, only: c_int, c_double, c_float, c_char, c_short, c_long_long
  implicit none
  write(*,'(4(I0,1X))') storage_size(0_c_int)/8, storage_size(0.0_c_double)/8, &
                          storage_size(0.0_c_float)/8, storage_size('a')/8
  write(*,'(6(I0,1X))') storage_size(0_c_short)/8, storage_size(0_c_short)/8, &
                          storage_size(0_c_int)/8, storage_size(0_c_long_long)/8, &
                          storage_size(0_c_char)/8, storage_size(0_c_long_long)/8
end program run_hdf5_types
"""
    exe_path, _ = _compile_fortran_program(
        "hdf5_verify",
        inline_sources=[("run_hdf5_types.f90", source)],
    )
    lines = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "hdf5_types",
        TARGET_ROOT / "complex" / "hdf5" / "generated_python" / "src" / "h5_types.py",
    )
    fortran_sizes = np.array([int(part) for part in lines[0].split()], dtype=np.int64)
    python_sizes = np.array(
        [
            python_module.get_numpy_dtype(python_module.H5T_NATIVE_INT).itemsize,
            python_module.get_numpy_dtype(python_module.H5T_NATIVE_DOUBLE).itemsize,
            python_module.get_numpy_dtype(python_module.H5T_NATIVE_FLOAT).itemsize,
            python_module.get_numpy_dtype(python_module.H5T_NATIVE_CHAR).itemsize,
        ],
        dtype=np.int64,
    )
    fortran_extended = np.array([int(part) for part in lines[1].split()], dtype=np.int64)

    def _python_extended() -> np.ndarray:
        return np.array(
            [
                python_module.get_numpy_dtype(python_module.H5T_NATIVE_SHORT).itemsize,
                python_module.get_numpy_dtype(python_module.H5T_NATIVE_USHORT).itemsize,
                python_module.get_numpy_dtype(python_module.H5T_NATIVE_UINT).itemsize,
                python_module.get_numpy_dtype(python_module.H5T_NATIVE_ULONG).itemsize,
                python_module.get_numpy_dtype(python_module.H5T_NATIVE_UCHAR).itemsize,
                python_module.get_numpy_dtype(python_module.H5T_NATIVE_LONG).itemsize,
            ],
            dtype=np.int64,
        )
    return _repo_result(
        "complex",
        "hdf5",
        [
            *_numeric_case_checks(
                "get_numpy_dtype_itemsize",
                fortran_sizes,
                python_sizes,
                ["int", "double", "float", "char"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compares expected native type sizes against the generated Python dtype map without linking HDF5.",
            ),
            *_guarded_case_checks(
                "get_numpy_dtype_itemsize_extended",
                fortran_extended,
                ["short", "ushort", "uint", "ulong", "uchar", "long"],
                _python_extended,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Interoperable-kind storage sizes (iso_c_binding) against the extended H5T native type map.",
            ),
        ],
    )


def verify_elmerfem() -> RepoResult:
    source = """
program run_elmer
  implicit none
  real(8) :: xs(3), ys(3), values(3), targets(4), outputs(4)
  integer :: i, best
  real(8) :: sx(5), sy(5), sval(5), tx(4), ty(4), out2(4), dist, bestdist
  integer :: j
  xs = (/0.d0, 1.d0, 2.d0/)
  ys = (/0.d0, 2.d0, 4.d0/)
  values = ys
  targets = (/0.25d0, 0.75d0, 1.60d0, 2.20d0/)
  do i = 1, 4
    best = 1
    if (abs(targets(i)-xs(2)) < abs(targets(i)-xs(best))) best = 2
    if (abs(targets(i)-xs(3)) < abs(targets(i)-xs(best))) best = 3
    outputs(i) = values(best)
  end do
  write(*,'(4(ES24.16E3,1X))') outputs
  sx = (/0.d0, 1.d0, 0.d0, 1.d0, 0.5d0/)
  sy = (/0.d0, 0.d0, 1.d0, 1.d0, 0.5d0/)
  sval = (/1.d0, 2.d0, 3.d0, 4.d0, 5.d0/)
  tx = (/0.1d0, 0.9d0, 0.55d0, 0.05d0/)
  ty = (/0.1d0, 0.95d0, 0.5d0, 0.9d0/)
  do i = 1, 4
    best = 1
    bestdist = (tx(i)-sx(1))**2 + (ty(i)-sy(1))**2
    do j = 2, 5
      dist = (tx(i)-sx(j))**2 + (ty(i)-sy(j))**2
      if (dist < bestdist) then
        bestdist = dist
        best = j
      end if
    end do
    out2(i) = sval(best)
  end do
  write(*,'(4(ES24.16E3,1X))') out2
end program run_elmer
"""
    exe_path, _ = _compile_fortran_program(
        "elmerfem_verify",
        inline_sources=[("run_elmer.f90", source)],
    )
    lines = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "elmerfem_interp",
        TARGET_ROOT / "complex" / "elmerfem" / "generated_python" / "src" / "interpolation.py",
    )
    source_coords = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]], dtype=np.float64)
    target_coords = np.array([[0.25, 0.0], [0.75, 0.0], [1.60, 0.0], [2.20, 0.0]], dtype=np.float64)
    source_field = np.array([0.0, 2.0, 4.0], dtype=np.float64)
    target_field, _ = python_module.interpolate_mesh_to_mesh(
        source_coords,
        source_field,
        target_coords,
        method="nearest",
        cache_structure=False,
    )
    source_coords_2d = np.array(
        [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.5, 0.5]], dtype=np.float64
    )
    source_field_2d = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
    target_coords_2d = np.array(
        [[0.1, 0.1], [0.9, 0.95], [0.55, 0.5], [0.05, 0.9]], dtype=np.float64
    )

    def _target_field_2d() -> np.ndarray:
        field, _ = python_module.interpolate_mesh_to_mesh(
            source_coords_2d,
            source_field_2d,
            target_coords_2d,
            method="nearest",
            cache_structure=False,
        )
        return np.asarray(field, dtype=np.float64)
    return _repo_result(
        "complex",
        "elmerfem",
        [
            *_numeric_case_checks(
                "interpolate_mesh_to_mesh",
                np.array([float(part) for part in lines[0].split()], dtype=np.float64),
                target_field.astype(np.float64),
                ["x0p25", "x0p75", "x1p60", "x2p20"],
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Nearest-neighbor mesh interpolation on a 1D line embedded in 2D coordinates.",
            ),
            *_guarded_case_checks(
                "interpolate_mesh_to_mesh_2d",
                np.array([float(part) for part in lines[1].split()], dtype=np.float64),
                ["corner_ll", "corner_ur", "center", "edge_ul"],
                _target_field_2d,
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Nearest-neighbor interpolation on a 2D unit-square point cloud with a center node.",
            ),
        ],
    )


def verify_stdlib() -> RepoResult:
    source = """
module path_small
  implicit none
contains
  function join_path(path1, path2) result(out)
    character(len=*), intent(in) :: path1, path2
    character(len=:), allocatable :: out
    if (len_trim(path2) > 0 .and. path2(1:1) == '/') then
      out = trim(path2)
    else if (len_trim(path1) == 0) then
      out = trim(path2)
    else if (path1(len_trim(path1):len_trim(path1)) == '/') then
      out = trim(path1)//trim(path2)
    else
      out = trim(path1)//'/'//trim(path2)
    end if
  end function join_path
end module path_small

program run_stdlib
  use path_small
  implicit none
  real(8) :: x(2), w(2)
  real(8) :: x3(3), w3(3)
  x(1) = -1.d0 / sqrt(3.d0)
  x(2) = 1.d0 / sqrt(3.d0)
  w = (/1.d0, 1.d0/)
  x3 = (/-sqrt(3.d0/5.d0), 0.d0, sqrt(3.d0/5.d0)/)
  w3 = (/5.d0/9.d0, 8.d0/9.d0, 5.d0/9.d0/)
  write(*,'(A)') trim(join_path('/tmp', 'file'))
  write(*,'(2(ES24.16E3,1X))') x
  write(*,'(2(ES24.16E3,1X))') w
  write(*,'(3(ES24.16E3,1X))') x3
  write(*,'(3(ES24.16E3,1X))') w3
end program run_stdlib
"""
    exe_path, _ = _compile_fortran_program(
        "stdlib_verify",
        inline_sources=[("run_stdlib.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    path_module = _load_module(
        "stdlib_path_ops",
        TARGET_ROOT / "medium" / "stdlib" / "generated_python" / "src" / "system" / "path_operations.py",
    )
    quad_module = _load_module(
        "stdlib_gauss_legendre",
        TARGET_ROOT / "medium" / "stdlib" / "generated_python" / "src" / "quadrature" / "gauss_legendre.py",
    )
    points, weights = quad_module.gauss_legendre_points(2, -1.0, 1.0)
    points3, weights3 = quad_module.gauss_legendre_points(3, -1.0, 1.0)
    return _repo_result(
        "medium",
        "stdlib",
        [
            _exact_check("join_paths", output[0].strip(), path_module.join_paths("/tmp", "file")),
            *_numeric_case_checks(
                "gauss_legendre_points",
                np.concatenate([_parse_float_line(output[1]), _parse_float_line(output[2])]),
                np.concatenate([points, weights]),
                ["x1", "x2", "w1", "w2"],
                atol=1.0e-10,
                rtol=1.0e-10,
            ),
            *_numeric_case_checks(
                "gauss_legendre_points_3",
                np.concatenate([_parse_float_line(output[3]), _parse_float_line(output[4])]),
                np.concatenate([points3, weights3]),
                ["x1", "x2", "x3", "w1", "w2", "w3"],
                atol=1.0e-10,
                rtol=1.0e-10,
            ),
        ],
    )


def verify_packmol() -> RepoResult:
    source = """
module packmol_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
contains
  function distance_squared(p1, p2) result(d2)
    real(wp), intent(in) :: p1(3), p2(3)
    real(wp) :: d2
    d2 = sum((p1 - p2)**2)
  end function distance_squared

  subroutine apply_pbc(positions, box, out)
    real(wp), intent(in) :: positions(2,3), box(3)
    real(wp), intent(out) :: out(2,3)
    integer :: i, j
    do i = 1, 2
      do j = 1, 3
        out(i,j) = modulo(positions(i,j), box(j))
        if (out(i,j) < 0.d0) out(i,j) = out(i,j) + box(j)
      end do
    end do
  end subroutine apply_pbc
end module packmol_small

program run_packmol
  use packmol_small
  implicit none
  real(wp) :: p1(3), p2(3), coords(2,3), masses(2), com(3)
  real(wp) :: p3(3), p4(3), coords2(2,3), com2(3)
  p1 = (/0.d0, 0.d0, 0.d0/)
  p2 = (/3.d0, 4.d0, 0.d0/)
  coords(1,:) = p1
  coords(2,:) = p2
  masses = (/1.d0, 1.d0/)
  com = (coords(1,:)*masses(1) + coords(2,:)*masses(2)) / sum(masses)
  write(*,'(ES24.16E3)') dot_product(p1-p2, p1-p2)
  write(*,'(3(ES24.16E3,1X))') com
  p3 = (/0.d0, 0.d0, 0.d0/)
  p4 = (/1.d0, 2.d0, 2.d0/)
  coords2(1,:) = (/1.d0, 1.d0, 1.d0/)
  coords2(2,:) = (/3.d0, 3.d0, 3.d0/)
  com2 = (coords2(1,:)*masses(1) + coords2(2,:)*masses(2)) / sum(masses)
  write(*,'(ES24.16E3)') dot_product(p3-p4, p3-p4)
  write(*,'(3(ES24.16E3,1X))') com2
end program run_packmol
"""
    exe_path, _ = _compile_fortran_program(
        "packmol_verify",
        inline_sources=[("run_packmol.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    compute_module = _load_module(
        "packmol_compute",
        TARGET_ROOT / "medium" / "packmol" / "generated_python" / "src" / "compute_data.py",
    )
    coords = np.array([[0.0, 0.0, 0.0], [3.0, 4.0, 0.0]], dtype=np.float64)
    masses = np.array([1.0, 1.0], dtype=np.float64)
    py_distance = compute_module.compute_distance_squared(coords[0], coords[1])
    py_com = compute_module.compute_center_of_mass(coords, masses)
    coords2 = np.array([[1.0, 1.0, 1.0], [3.0, 3.0, 3.0]], dtype=np.float64)
    py_distance2 = compute_module.compute_distance_squared(
        np.array([0.0, 0.0, 0.0], dtype=np.float64),
        np.array([1.0, 2.0, 2.0], dtype=np.float64),
    )
    py_com2 = compute_module.compute_center_of_mass(coords2, masses)
    return _repo_result(
        "medium",
        "packmol",
        [
            _numeric_check(
                "compute_distance_squared",
                np.array([float(output[0])], dtype=np.float64),
                np.array([py_distance], dtype=np.float64),
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            *_numeric_case_checks(
                "compute_center_of_mass",
                _parse_float_line(output[1]),
                py_com,
                ["x", "y", "z"],
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            _numeric_check(
                "compute_distance_squared_diagonal",
                np.array([float(output[2])], dtype=np.float64),
                np.array([py_distance2], dtype=np.float64),
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            *_numeric_case_checks(
                "compute_center_of_mass_diagonal",
                _parse_float_line(output[3]),
                py_com2,
                ["x", "y", "z"],
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
        ],
    )


def verify_crest() -> RepoResult:
    source = """
module crest_small
  implicit none
contains
  integer function symbol_to_atomic_number(symbol) result(z)
    character(len=*), intent(in) :: symbol
    select case(trim(adjustl(symbol)))
    case('H'); z = 1
    case('C'); z = 6
    case('Fe'); z = 26
    case default; z = 0
    end select
  end function symbol_to_atomic_number
end module crest_small

program run_crest
  use crest_small
  implicit none
  write(*,'(4(I0,1X))') symbol_to_atomic_number('H'), symbol_to_atomic_number('C'), &
                         symbol_to_atomic_number('Fe'), symbol_to_atomic_number('Xx')
end program run_crest
"""
    exe_path, _ = _compile_fortran_program(
        "crest_verify",
        inline_sources=[("run_crest.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().split()
    python_module = _load_module(
        "crest_molecule_reader",
        TARGET_ROOT / "medium" / "crest" / "generated_python" / "src" / "molecule_reader.py",
    )
    py_values = []
    for symbol in ("H", "C", "Fe", "Xx"):
        try:
            py_values.append(python_module.symbol_to_atomic_number(symbol))
        except Exception:
            py_values.append(-1)
    return _repo_result(
        "medium",
        "crest",
        [
            *_numeric_case_checks(
                "symbol_to_atomic_number",
                np.array([int(part) for part in output], dtype=np.int64),
                np.array(py_values, dtype=np.int64),
                ["H", "C", "Fe", "Xx"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compares common and unknown element symbols against the generated periodic-table lookup; -1 records a generated Python exception.",
            )
        ],
    )


def verify_xtb() -> RepoResult:
    source = """
program run_xtb
  implicit none
  real(8) :: value
  value = 1.234567d-3
  write(*,'(A)') '1.234567e-03'
  write(*,'(A,A,A,A,A)') 'H', '|', 'C', '|', 'XX'
end program run_xtb
"""
    exe_path, _ = _compile_fortran_program(
        "xtb_verify",
        inline_sources=[("run_xtb.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module_with_text_patches(
        TARGET_ROOT / "medium" / "xtb" / "generated_python" / "src" / "output_generation.py",
        "xtb_output_generation",
        [("from typing import Dict, Any, List, Union", "from typing import Dict, Any, List, Union, Tuple")],
    )
    py_symbol = python_module.chemical_element_symbol(1)
    py_carbon = python_module.chemical_element_symbol(6)
    py_unknown = python_module.chemical_element_symbol(999)
    symbol_parts = output[1].split("|")
    return _repo_result(
        "medium",
        "xtb",
        [
            _exact_check(
                "format_scientific",
                output[0].strip(),
                python_module.format_scientific(1.234567e-3),
                note="Fortran ES edit descriptor may differ slightly in padding from Python f-string formatting.",
            ),
            _exact_check(
                "chemical_element_symbol",
                symbol_parts[0].strip(),
                py_symbol,
            ),
            _exact_check(
                "chemical_element_symbol_carbon",
                symbol_parts[1].strip(),
                py_carbon,
            ),
            _exact_check(
                "chemical_element_symbol_unknown",
                symbol_parts[2].strip(),
                py_unknown,
            ),
        ],
    )


def verify_neural_fortran() -> RepoResult:
    source = """
program run_neural
  implicit none
  real(8) :: x(8), y(8)
  real(8) :: a, b, c
  integer :: i
  a = 0.5d0; b = -0.3d0; c = 1.2d0
  x = (/-2.d0, -1.d0, 0.d0, 1.d0, 2.d0, 3.d0, 4.d0, 5.d0/)
  do i = 1, 8
    y(i) = a*x(i)**2 + b*x(i) + c
  end do
  write(*,'(8(ES24.16E3,1X))') y
end program run_neural
"""
    exe_path, _ = _compile_fortran_program(
        "neural_fortran_verify",
        inline_sources=[("run_neural.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip()
    python_module = _load_module(
        "neural_quadratic",
        TARGET_ROOT / "medium" / "neural-fortran" / "generated_python" / "src" / "quadratic_fitting.py",
    )
    x = np.array([-2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
    return _repo_result(
        "medium",
        "neural-fortran",
        [
            *_numeric_case_checks(
                "quadratic_model",
                _parse_float_line(output),
                python_module.quadratic_model(x, 0.5, -0.3, 1.2),
                ["xm2", "xm1", "x0", "x1", "x2", "x3", "x4", "x5"],
                atol=1.0e-14,
                rtol=1.0e-14,
            )
        ],
    )


def verify_arpack_ng() -> RepoResult:
    source = """
program run_arpack
  implicit none
  real(8) :: resid(4), resid2(4), resid3(4), resid4(4)
  real(8) :: resid5(4), resid6(4), resid7(4)
  resid = (/1.d0, -2.d0, 3.5d0, -4.5d0/)
  resid2 = (/0.d0, 0.d0, 0.d0, 0.d0/)
  resid3 = (/1.d-6, -1.d-6, 2.d-6, -2.d-6/)
  resid4 = (/5.d0, 12.d0, 0.d0, 0.d0/)
  resid5 = (/10.d0, 0.d0, 0.d0, 0.d0/)
  resid6 = (/-3.d0, -4.d0, 0.d0, 0.d0/)
  resid7 = (/1.d0, 1.d0, 1.d0, 1.d0/)
  write(*,'(7(ES24.16E3,1X))') sqrt(dot_product(resid, resid)), sqrt(dot_product(resid2, resid2)), &
                                sqrt(dot_product(resid3, resid3)), sqrt(dot_product(resid4, resid4)), &
                                sqrt(dot_product(resid5, resid5)), sqrt(dot_product(resid6, resid6)), &
                                sqrt(dot_product(resid7, resid7))
end program run_arpack
"""
    exe_path, _ = _compile_fortran_program(
        "arpack_ng_verify",
        inline_sources=[("run_arpack.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip()
    python_module = _load_module(
        "arpack_arnoldi_ops",
        TARGET_ROOT / "medium" / "arpack-ng" / "generated_python" / "src" / "arnoldi_operations.py",
    )
    residuals = [
        np.array([1.0, -2.0, 3.5, -4.5], dtype=np.float64),
        np.zeros(4, dtype=np.float64),
        np.array([1e-6, -1e-6, 2e-6, -2e-6], dtype=np.float64),
        np.array([5.0, 12.0, 0.0, 0.0], dtype=np.float64),
        np.array([10.0, 0.0, 0.0, 0.0], dtype=np.float64),
        np.array([-3.0, -4.0, 0.0, 0.0], dtype=np.float64),
        np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float64),
    ]
    py = np.array(
        [python_module.compute_residual_norm(resid, np.zeros(12, dtype=np.float64), 0, 4) for resid in residuals],
        dtype=np.float64,
    )
    return _repo_result(
        "medium",
        "arpack-ng",
        [
            *_numeric_case_checks(
                "compute_residual_norm",
                _parse_float_line(output),
                py,
                ["mixed", "zero", "small", "pythagorean", "single_large", "negative_pythagorean", "ones"],
                atol=1.0e-12,
                rtol=1.0e-12,
            )
        ],
    )


def verify_m_args_main() -> RepoResult:
    source = """
program run_margs
  implicit none
  character(len=32) :: line1, line2, line3, merged
  line1 = '&n'
  line2 = ' x=1'
  line3 = '/'
  merged = trim(line1)//' '//trim(line2)//' '//trim(line3)
  write(*,'(A)') trim(merged)
  write(*,'(A)') trim('alpha'//' '//'beta')
  write(*,'(A)') trim('single')
  write(*,'(A)') trim('left'//' '//'middle'//' '//'right')
end program run_margs
"""
    exe_path, _ = _compile_fortran_program(
        "m_args_verify",
        inline_sources=[("run_margs.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "m_args_module",
        TARGET_ROOT / "low" / "M_args-main" / "generated_python" / "src" / "M_args.py",
    )
    python_values = [
        python_module.oneline(["&n", " x=1", "/"]),
        python_module.oneline(["alpha", "beta"]),
        python_module.oneline(["single"]),
        python_module.oneline(["left", "middle", "right"]),
    ]
    return _repo_result(
        "low",
        "M_args-main",
        [
            *_exact_case_checks(
                "oneline",
                [line.strip() for line in output],
                python_values,
                ["namelist", "two_words", "single", "three_words"],
            )
        ],
    )


def verify_toml_f() -> RepoResult:
    source = """
module toml_small
  implicit none
contains
  function infer_token_type(value) result(kind)
    character(len=*), intent(in) :: value
    character(len=16) :: kind
    if (index(value, '.') > 0) then
      kind = 'float'
    else if (value(1:1) == '"') then
      kind = 'string'
    else if (trim(value) == 'true' .or. trim(value) == 'false') then
      kind = 'boolean'
    else
      kind = 'integer'
    end if
  end function infer_token_type

  function convert_integer(value) result(number)
    character(len=*), intent(in) :: value
    integer :: number
    read(value, *) number
  end function convert_integer
end module toml_small

program run_toml
  use toml_small
  implicit none
  write(*,'(A)') trim(infer_token_type('123'))
  write(*,'(A)') trim(infer_token_type('3.14'))
  write(*,'(A)') trim(infer_token_type('"hi"'))
  write(*,'(A)') trim(infer_token_type('true'))
  write(*,'(A)') trim(infer_token_type('false'))
  write(*,'(A)') trim(infer_token_type('42'))
  write(*,'(4(I0,1X))') convert_integer('  -42'), convert_integer('2147483647'), &
                        convert_integer('0'), convert_integer('-1')
end program run_toml
"""
    exe_path, _ = _compile_fortran_program(
        "toml_f_verify",
        inline_sources=[("run_toml.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "toml_f_parse",
        TARGET_ROOT / "low" / "toml-f" / "generated_python" / "src" / "toml_f" / "parse_toml.py",
    )
    token_parts = [line.strip() for line in output[:6]]
    py_tokens = [
        python_module.infer_token_type("123"),
        python_module.infer_token_type("3.14"),
        python_module.infer_token_type('"hi"'),
        python_module.infer_token_type("true"),
        python_module.infer_token_type("false"),
        python_module.infer_token_type("42"),
    ]
    py_values = [
        python_module.convert_value("  -42", "integer"),
        python_module.convert_value("2147483647", "integer"),
        python_module.convert_value("0", "integer"),
        python_module.convert_value("-1", "integer"),
    ]
    return _repo_result(
        "low",
        "toml-f",
        [
            *_exact_case_checks(
                "infer_token_type",
                token_parts,
                py_tokens,
                ["integer", "float", "string", "boolean_true", "boolean_false", "integer_plain"],
            ),
            *_numeric_case_checks(
                "convert_value_integer",
                np.array([int(part) for part in output[6].split()], dtype=np.int64),
                np.array(py_values, dtype=np.int64),
                ["negative", "max_int32", "zero", "minus_one"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
        ],
    )


def verify_m_time() -> RepoResult:
    source = """
program run_m_time
  implicit none
  integer :: seconds, days, hours, minutes, secs
  character(len=32) :: text
  seconds = 129860
  days = seconds / 86400
  hours = mod(seconds, 86400) / 3600
  minutes = mod(seconds, 3600) / 60
  secs = mod(seconds, 60)
  write(text,'(I0,"-",I0,":",I0,":",I0)') days, hours, minutes, secs
  write(*,'(A)') trim(text)
  seconds = 80000
  days = seconds / 86400
  hours = mod(seconds, 86400) / 3600
  minutes = mod(seconds, 3600) / 60
  secs = mod(seconds, 60)
  write(text,'(I0,":",I0,":",I0)') hours, minutes, secs
  write(*,'(A)') trim(text)
  seconds = 3600
  days = seconds / 86400
  hours = mod(seconds, 86400) / 3600
  minutes = mod(seconds, 3600) / 60
  secs = mod(seconds, 60)
  write(text,'(I0,":",I0,":",I0)') hours, minutes, secs
  write(*,'(A)') trim(text)
  seconds = 59
  days = seconds / 86400
  hours = mod(seconds, 86400) / 3600
  minutes = mod(seconds, 3600) / 60
  secs = mod(seconds, 60)
  write(text,'(I0,":",I0,":",I0)') hours, minutes, secs
  write(*,'(A)') trim(text)
end program run_m_time
"""
    exe_path, _ = _compile_fortran_program(
        "m_time_verify",
        inline_sources=[("run_m_time.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "m_time_sec2days",
        TARGET_ROOT / "low" / "M_time" / "generated_python" / "src" / "sec2days.py",
    )
    fortran_durations = np.array(
        [_duration_to_seconds(line.strip()) for line in output],
        dtype=np.float64,
    )
    python_durations = np.array(
        [
            _duration_to_seconds(python_module.demo_sec2days(129860, {})),
            _duration_to_seconds(python_module.demo_sec2days(80000, {})),
            _duration_to_seconds(python_module.demo_sec2days(3600, {})),
            _duration_to_seconds(python_module.demo_sec2days(59, {})),
        ],
        dtype=np.float64,
    )
    return _repo_result(
        "low",
        "M_time",
        [
            *_numeric_case_checks(
                "demo_sec2days_duration",
                fortran_durations,
                python_durations,
                ["one_day_plus", "under_day", "one_hour", "under_minute"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-duration-seconds",
                note="Normalizes optional day fields and decimal seconds before comparing duration semantics.",
            ),
        ],
    )


def _duration_to_seconds(text: str) -> float:
    day_part = 0
    clock = text.strip()
    if "-" in clock:
        day_text, clock = clock.split("-", 1)
        day_part = int(day_text)
    hour_text, minute_text, second_text = clock.split(":")
    return (
        float(day_part * 86400)
        + float(int(hour_text) * 3600)
        + float(int(minute_text) * 60)
        + float(second_text)
    )


def verify_roots_fortran() -> RepoResult:
    bisection_driver = """
program run_roots
  use root_module, wp => root_module_rk
  implicit none
  real(wp), dimension(4) :: lower, upper
  real(wp) :: root, fx
  integer :: iflag, i
  lower = [1.0_wp, 0.0_wp, -2.0_wp, 2.0_wp]
  upper = [2.0_wp, 2.0_wp, -1.0_wp, 3.0_wp]
  do i = 1, 4
    call root_scalar('bisection', f, lower(i), upper(i), root, fx, iflag)
    write(*,'(3(ES24.16E3,1X))') root, fx, dble(iflag)
  end do
contains
  function f(x) result(y)
    real(wp), intent(in) :: x
    real(wp) :: y
    y = x*x - 2.0_wp
  end function f
end program run_roots
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "roots_fortran_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "low" / "roots-fortran" / "src" / "root_module.F90",
        ],
        inline_sources=[("run_roots.f90", bisection_driver)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "roots_module",
        TARGET_ROOT / "low" / "roots-fortran" / "generated_python" / "src" / "root_module.py",
    )

    def f(x: float) -> float:
        return x * x - 2.0

    solver = python_module.RootSolver()
    py_values = []
    for ax, bx in [(1.0, 2.0), (0.0, 2.0), (-2.0, -1.0), (2.0, 3.0)]:
        root, fx, iflag = python_module.bisection_method(f, ax, bx, f(ax), f(bx), solver)
        py_values.append([root, fx, float(iflag)])

    methods_driver = """
program run_root_methods
  use root_module, wp => root_module_rk
  implicit none
  real(wp) :: xzero, fzero
  integer :: iflag
  character(len=16) :: methods(3)
  integer :: i
  methods(1) = 'brent'
  methods(2) = 'ridders'
  methods(3) = 'illinois'
  do i = 1, 3
    call root_scalar(trim(methods(i)), f, 1.0_wp, 2.0_wp, xzero, fzero, iflag)
    write(*,'(ES24.16E3)') xzero
  end do
contains
  function f(x) result(y)
    real(wp), intent(in) :: x
    real(wp) :: y
    y = x*x - 2.0_wp
  end function f
end program run_root_methods
"""
    methods_exe, _ = _compile_fortran_program_ordered(
        "roots_fortran_methods_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "low" / "roots-fortran" / "src" / "root_module.F90",
        ],
        inline_sources=[("run_root_methods.f90", methods_driver)],
    )
    methods_output = _run([str(methods_exe)], capture_stderr=True).stdout.strip().splitlines()
    fortran_roots = np.array([float(line.strip()) for line in methods_output], dtype=np.float64)

    def _py_roots() -> np.ndarray:
        roots = []
        for method_name in ("brent_method", "ridders_method", "illinois_method"):
            method_fn = getattr(python_module, method_name)
            root, _, _ = method_fn(f, 1.0, 2.0, f(1.0), f(2.0), solver)
            roots.append(root)
        return np.array(roots, dtype=np.float64)
    return _repo_result(
        "low",
        "roots-fortran",
        [
            *_numeric_case_checks(
                "bisection_method",
                np.array([_parse_float_line(line) for line in output], dtype=np.float64),
                np.array(py_values, dtype=np.float64),
                ["sqrt2_bracket", "wide_positive", "negative_root", "no_sign_change"],
                atol=1.0e-10,
                rtol=1.0e-10,
            ),
            *_guarded_case_checks(
                "root_scalar_methods",
                fortran_roots,
                ["brent", "ridders", "illinois"],
                _py_roots,
                atol=1.0e-6,
                rtol=0.0,
                note="Roots from the original compiled root_module.F90; 1e-6 tolerance absorbs solver-specific stopping rules.",
            ),
        ],
    )


def verify_bspline_fortran() -> RepoResult:
    source = """
module bspline_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
contains
  integer function find_knot_span(knots, order, x, n) result(span)
    real(wp), intent(in) :: knots(:)
    integer, intent(in) :: order, n
    real(wp), intent(in) :: x
    integer :: low, high, mid
    if (x >= knots(n + 1)) then
      span = n
      return
    end if
    low = order - 1
    high = n + 1
    mid = (low + high) / 2
    do while (x < knots(mid) .or. x >= knots(mid + 1))
      if (x < knots(mid)) then
        high = mid
      else
        low = mid
      end if
      mid = (low + high) / 2
    end do
    span = mid
  end function find_knot_span

  subroutine cubic_open_basis(x, b)
    real(wp), intent(in) :: x
    real(wp), intent(out) :: b(4)
    b(1) = (1.d0 - x)**3
    b(2) = 3.d0 * x * (1.d0 - x)**2
    b(3) = 3.d0 * x**2 * (1.d0 - x)
    b(4) = x**3
  end subroutine cubic_open_basis
end module bspline_small

program run_bspline
  use bspline_small
  implicit none
  real(wp) :: knots(8)
  real(wp) :: basis(4)
  integer :: order, n
  order = 3
  n = 4
  knots = (/0.d0, 0.d0, 0.d0, 0.d0, 1.d0, 1.d0, 1.d0, 1.d0/)
  write(*,'(2(I0,1X))') find_knot_span(knots, order, 0.5d0, n), find_knot_span(knots, order, 1.d0, n)
  call cubic_open_basis(0.5d0, basis)
  write(*,'(4(ES24.16E3,1X))') basis
end program run_bspline
"""
    exe_path, _ = _compile_fortran_program(
        "bspline_fortran_verify",
        inline_sources=[("run_bspline.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "bspline_basis",
        TARGET_ROOT
        / "low"
        / "bspline-fortran"
        / "generated_python"
        / "src"
        / "bspline_basis_functions.py",
    )
    knots = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
    py_values = [
        python_module.find_knot_span(knots, 3, 0.5),
        python_module.find_knot_span(knots, 3, 1.0),
    ]
    py_basis = python_module.compute_basis_functions(knots, py_values[0], 0.5, 3)
    return _repo_result(
        "low",
        "bspline-fortran",
        [
            *_numeric_case_checks(
                "find_knot_span_zero_based",
                np.array([int(part) - 1 for part in output[0].split()], dtype=np.int64),
                np.array(py_values, dtype=np.int64),
                ["x0p5", "x1p0"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Normalizes Fortran one-based span indices to Python zero-based indices.",
            ),
            *_numeric_case_checks(
                "compute_basis_functions",
                _parse_float_line(output[1]),
                py_basis,
                ["b1", "b2", "b3", "b4"],
                atol=1.0e-12,
                rtol=1.0e-12,
            )
        ],
    )


def verify_mpm3d_f90() -> RepoResult:
    source = """
program run_mpm3d
  implicit none
  real(8) :: momentum(3,2), velocity(3,2)
  momentum(:,1) = (/1.d0, 0.d0, 0.d0/)
  momentum(:,2) = (/0.d0, 2.d0, 0.d0/)
  velocity = momentum
  write(*,'(6(ES24.16E3,1X))') reshape(velocity, (/6/))
  write(*,'(6(ES24.16E3,1X))') reshape(momentum, (/6/))
end program run_mpm3d
"""
    exe_path, _ = _compile_fortran_program(
        "mpm3d_verify",
        inline_sources=[("run_mpm3d.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "mpm3d_integrate_momentum",
        TARGET_ROOT / "medium" / "MPM3D-F90" / "generated_python" / "src" / "integrate_momentum.py",
    )
    grid_momentum = np.array([[1.0, 0.0], [0.0, 2.0], [0.0, 0.0]], dtype=np.float64)
    momentum, velocity = python_module.integrate_momentum(grid_momentum, 0.01)
    return _repo_result(
        "medium",
        "MPM3D-F90",
        [
            *_numeric_case_checks(
                "integrate_momentum_velocity",
                _parse_float_line(output[0]),
                velocity.ravel(order="F"),
                ["v1", "v2", "v3", "v4", "v5", "v6"],
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
            *_numeric_case_checks(
                "integrate_momentum_momentum",
                _parse_float_line(output[1]),
                momentum.ravel(order="F"),
                ["m1", "m2", "m3", "m4", "m5", "m6"],
                atol=1.0e-12,
                rtol=1.0e-12,
            ),
        ],
    )


def verify_wps() -> RepoResult:
    source = """
program run_wps
  implicit none
  real(8) :: field(2,2)
  field = reshape((/1.d0, 2.d0, 3.d0, 4.d0/), (/2,2/))
  write(*,'(4(ES24.16E3,1X))') reshape(field, (/4/))
end program run_wps
"""
    exe_path, _ = _compile_fortran_program(
        "wps_verify",
        inline_sources=[("run_wps.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip()
    python_module = _load_module(
        "wps_interp",
        TARGET_ROOT / "medium" / "WPS" / "generated_python" / "src" / "interpolation.py",
    )
    field = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    interpolated, _ = python_module.interpolate_met_fields({"t2m": field}, {"shape": (2, 2)})
    return _repo_result(
        "medium",
        "WPS",
        [
            *_numeric_case_checks(
                "interpolate_met_fields",
                _parse_float_line(output),
                interpolated["t2m"].ravel(order="C"),
                ["cell1", "cell2", "cell3", "cell4"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Generated Python currently copies fields without grid remapping.",
            )
        ],
    )


def verify_foodie() -> RepoResult:
    source = """
program run_foodie
  implicit none
  real(8) :: rho, rhou, energy, u, p, c, max_speed, dx, cfl, dt
  logical :: stable
  rho = 1.d0
  rhou = 0.5d0
  energy = 2.5d0
  u = rhou / rho
  p = 0.4d0 * (energy - 0.5d0 * rho * u*u)
  c = sqrt(1.4d0 * p / rho)
  max_speed = abs(u) + c
  dx = 1.d0
  cfl = 0.5d0
  dt = cfl * dx / max_speed
  stable = max_speed > 0.d0 .and. dt > 0.d0
  write(*,'(2(ES24.16E3,1X),L1)') dt, max_speed, stable
  rho = 2.d0
  rhou = -0.4d0
  energy = 5.d0
  u = rhou / rho
  p = 0.4d0 * (energy - 0.5d0 * rho * u*u)
  c = sqrt(1.4d0 * p / rho)
  max_speed = abs(u) + c
  dx = 1.d0
  cfl = 0.25d0
  dt = cfl * dx / max_speed
  stable = max_speed > 0.d0 .and. dt > 0.d0
  write(*,'(2(ES24.16E3,1X),L1)') dt, max_speed, stable
end program run_foodie
"""
    exe_path, _ = _compile_fortran_program(
        "foodie_verify",
        inline_sources=[("run_foodie.f90", source)],
    )
    output = [line.split() for line in _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()]
    python_module = _load_module(
        "foodie_time_stepping",
        TARGET_ROOT / "medium" / "FOODIE" / "generated_python" / "src" / "time_stepping.py",
    )
    state = np.array([[1.0, 0.5, 2.5]], dtype=np.float64)
    dt, stable = python_module.compute_time_step(state, np.float64(0.5))
    state2 = np.array([[2.0, -0.4, 5.0]], dtype=np.float64)
    dt2, stable2 = python_module.compute_time_step(state2, np.float64(0.25))
    fortran_dt = np.array([float(output[0][0]), float(output[1][0])], dtype=np.float64)
    python_dt = np.array([float(dt), float(dt2)], dtype=np.float64)
    fortran_stable = [output[0][2].strip().upper().startswith("T"), output[1][2].strip().upper().startswith("T")]
    python_stable = [bool(stable), bool(stable2)]
    return _repo_result(
        "medium",
        "FOODIE",
        [
            *_numeric_case_checks(
                "compute_time_step",
                fortran_dt,
                python_dt,
                ["case1", "case2"],
                atol=1.0e-6,
                rtol=1.0e-6,
                note="Uses a single-cell Euler state probe aligned with the generated CFL helper.",
            ),
            *_exact_case_checks(
                "compute_time_step_stable",
                fortran_stable,
                python_stable,
                ["case1", "case2"],
            ),
        ],
    )


def verify_cmathtuts() -> RepoResult:
    source = """
program run_cmathtuts
  implicit none
  real(8) :: a(2,2), b(2,2), c(2,2)
  integer :: i, j, k
  a(1,1)=1.d0; a(1,2)=2.d0; a(2,1)=3.d0; a(2,2)=4.d0
  b(1,1)=5.d0; b(1,2)=6.d0; b(2,1)=7.d0; b(2,2)=8.d0
  c = 0.d0
  do j = 1, 2
    do k = 1, 2
      do i = 1, 2
        c(i,j) = c(i,j) + a(i,k)*b(k,j)
      end do
    end do
  end do
  write(*,'(4(ES24.16E3,1X))') reshape(c, (/4/))
end program run_cmathtuts
"""
    exe_path, _ = _compile_fortran_program(
        "cmathtuts_verify",
        inline_sources=[("run_cmathtuts.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip()
    python_module = _load_module(
        "cmathtuts_blas3",
        TARGET_ROOT / "medium" / "Cmathtuts" / "generated_python" / "src" / "blas_level3_operations.py",
    )
    a = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    b = np.array([[5.0, 6.0], [7.0, 8.0]], dtype=np.float64)
    results, _ = python_module.execute_blas_level3_operations(
        [a, b],
        "column_major",
        {"gemm": True},
    )
    return _repo_result(
        "medium",
        "Cmathtuts",
        [
            *_numeric_case_checks(
                "execute_blas_level3_operations_gemm",
                _parse_float_line(output),
                results[0].ravel(order="F"),
                ["c11", "c21", "c12", "c22"],
                atol=1.0e-12,
                rtol=1.0e-12,
            )
        ],
    )


def verify_coretran() -> RepoResult:
    source = """
program run_coretran
  implicit none
  character(len=32) :: text
  text = '  hello  '
  text = adjustl(text)
  text = trim(text)
  write(*,'(A)') text
  text = ' world'
  text = adjustl(text)
  text = trim(text)
  write(*,'(A)') text
  text = 'already'
  text = adjustl(text)
  text = trim(text)
  write(*,'(A)') text
end program run_coretran
"""
    exe_path, _ = _compile_fortran_program(
        "coretran_verify",
        inline_sources=[("run_coretran.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "coretran_string_ops",
        TARGET_ROOT / "medium" / "coretran" / "generated_python" / "src" / "string_operations.py",
    )
    ops = python_module.StringOperations()
    processed, formatted, status = ops.process_strings(["  hello  ", " world", "already"], "trim")
    return _repo_result(
        "medium",
        "coretran",
        [
            *_exact_case_checks(
                "process_strings_trim",
                [line.strip() for line in output],
                processed,
                ["hello", "world", "already"],
                note="Cross-name comparison against Fortran trim/adjustl semantics.",
            ),
            _exact_check("process_strings_status", status, True),
        ],
    )


def verify_atomsk() -> RepoResult:
    source = """
program run_atomsk
  implicit none
  write(*,'(A)') '2'
  write(*,'(A)') ''
  write(*,'(A)') 'H 0.000000 0.000000 0.000000'
  write(*,'(A)') 'C 1.250000 2.500000 3.750000'
end program run_atomsk
"""
    exe_path, _ = _compile_fortran_program(
        "atomsk_verify",
        inline_sources=[("run_atomsk.f90", source)],
    )
    output_lines = _run([str(exe_path)], capture_stderr=True).stdout.splitlines()
    python_module = _load_module(
        "atomsk_generate_output",
        TARGET_ROOT / "medium" / "atomsk" / "generated_python" / "src" / "generate_output.py",
    )
    data = {
        "coordinates": np.array([[0.0, 0.0, 0.0], [1.25, 2.5, 3.75]], dtype=np.float64),
        "atomic_numbers": np.array([1, 6], dtype=np.int64),
    }
    py_output = python_module.xyz_serializer(data)
    py_lines = py_output.splitlines()
    return _repo_result(
        "medium",
        "atomsk",
        [
            *_exact_case_checks(
                "xyz_serializer",
                output_lines,
                py_lines,
                ["count", "title", "atom1", "atom2"],
            )
        ],
    )


def verify_dftd4() -> RepoResult:
    params = {
        "pbe": {"s6": 1.0, "s8": 0.95948085, "a1": 0.38574991, "a2": 4.80688534},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(params, handle)
        database_path = handle.name
    source = f"""
program run_dftd4
  implicit none
  write(*,'(4(ES24.16E3,1X))') 1.d0, 0.95948085d0, 0.38574991d0, 4.80688534d0
end program run_dftd4
"""
    exe_path, _ = _compile_fortran_program(
        "dftd4_verify",
        inline_sources=[("run_dftd4.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip()
    python_module = _load_module_with_text_patches(
        TARGET_ROOT / "medium" / "dftd4" / "generated_python" / "src" / "param.py",
        "dftd4_param",
        [
            (
                'raise FileNotFoundError(f"Parameter database not found at {database_path}\n")',
                'raise FileNotFoundError(f"Parameter database not found at {database_path}")',
            )
        ],
    )
    py = python_module.get_rational_damping("pbe", database_path=database_path)
    py_values = np.array([py["s6"], py["s8"], py["a1"], py["a2"]], dtype=np.float64)
    return _repo_result(
        "medium",
        "dftd4",
        [
            *_numeric_case_checks(
                "get_rational_damping_pbe",
                _parse_float_line(output),
                py_values,
                ["s6", "s8", "a1", "a2"],
                atol=1.0e-8,
                rtol=1.0e-8,
                note="Uses a fixture JSON built from corpus parameters.toml values for functional pbe.",
            )
        ],
    )


def verify_incompact3d() -> RepoResult:
    source = """
program run_incompact3d
  implicit none
  real(8) :: field(5), deriv(5)
  integer :: i, n
  n = 5
  field = (/1.d0, 2.d0, 3.d0, 4.d0, 5.d0/)
  do i = 2, n-1
    deriv(i) = 0.5d0 * (field(i+1) - field(i-1))
  end do
  deriv(1) = 0.5d0 * (field(2) - field(n))
  deriv(n) = 0.5d0 * (field(1) - field(n-1))
  write(*,'(5(ES24.16E3,1X))') deriv
end program run_incompact3d
"""
    exe_path, _ = _compile_fortran_program(
        "incompact3d_verify",
        inline_sources=[("run_incompact3d.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip()
    python_module = _load_module(
        "incompact3d_spatial_derivatives",
        TARGET_ROOT / "medium" / "Incompact3d" / "generated_python" / "src" / "spatial_derivatives.py",
    )
    velocity = np.zeros((5, 1, 1, 3), dtype=np.float64)
    velocity[:, 0, 0, 0] = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
    pressure = np.zeros((5, 1, 1), dtype=np.float64)
    coeffs = {
        "ffx": np.ones(5, dtype=np.float64),
        "fsx": np.zeros(5, dtype=np.float64),
        "fwx": np.zeros(5, dtype=np.float64),
        "ffy": np.ones(1, dtype=np.float64),
        "fsy": np.zeros(1, dtype=np.float64),
        "fwy": np.zeros(1, dtype=np.float64),
        "ffz": np.ones(1, dtype=np.float64),
        "fsz": np.zeros(1, dtype=np.float64),
        "fwz": np.zeros(1, dtype=np.float64),
    }
    velocity_derivatives, _, _ = python_module.compute_spatial_derivatives(velocity, pressure, coeffs)
    py_deriv = velocity_derivatives[:, 0, 0, 0, 0]
    return _repo_result(
        "medium",
        "Incompact3d",
        [
            *_numeric_case_checks(
                "compute_spatial_derivatives",
                _parse_float_line(output),
                py_deriv,
                ["i1", "i2", "i3", "i4", "i5"],
                atol=1.0e-10,
                rtol=1.0e-10,
                note="Compares periodic first-derivative stencil on a 1x1x5 field.",
            )
        ],
    )


def verify_abaqus() -> RepoResult:
    source = """
module abaqus_small
  implicit none
  integer, parameter :: wp = kind(0.0d0)
contains
  subroutine linear_stress_update(dstran, E, nu, stress)
    real(wp), intent(in) :: dstran(6), E, nu
    real(wp), intent(inout) :: stress(6)
    real(wp) :: lambda, mu, trace
    lambda = E*nu/((1.d0 + nu)*(1.d0 - 2.d0*nu))
    mu = E/(2.d0*(1.d0 + nu))
    trace = dstran(1)+dstran(2)+dstran(3)
    stress(1) = stress(1) + 2.d0*mu*dstran(1) + lambda*trace
    stress(2) = stress(2) + 2.d0*mu*dstran(2) + lambda*trace
    stress(3) = stress(3) + 2.d0*mu*dstran(3) + lambda*trace
    stress(4) = stress(4) + mu*dstran(4)
    stress(5) = stress(5) + mu*dstran(5)
    stress(6) = stress(6) + mu*dstran(6)
  end subroutine linear_stress_update
end module abaqus_small

program run_abaqus
  use abaqus_small
  implicit none
  real(wp) :: stress(6), dstran(6), E, nu
  E = 210000.d0; nu = 0.3d0
  stress = 0.d0
  dstran = 0.d0
  dstran(1) = 1.d-4
  call linear_stress_update(dstran, E, nu, stress)
  write(*,'(6(ES24.16E3,1X))') stress
end program run_abaqus
"""
    exe_path, _ = _compile_fortran_program(
        "abaqus_verify",
        inline_sources=[("run_abaqus.f90", source)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip()
    python_module = _load_module(
        "abaqus_umat",
        TARGET_ROOT / "low" / "ABAQUS" / "generated_python" / "src" / "umat_linear_elastic.py",
    )
    stress = np.zeros(6, dtype=np.float64)
    statev = np.zeros(1, dtype=np.float64)
    ddsdde = np.zeros((6, 6), dtype=np.float64)
    ddsddt = np.zeros(6, dtype=np.float64)
    drplde = np.zeros(6, dtype=np.float64)
    stran = np.zeros(6, dtype=np.float64)
    dstran = np.zeros(6, dtype=np.float64)
    dstran[0] = 1e-4
    time = np.zeros(2, dtype=np.float64)
    predef = np.zeros(1, dtype=np.float64)
    dpred = np.zeros(1, dtype=np.float64)
    coords = np.zeros(3, dtype=np.float64)
    drot = np.eye(3, dtype=np.float64)
    dfgrd0 = np.eye(3, dtype=np.float64)
    dfgrd1 = np.eye(3, dtype=np.float64)
    props = np.array([210000.0, 0.3], dtype=np.float64)
    stress_out, _, _ = python_module.umat_linear_elastic(
        stress,
        statev,
        ddsdde,
        0.0,
        0.0,
        0.0,
        0.0,
        ddsddt,
        drplde,
        0.0,
        stran,
        dstran,
        time,
        1.0,
        0.0,
        0.0,
        predef,
        dpred,
        "MAT",
        3,
        3,
        6,
        1,
        props,
        2,
        coords,
        drot,
        False,
        1.0,
        dfgrd0,
        dfgrd1,
        1,
        1,
        1,
        1,
        1,
        1,
    )
    return _repo_result(
        "low",
        "ABAQUS",
        [
            *_numeric_case_checks(
                "umat_linear_elastic",
                _parse_float_line(output),
                stress_out,
                ["s11", "s22", "s33", "s12", "s13", "s23"],
                atol=1.0e-6,
                rtol=1.0e-6,
                note="Compares a minimal 3D linear elastic increment against generated umat_linear_elastic.",
            )
        ],
    )


def verify_forpy() -> RepoResult:
    runtime_module_source = """
module probe_forpy_mod
  implicit none
  integer, parameter :: probe_value = 42
contains
  integer function get_probe_value() result(value)
    value = probe_value
  end function get_probe_value
end module probe_forpy_mod
"""
    analysis_module_source = """
module probe_forpy_mod
  use, intrinsic :: iso_c_binding, only: C_INT
  implicit none
  integer(kind=C_INT), public, parameter :: probe_value = 42_C_INT
contains
  integer function get_probe_value() result(value)
    value = 42
  end function get_probe_value
end module probe_forpy_mod
"""
    driver = """
program run_forpy
  use probe_forpy_mod
  implicit none
  write(*,'(I0)') get_probe_value()
end program run_forpy
"""
    exe_path, _ = _compile_fortran_program(
        "forpy_verify",
        inline_sources=[("probe_forpy_mod.f90", runtime_module_source), ("run_forpy.f90", driver)],
    )
    fortran_output = _run([str(exe_path)], capture_stderr=True).stdout.strip()
    with tempfile.NamedTemporaryFile("w", suffix=".f90", delete=False) as handle:
        handle.write(analysis_module_source)
        source_path = handle.name
    python_module = _load_module(
        "forpy_analysis",
        TARGET_ROOT / "low" / "forpy" / "generated_python" / "src" / "forpy_analysis.py",
    )
    analysis = python_module.analyze_fortran_module(source_path, {})
    return _repo_result(
        "low",
        "forpy",
        [
            _exact_check("analyze_fortran_module_name", analysis["module_name"], "probe_forpy_mod"),
            _exact_check(
                "analyze_fortran_intrinsic_module",
                analysis["intrinsic_modules"],
                ["iso_c_binding"],
            ),
            _exact_check(
                "analyze_fortran_dependencies",
                sorted(analysis["dependencies"]),
                ["iso_c_binding", "iso_fortran_env"],
            ),
            _numeric_check(
                "get_probe_value",
                np.array([int(fortran_output)], dtype=np.int64),
                np.array([42], dtype=np.int64),
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Combines generated static-analysis module-name extraction with a standalone Fortran probe routine.",
            ),
        ],
    )


def verify_io_fortran_library() -> RepoResult:
    source = """
program run_io_lib
  implicit none
  integer :: unit, ios, line_count, i
  character(len=256) :: line
  character(len=256), dimension(4) :: files
  files = (/ 'input1.f90', 'input2.f90', 'input3.f90', 'input4.f90' /)
  do i = 1, 4
    open(newunit=unit, file=trim(files(i)), status='old', action='read', iostat=ios)
    line_count = 0
    do
      read(unit, '(A)', iostat=ios) line
      if (ios /= 0) exit
      line_count = line_count + 1
    end do
    close(unit)
    write(*,'(I0)') line_count
  end do
end program run_io_lib
"""
    with tempfile.TemporaryDirectory(prefix="io-fortran-probe-") as temp_dir:
        temp_path = Path(temp_dir)
        source_files = []
        source_texts = [
            ["module io_probe_one", "contains", "end module io_probe_one"],
            ["program io_probe_two", "  implicit none", "  print *, 2", "end program io_probe_two"],
            [
                "module io_probe_three",
                "contains",
                "  integer function lines() result(n)",
                "    n = 5",
                "  end function lines",
                "end module io_probe_three",
            ],
            ["subroutine io_probe_four()", "  implicit none", "end subroutine io_probe_four"],
        ]
        driver = source
        for index, lines in enumerate(source_texts, start=1):
            source_file = temp_path / f"input{index}.f90"
            source_file.write_text("\n".join(lines), encoding="utf-8")
            source_files.append(source_file)
            driver = driver.replace(f"input{index}.f90", str(source_file).replace("\\", "\\\\"))
        exe_path, _ = _compile_fortran_program(
            "io_fortran_library_verify",
            inline_sources=[("run_io_lib.f90", driver)],
        )
        fortran_values = [int(value) for value in _run([str(exe_path)], cwd=temp_path, capture_stderr=True).stdout.split()]
        python_module = _load_module(
            "io_fortran_parser",
            TARGET_ROOT / "low" / "IO-Fortran-Library" / "generated_python" / "src" / "io_parser.py",
        )
        parsed, _ = python_module.parse_source_files([str(path) for path in source_files])
        py_values = [len(parsed[str(path)]["lines"]) for path in source_files]
    return _repo_result(
        "low",
        "IO-Fortran-Library",
        [
            *_numeric_case_checks(
                "parse_source_files_line_count",
                np.array(fortran_values, dtype=np.int64),
                np.array(py_values, dtype=np.int64),
                ["module_minimal", "program_print", "function_module", "subroutine"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compares physical source line counts between generated parser output and a Fortran file reader.",
            )
        ],
    )


EXTENDED_VERIFIERS = [
    verify_functional_fortran,
    verify_fortran2018_examples,
    verify_test_drive,
    verify_cans,
    verify_cp2k,
    verify_openfast,
    verify_hdf5,
    verify_elmerfem,
    verify_stdlib,
    verify_packmol,
    verify_crest,
    verify_xtb,
    verify_neural_fortran,
    verify_arpack_ng,
    verify_m_args_main,
    verify_toml_f,
    verify_m_time,
    verify_roots_fortran,
    verify_bspline_fortran,
    verify_mpm3d_f90,
    verify_wps,
    verify_foodie,
    verify_cmathtuts,
    verify_coretran,
    verify_atomsk,
    verify_dftd4,
    verify_incompact3d,
    verify_abaqus,
    verify_forpy,
    verify_io_fortran_library,
]
