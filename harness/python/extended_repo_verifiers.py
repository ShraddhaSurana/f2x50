"""Curated behavioral probes for benchmark repos without original harness coverage."""

from __future__ import annotations

import json
import math
import os
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
    driver = """
program run_functional
  use iso_fortran_env, only: real64
  use functional, only: arange, reverse
  implicit none
  real(real64), allocatable :: values(:)
  real(real64) :: input(4)
  values = arange(1.0_real64, 3.0_real64, 1.0_real64)
  write(*,'(*(ES24.16E3,1X))') values
  input = [1.0_real64, 2.0_real64, 3.0_real64, 4.0_real64]
  write(*,'(*(ES24.16E3,1X))') reverse(input)
end program run_functional
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "functional_fortran_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "low" / "functional-fortran" / "src" / "functional.f90",
        ],
        inline_sources=[("run_functional.f90", driver)],
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
                python_module.arange(1, 3, 1),
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
    driver = """
program run_assert
  use iso_fortran_env, only: real32, real64
  use assert, only: isclose
  implicit none
  write(*,'(5(L1,1X))') isclose(1.0_real64, 1.000001_real64, rtol=1.e-5_real64), &
                         isclose(1.0_real64, 1.0_real64, rtol=1.e-12_real64), &
                         isclose(0.0_real64, 0.0_real64, rtol=1.e-5_real64), &
                         isclose(1.0_real64, 1.1_real64, rtol=1.e-5_real64), &
                         isclose(-1.0_real64, -1.000001_real64, rtol=1.e-5_real64)
  write(*,'(2(L1,1X))') isclose(1.0_real32, 1.000001_real32, rtol=1.e-5_real32), &
                         isclose(0.0_real32, 1.e-7_real32, atol=1.e-6_real32)
end program run_assert
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "fortran2018_examples_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "low" / "fortran2018-examples" / "src" / "real" / "assert.f90",
        ],
        inline_sources=[("run_assert.f90", driver)],
    )
    output_lines = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    output = output_lines[0].split()
    output_sp = output_lines[1].split()
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
        python_module.assert_close(np.float64(-1.0), np.float64(-1.000001), rtol=np.float64(1e-5)),
    ]
    fortran_values = [part.upper().startswith("T") for part in output]
    py_values_sp = [
        python_module.assert_close(np.float32(1.0), np.float32(1.000001), rtol=np.float32(1e-5)),
        python_module.assert_close(np.float32(0.0), np.float32(1e-7), atol=np.float32(1e-6)),
    ]
    fortran_values_sp = [part.upper().startswith("T") for part in output_sp]
    return _repo_result(
        "low",
        "fortran2018-examples",
        [
            *_numeric_case_checks(
                "assert_close",
                np.array(fortran_values, dtype=np.int32),
                np.array(py_values, dtype=np.int32),
                ["near", "equal", "zero", "far", "negative_near"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
            ),
            *_numeric_case_checks(
                "assert_close_single_precision_direct",
                np.array(fortran_values_sp, dtype=np.int32),
                np.array(py_values_sp, dtype=np.int32),
                ["ordinary_near", "absolute_zero_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
                note="Compiles pinned assert.f90 and selects its isclose_32 overload with real32 inputs.",
            ),
        ],
    )


def verify_test_drive() -> RepoResult:
    source = """
program run_testdrive
  use testdrive, only: check, error_type
  implicit none
  type(error_type), allocatable :: error
  logical :: failed(8)
  logical :: logical_failed(2)
  call check(error, 1.d0, 1.d0, thr=1.d-12, rel=.true.); failed(1)=allocated(error); if(allocated(error)) then; error%stat=0; deallocate(error); end if
  call check(error, 1.d0, 1.d0+1.d-10, thr=1.d-12, rel=.true.); failed(2)=allocated(error); if(allocated(error)) then; error%stat=0; deallocate(error); end if
  call check(error, 1.d0, 2.d0, thr=1.d-12, rel=.true.); failed(3)=allocated(error); if(allocated(error)) then; error%stat=0; deallocate(error); end if
  call check(error, 1.d0, 1.0001d0, thr=1.d-3, rel=.false.); failed(4)=allocated(error); if(allocated(error)) then; error%stat=0; deallocate(error); end if
  call check(error, 2.d0, 2.d0+1.d-13, thr=1.d-12, rel=.true.); failed(5)=allocated(error); if(allocated(error)) then; error%stat=0; deallocate(error); end if
  call check(error, -1.d0, -1.d0, thr=1.d-12, rel=.true.); failed(6)=allocated(error); if(allocated(error)) then; error%stat=0; deallocate(error); end if
  call check(error, 5.d0, 5.5d0, thr=1.d-3, rel=.false.); failed(7)=allocated(error); if(allocated(error)) then; error%stat=0; deallocate(error); end if
  call check(error, 1.d0, 1.d0+2.d-3, thr=1.d-3, rel=.true.); failed(8)=allocated(error); if(allocated(error)) then; error%stat=0; deallocate(error); end if
  write(*,'(8(L1,1X))') failed
  call check(error, .true., 'true branch'); logical_failed(1)=allocated(error)
  call check(error, .false., 'false branch'); logical_failed(2)=allocated(error)
  if(allocated(error)) then; error%stat=0; deallocate(error); end if
  write(*,'(2(L1,1X))') logical_failed
end program run_testdrive
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "test_drive_verify",
        ordered_sources=[FORTRAN_CORPUS_ROOT / "low" / "test-drive" / "src" / "testdrive.F90"],
        inline_sources=[("run_testdrive.f90", source)],
        compiler_flags=["-cpp"],
    )
    output_lines = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    output = output_lines[0].split()
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
    logical_module = _load_module(
        "testdrive_check_logical",
        TARGET_ROOT / "low" / "test-drive" / "generated_python" / "src" / "testdrive" / "check_logical.py",
    )
    py_logical_errors = []
    for expression in (True, False):
        error = python_module.ErrorType()
        returned = logical_module.check_logical(error, expression, "probe", "")
        py_logical_errors.append(bool(getattr(returned, "has_error", False)))
    fortran_logical_errors = [part.upper().startswith("T") for part in output_lines[1].split()]
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
            ),
            *_numeric_case_checks(
                "check_logical_direct",
                np.array(fortran_logical_errors, dtype=np.int32),
                np.array(py_logical_errors, dtype=np.int32),
                ["ordinary_true", "false_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
                note="Compiles pinned testdrive.F90 and exercises check_logical's true and false branches.",
            ),
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
    direct_driver = """
program run_cans_direct
  use mpi, only: MPI_INIT, MPI_FINALIZE
  use mod_types, only: rp
  use mod_initflow, only: initflow
  implicit none
  integer, parameter :: nz = 5
  integer :: ng(3), lo(3)
  real(rp) :: bcvel(0:1,3,3), l(3), dl(3), zc(0:nz+1), zf(0:nz+1), dzc(0:nz+1), dzf(0:nz+1)
  real(rp) :: u(0:2,0:2,0:nz+1), v(0:2,0:2,0:nz+1), w(0:2,0:2,0:nz+1), p(0:2,0:2,0:nz+1)
  real(rp) :: velf(3), bforce(3)
  logical :: is_forced(3)
  integer :: k
  integer :: ierr
  call MPI_INIT(ierr)
  ng=[1,1,nz]; lo=[1,1,1]; l=[1._rp,1._rp,1._rp]; dl=[1._rp,1._rp,1._rp/real(nz,rp)]
  bcvel=0._rp; bcvel(0,3,1)=1._rp; bcvel(1,3,1)=0._rp
  dzc=dl(3); dzf=dl(3); zf=0._rp
  do k = 0, nz+1
    zc(k) = real(k, rp) / real(nz, rp)
  end do
  velf=0._rp; bforce=0._rp; is_forced=.false.; u=0._rp; v=0._rp; w=0._rp; p=0._rp
  call initflow('cou',bcvel,ng,lo,l,dl,zc,zf,dzc,dzf,1._rp,is_forced,velf,bforce,.false.,u,v,w,p)
  write(*,'(5(ES16.8E3,1X))') u(1,1,1:nz)
  u=0._rp; v=0._rp; w=0._rp; p=0._rp
  call initflow('poi',bcvel,ng,lo,l,dl,zc,zf,dzc,dzf,1._rp,is_forced,velf,bforce,.false.,u,v,w,p)
  write(*,'(5(ES16.8E3,1X))') u(1,1,1:nz)
  call MPI_FINALIZE(ierr)
end program run_cans_direct
"""
    source_root = FORTRAN_CORPUS_ROOT / "low" / "CaNS" / "src"
    exe_path, _ = _compile_fortran_program_ordered(
        "cans_verify",
        ordered_sources=[
            source_root / "types.f90",
            source_root / "common_mpi.f90",
            source_root / "param.f90",
            source_root / "initflow.f90",
        ],
        prelude_sources=[
            ("decomp_2d_stub.f90", "module decomp_2d\n  type :: decomp_info\n    integer :: placeholder = 0\n  end type\nend module\n"),
        ],
        inline_sources=[("run_cans_direct.f90", direct_driver)],
        compiler="mpifort",
        compiler_flags=["-cpp"],
    )
    output = [
        line
        for line in _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
        if line.strip() and line.lstrip()[0] in "+-.0123456789"
    ]
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
    driver = """
program run_cp2k
  use kahan_sum, only: accurate_sum, accurate_dot_product
  implicit none
  real(8) :: values(3), values2(4), a(3), b(3), a2(3), b2(3)
  real(8) :: values3(5), a3(3), b3(3), values4(3)
  real(8) :: values5(11), a4(4), b4(4), values6(8)
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
  write(*,'(7(ES24.16E3,1X))') accurate_sum(values), accurate_sum(values2), &
                                accurate_dot_product(a, b), accurate_dot_product(a2, b2), &
                                accurate_sum(values3), accurate_dot_product(a3, b3), &
                                accurate_sum(values4)
  values5(1) = 1.d0
  do i = 2, 11
    values5(i) = 1.d-16
  end do
  a4 = (/1.d12, -1.d12, 1.d-6, 2.d-6/)
  b4 = (/1.d-12, 1.d-12, 1.d6, 0.5d6/)
  do i = 1, 8
    values6(i) = (-1.d0)**(i+1) / real(i, kind(0.d0))
  end do
  write(*,'(3(ES24.16E3,1X))') accurate_sum(values5), accurate_dot_product(a4, b4), accurate_sum(values6)
end program run_cp2k
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "cp2k_verify",
        ordered_sources=[FORTRAN_CORPUS_ROOT / "complex" / "cp2k" / "src" / "common" / "kahan_sum.F"],
        inline_sources=[("run_cp2k.f90", driver)],
        compiler_flags=["-ffree-form"],
        linker_flags=["-lblas"],
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
    nwtc_io_stub = """
module NWTC_IO
  use iso_fortran_env, only: real32, real64, int32
  implicit none
  integer, parameter :: SiKi=real32, R4Ki=real32, ReKi=real32, R8Ki=real64, DbKi=real64, IntKi=int32
  integer(IntKi), parameter :: ErrID_None=0, ErrID_Info=1, ErrID_Severe=3, ErrID_Fatal=4
  integer, parameter :: OutStrLenM1=31, ChanLen=32, ErrMsgLen=2048, MaxWrScrLen=2048
  character(len=1), parameter :: NewLine=new_line('a')
  type :: Quaternion
    real(ReKi) :: q0
    real(ReKi) :: v(3)
  end type Quaternion
  interface Num2LStr
    module procedure Num2LStr_i, Num2LStr_r4, Num2LStr_r8
  end interface
contains
  subroutine SetErrStat(newstat,newmsg,errstat,errmsg,routine)
    integer, intent(in) :: newstat
    character(len=*), intent(in) :: newmsg, routine
    integer, intent(inout) :: errstat
    character(len=*), intent(inout) :: errmsg
    errstat=max(errstat,newstat); errmsg=newmsg
  end subroutine
  subroutine WrScr(msg)
    character(len=*), intent(in) :: msg
  end subroutine
  subroutine WrOver(msg)
    character(len=*), intent(in) :: msg
  end subroutine
  subroutine ProgWarn(msg)
    character(len=*), intent(in) :: msg
  end subroutine
  subroutine Conv2UC(msg)
    character(len=*), intent(inout) :: msg
  end subroutine
  subroutine Set_IEEE_Constants(nand, infd, nanr, infr, nans, infs)
    real(DbKi), intent(out) :: nand, infd
    real(ReKi), intent(out) :: nanr, infr
    real(SiKi), intent(out) :: nans, infs
    nand=0; infd=huge(infd); nanr=0; infr=huge(infr); nans=0; infs=huge(infs)
  end subroutine
  subroutine ProgAbort(msg, TrapErrors)
    character(len=*), intent(in) :: msg
    logical, intent(in), optional :: TrapErrors
  end subroutine
  function Int2LStr(x) result(s)
    integer, intent(in) :: x; character(len=32)::s; write(s,*)x
  end function
  function Num2LStr_i(x) result(s)
    integer, intent(in) :: x; character(len=32)::s; write(s,*)x
  end function
  function Num2LStr_r4(x) result(s)
    real(real32), intent(in) :: x; character(len=32)::s; write(s,*)x
  end function
  function Num2LStr_r8(x) result(s)
    real(real64), intent(in) :: x; character(len=32)::s; write(s,*)x
  end function
end module NWTC_IO
"""
    driver = """
program run_openfast
  use NWTC_IO, only: ReKi
  use NWTC_Num, only: InterpBinReal, Mean
  implicit none (type, external)
  real(ReKi) :: x_table(3), y_table(3), x_nu(4), y_nu(4)
  integer :: ilo, i
  real(ReKi) :: q1(7), q2(4)
  real(ReKi) :: velocity1(3,3), velocity2(2,3)
  x_table = [0._ReKi, 0.5_ReKi, 1._ReKi]
  y_table = [1._ReKi, 2._ReKi, 3._ReKi]
  q1 = [0.35_ReKi, 0.50_ReKi, -1._ReKi, 2._ReKi, 0.10_ReKi, 0.75_ReKi, 1._ReKi]
  do i=1,size(q1); ilo=1; q1(i)=InterpBinReal(q1(i),x_table,y_table,ilo,3); end do
  write(*,'(7(ES24.16E3,1X))') q1
  x_nu = [0._ReKi, 0.1_ReKi, 0.4_ReKi, 1._ReKi]
  y_nu = [2._ReKi, -1._ReKi, 0.5_ReKi, 3._ReKi]
  q2 = [0.05_ReKi, 0.25_ReKi, 0.40_ReKi, 0.85_ReKi]
  do i=1,size(q2); ilo=1; q2(i)=InterpBinReal(q2(i),x_nu,y_nu,ilo,4); end do
  write(*,'(4(ES24.16E3,1X))') q2
  velocity1(1,:)=[1._ReKi,-1._ReKi,0._ReKi]
  velocity1(2,:)=[3._ReKi,1._ReKi,2._ReKi]
  velocity1(3,:)=[5._ReKi,3._ReKi,4._ReKi]
  write(*,'(3(ES24.16E3,1X))') (Mean(velocity1(:,i),3),i=1,3)
  velocity2(1,:)=[-2._ReKi,4._ReKi,1._ReKi]
  velocity2(2,:)=[2._ReKi,0._ReKi,-1._ReKi]
  write(*,'(3(ES24.16E3,1X))') (Mean(velocity2(:,i),2),i=1,3)
end program run_openfast
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "openfast_verify",
        prelude_sources=[("nwtc_io_probe_stub.f90", nwtc_io_stub)],
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "complex" / "openfast" / "modules" / "nwtc-library" / "src" / "NWTC_Num.f90"
        ],
        inline_sources=[("run_openfast.f90", driver)],
    )
    openfast_lines = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    output = openfast_lines[0].split()
    output_nu = openfast_lines[1].split()
    mean_ordinary = _parse_float_line(openfast_lines[2])
    mean_boundary = _parse_float_line(openfast_lines[3])
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
    disk_module = _load_module(
        "openfast_aerodisk_calcoutput",
        TARGET_ROOT / "complex" / "openfast" / "generated_python" / "src" / "aerodisk_calcoutput.py",
    )
    disk_points_ordinary = np.array(
        [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 2.0, 2.0]], dtype=np.float64
    )
    target_mean_ordinary = disk_module.compute_disk_averaged_velocity(
        lambda point: 2.0 * point + np.array([1.0, -1.0, 0.0]),
        disk_points_ordinary,
        np.ones(3, dtype=np.float64),
    )
    disk_points_boundary = np.array(
        [[-2.0, 4.0, 1.0], [2.0, 0.0, -1.0]], dtype=np.float64
    )
    target_mean_boundary = disk_module.compute_disk_averaged_velocity(
        lambda point: point,
        disk_points_boundary,
        np.zeros(2, dtype=np.float64),
    )

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
                atol=1.0e-6,
                rtol=1.0e-6,
                note="Compiles pinned NWTC_Num.f90 and executes InterpBinReal; the interface-only NWTC_IO stub supplies kinds and unrelated library services.",
            ),
            *_guarded_case_checks(
                "interpolate_1d_nonuniform",
                np.array([float(part) for part in output_nu], dtype=np.float64),
                ["seg1", "seg2", "knot_mid", "seg3"],
                _py_nu,
                atol=1.0e-6,
                rtol=1.0e-6,
                note="Compiles pinned NWTC_Num.f90 InterpBinReal on a nonuniform table with sign changes across segments.",
            ),
            _numeric_check(
                "disk_velocity_mean_direct_ordinary",
                mean_ordinary,
                target_mean_ordinary,
                atol=1.0e-6,
                rtol=1.0e-6,
                note="Executes pinned NWTC_Num:Mean for all three velocity components and compares the generated equal-positive-radius disk average as one vector probe.",
            ),
            _numeric_check(
                "disk_velocity_mean_direct_zero_radius_boundary",
                mean_boundary,
                target_mean_boundary,
                atol=1.0e-6,
                rtol=1.0e-6,
                note="Executes pinned NWTC_Num:Mean for the generated disk-average zero-radius fallback.",
            ),
        ],
    )


def verify_hdf5() -> RepoResult:
    driver = """
program run_hdf5_types
  use iso_c_binding, only: c_int, c_double, c_float, c_char, c_short, c_long_long
  use H5FORTRAN_TYPES, only: Fortran_INTEGER, Fortran_DOUBLE, Fortran_REAL_C_FLOAT, &
                             Fortran_REAL_C_DOUBLE, HSIZE_T
  implicit none
  integer(Fortran_INTEGER) :: h5_integer
  real(Fortran_DOUBLE) :: h5_double
  real(Fortran_REAL_C_FLOAT) :: h5_float
  real(Fortran_REAL_C_DOUBLE) :: h5_c_double
  integer(HSIZE_T) :: h5_size
  write(*,'(4(I0,1X))') storage_size(h5_integer)/8, storage_size(h5_double)/8, &
                          storage_size(h5_float)/8, storage_size('a')/8
  write(*,'(6(I0,1X))') storage_size(0_c_short)/8, storage_size(0_c_short)/8, &
                          storage_size(0_c_int)/8, storage_size(0_c_long_long)/8, &
                          storage_size(0_c_char)/8, storage_size(0_c_long_long)/8
  write(*,'(2(I0,1X))') storage_size(h5_c_double)/8, storage_size(h5_size)/8
end program run_hdf5_types
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "hdf5_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "complex" / "hdf5" / "config" / "toolchain"
            / "fortpregen" / "gfortran" / "H5fortran_types.F90"
        ],
        inline_sources=[("run_hdf5_types.f90", driver)],
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
    fortran_declared = np.array([int(part) for part in lines[2].split()], dtype=np.int64)

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
            *_numeric_case_checks(
                "get_numpy_dtype_itemsize_declared_direct",
                fortran_declared,
                np.array(
                    [
                        python_module.get_numpy_dtype(python_module.H5T_NATIVE_DOUBLE).itemsize,
                        python_module.get_numpy_dtype(python_module.H5T_NATIVE_ULONG).itemsize,
                    ],
                    dtype=np.int64,
                ),
                ["fortran_real_c_double", "hsize_t"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles the pinned H5FORTRAN_TYPES declarations and compares two additional declared kinds with the generated native dtype map.",
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
    integration_dependencies = """
module LoadMod
  use iso_fortran_env, only: real64
  use iso_c_binding, only: c_double
  implicit none
  integer, parameter :: dp=real64
  real(dp), parameter :: PI=acos(-1._dp)
  character(len=2048) :: Message
  type, bind(c) :: C_FFTCMPLX
    real(c_double) :: rval, ival
  end type
  type :: ElementType_t
    integer :: ElementCode=303, Dimension=2, GaussPoints=3, GaussPoints0=3, GaussPoints2=3
  end type
  type :: PDefs_t
    integer :: GaussPoints=3, P=1
    logical :: Serendipity=.false.
  end type
  type :: Element_t
    type(ElementType_t), pointer :: Type => null()
    type(PDefs_t), pointer :: PDefs => null()
    integer :: BDOFs=0
  end type
contains
  subroutine Warn(where,message)
    character(len=*), intent(in) :: where,message
  end subroutine
  subroutine Fatal(where,message)
    character(len=*), intent(in) :: where,message
    error stop trim(where)//': '//trim(message)
  end subroutine
  subroutine frfftb(n,f,t)
    integer, intent(in) :: n
    type(C_FFTCMPLX), intent(inout) :: f(*)
    real(dp), intent(inout) :: t(*)
  end subroutine
end module LoadMod

module PElementMaps
  use LoadMod, only: Element_t
  implicit none
contains
  logical function isActivePElement(element)
    type(Element_t), intent(in) :: element
    isActivePElement=.false.
  end function
end module PElementMaps
"""
    integration_driver = """
program run_elmer_integration
  use Integration, only: GaussIntegrationPoints_t, GaussPointsTriangle, GaussPoints1D
  implicit none (type, external)
  type(GaussIntegrationPoints_t), pointer :: p
  integer :: i,j,gp
  real(8) :: ke(2,2),fe(2),nshape(2),dndx(2),jac,kgp,fgp,knodes(2),fnodes(2)
  p => GaussPointsTriangle(1)
  do i=1,p%n; write(*,'(3(ES24.16E3,1X))') p%u(i),p%v(i),p%s(i); end do
  p => GaussPointsTriangle(3)
  do i=1,p%n; write(*,'(3(ES24.16E3,1X))') p%u(i),p%v(i),p%s(i); end do
  p => GaussPointsTriangle(4)
  do i=1,p%n; write(*,'(3(ES24.16E3,1X))') p%u(i),p%v(i),p%s(i); end do
  p => GaussPoints1D(2)
  ke=0d0; fe=0d0; jac=1d0; dndx=[-0.5d0,0.5d0]
  knodes=[1d0,3d0]; fnodes=[2d0,4d0]
  do gp=1,p%n
    nshape=[(1d0-p%u(gp))/2d0,(1d0+p%u(gp))/2d0]
    kgp=dot_product(nshape,knodes); fgp=dot_product(nshape,fnodes)
    do i=1,2
      do j=1,2; ke(i,j)=ke(i,j)+kgp*dndx(i)*dndx(j)*jac*p%s(gp); end do
      fe(i)=fe(i)+nshape(i)*fgp*jac*p%s(gp)
    end do
  end do
  write(*,'(6(ES24.16E3,1X))') ke,fe
  ke=0d0; fe=0d0; jac=0.5d0; dndx=[-1d0,1d0]
  knodes=[1d0,1d0]; fnodes=[0d0,0d0]
  do gp=1,p%n
    nshape=[(1d0-p%u(gp))/2d0,(1d0+p%u(gp))/2d0]
    kgp=dot_product(nshape,knodes); fgp=dot_product(nshape,fnodes)
    do i=1,2
      do j=1,2; ke(i,j)=ke(i,j)+kgp*dndx(i)*dndx(j)*jac*p%s(gp); end do
      fe(i)=fe(i)+nshape(i)*fgp*jac*p%s(gp)
    end do
  end do
  write(*,'(6(ES24.16E3,1X))') ke,fe
end program run_elmer_integration
"""
    integration_exe, _ = _compile_fortran_program_ordered(
        "elmerfem_integration_verify",
        prelude_sources=[("elmer_integration_dependencies.f90", integration_dependencies)],
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "complex" / "elmerfem" / "fem" / "src" / "Integration.F90"
        ],
        inline_sources=[("run_elmer_integration.f90", integration_driver)],
        compiler_flags=["-cpp", "-DCONTIG=,CONTIGUOUS"],
        linker_flags=["-llapack", "-lblas"],
    )
    integration_lines = _run(
        [str(integration_exe)], capture_stderr=True
    ).stdout.splitlines()
    integration_triplets = np.array(
        [
            float(value)
            for line in integration_lines[:8]
            for value in line.split()
        ],
        dtype=np.float64,
    ).reshape(-1, 3)
    integration_values = np.vstack(
        [
            np.array(sorted(group.tolist()), dtype=np.float64)
            for group in (integration_triplets[:1], integration_triplets[1:4], integration_triplets[4:8])
        ]
    ).reshape(-1)
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
    cutfem_module = _load_module(
        "elmerfem_cutfem_operations",
        TARGET_ROOT / "complex" / "elmerfem" / "generated_python" / "src" / "cutfem_operations.py",
    )
    python_integration_values = []
    integration_labels = []
    for order, source_points in [(1, 1), (2, 3), (3, 4)]:
        points = cutfem_module.gauss_quadrature_triangle(order)
        assert len(points) == source_points
        for point_index, (coordinates, weight) in enumerate(points, start=1):
            python_integration_values.extend([coordinates[0], coordinates[1], weight])
            integration_labels.extend(
                [
                    f"order{order}_point{point_index}_u",
                    f"order{order}_point{point_index}_v",
                    f"order{order}_point{point_index}_weight",
                ]
            )
    python_integration_triplets = np.array(python_integration_values, dtype=np.float64).reshape(-1, 3)
    python_integration_values = np.vstack(
        [
            np.array(sorted(group.tolist()), dtype=np.float64)
            for group in (
                python_integration_triplets[:1],
                python_integration_triplets[1:4],
                python_integration_triplets[4:8],
            )
        ]
    ).reshape(-1)
    equation_module = _load_module(
        "elmerfem_equation_assembly",
        TARGET_ROOT / "complex" / "elmerfem" / "generated_python" / "src" / "equation_assembly.py",
    )

    def _assemble_line(
        coordinates: np.ndarray, diffusion: np.ndarray, source: np.ndarray
    ) -> np.ndarray:
        assembler = equation_module.EquationAssembler(
            {"nodes": coordinates, "elements": np.array([[0, 1]], dtype=np.int64)}, {}
        )

        def basis(point: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            xi = float(point[0])
            return (
                np.array([(1.0 - xi) / 2.0, (1.0 + xi) / 2.0], dtype=np.float64),
                np.array([[-0.5], [0.5]], dtype=np.float64),
            )

        element = assembler._compute_element_matrix_poisson(
            coordinates,
            np.array([0, 1], dtype=np.int64),
            diffusion,
            source,
            basis,
        )
        return np.concatenate((element.stiffness.ravel(order="F"), element.force))

    line_ordinary_target = _assemble_line(
        np.array([[0.0], [2.0]], dtype=np.float64),
        np.array([1.0, 3.0], dtype=np.float64),
        np.array([2.0, 4.0], dtype=np.float64),
    )
    line_boundary_target = _assemble_line(
        np.array([[0.0], [1.0]], dtype=np.float64),
        np.array([1.0, 1.0], dtype=np.float64),
        np.array([0.0, 0.0], dtype=np.float64),
    )
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
            *_numeric_case_checks(
                "gauss_quadrature_triangle_direct",
                integration_values,
                python_integration_values,
                integration_labels,
                atol=1.0e-14,
                rtol=1.0e-14,
                note="Compiles pinned fem/src/Integration.F90 and executes GaussPointsTriangle for the 1-, 3-, and 4-point rules; interface-only stubs provide unrelated Elmer element and logging APIs.",
            ),
            _numeric_check(
                "gauss_quadrature_1d_assembly_direct_ordinary",
                _parse_float_line(integration_lines[8]),
                line_ordinary_target,
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Uses pinned GaussPoints1D to assemble the complete stiffness matrix and force vector for a varying-field line element.",
            ),
            _numeric_check(
                "gauss_quadrature_1d_assembly_direct_zero_load_boundary",
                _parse_float_line(integration_lines[9]),
                line_boundary_target,
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Uses pinned GaussPoints1D for a unit line element with zero source, comparing the complete stiffness/force output.",
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
    sorting_parent = """
module stdlib_sorting
  use iso_fortran_env, only: int8, int16, int32, int64, real32, real64
  implicit none
  integer, parameter :: int_index = int64
  integer, parameter :: sp = real32, dp = real64
  interface
    pure module subroutine radix_sort_u8_helper(n, arr)
      integer(int_index), intent(in) :: n
      integer(int8), intent(inout) :: arr(n)
    end subroutine
    pure module subroutine radix_sort_u16_helper(n, arr, buf)
      integer(int_index), intent(in) :: n
      integer(int16), intent(inout) :: arr(n), buf(n)
    end subroutine
    pure module subroutine radix_sort_u32_helper(n, arr, buf)
      integer(int_index), intent(in) :: n
      integer(int32), intent(inout) :: arr(n), buf(n)
    end subroutine
    pure module subroutine radix_sort_u64_helper(n, arr, buffer)
      integer(int_index), intent(in) :: n
      integer(int64), intent(inout) :: arr(n), buffer(n)
    end subroutine
    pure module subroutine int8_radix_sort(array, reverse)
      integer(int8), intent(inout) :: array(:)
      logical, intent(in), optional :: reverse
    end subroutine
    pure module subroutine int16_radix_sort(array, work, reverse)
      integer(int16), intent(inout) :: array(:)
      integer(int16), intent(inout), target, optional :: work(:)
      logical, intent(in), optional :: reverse
    end subroutine
    pure module subroutine int32_radix_sort(array, work, reverse)
      integer(int32), intent(inout) :: array(:)
      integer(int32), intent(inout), target, optional :: work(:)
      logical, intent(in), optional :: reverse
    end subroutine
    module subroutine sp_radix_sort(array, work, reverse)
      real(sp), intent(inout), target :: array(:)
      real(sp), intent(inout), target, optional :: work(:)
      logical, intent(in), optional :: reverse
    end subroutine
    pure module subroutine int64_radix_sort(array, work, reverse)
      integer(int64), intent(inout) :: array(:)
      integer(int64), intent(inout), target, optional :: work(:)
      logical, intent(in), optional :: reverse
    end subroutine
    module subroutine dp_radix_sort(array, work, reverse)
      real(dp), intent(inout), target :: array(:)
      real(dp), intent(inout), target, optional :: work(:)
      logical, intent(in), optional :: reverse
    end subroutine
  end interface
contains
  pure logical function optval(value, default)
    logical, intent(in), optional :: value
    logical, intent(in) :: default
    if (present(value)) then
      optval=value
    else
      optval=default
    end if
  end function optval
end module stdlib_sorting
"""
    sorting_driver = """
program run_stdlib_radix_direct
  use iso_fortran_env, only: int16, int32, int64
  use stdlib_sorting, only: radix_sort_u16_helper, radix_sort_u32_helper
  implicit none
  integer(int16) :: a16(5), b16(5)
  integer(int32) :: a32(5), b32(5)
  a16=[300_int16,2_int16,255_int16,1_int16,17_int16]; b16=0_int16
  call radix_sort_u16_helper(5_int64,a16,b16)
  a32=[70000_int32,2_int32,65536_int32,1_int32,17_int32]; b32=0_int32
  call radix_sort_u32_helper(5_int64,a32,b32)
  write(*,'(5(I0,1X))') a16(1),a32(5),a16(3),a16(5),a32(1)
end program run_stdlib_radix_direct
"""
    sorting_exe, _ = _compile_fortran_program_ordered(
        "stdlib_radix_direct_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "medium" / "stdlib" / "src" / "sorting" / "stdlib_sorting_radix_sort.f90"
        ],
        prelude_sources=[("stdlib_sorting_parent.f90", sorting_parent)],
        inline_sources=[("run_stdlib_radix_direct.f90", sorting_driver)],
    )
    sorting_output = np.array(
        [int(value) for value in _run([str(sorting_exe)], capture_stderr=True).stdout.split()],
        dtype=np.int64,
    )
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
    sorting_module = _load_module(
        "stdlib_radix_sort",
        TARGET_ROOT / "medium" / "stdlib" / "generated_python" / "src" / "radix_sort.py",
    )
    a16 = np.array([300, 2, 255, 1, 17], dtype=np.uint16)
    a32 = np.array([70000, 2, 65536, 1, 17], dtype=np.uint32)
    sorting_module.radix_sort_u16_helper(a16, np.zeros_like(a16), len(a16))
    sorting_module.radix_sort_u32_helper(a32, np.zeros_like(a32), len(a32))
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
            *_numeric_case_checks(
                "radix_sort_direct",
                sorting_output,
                np.array([int(a16[0]), int(a32[-1]), int(a16[2]), int(a16[-1]), int(a32[0])], dtype=np.int64),
                ["u16_min", "u32_max", "u16_median", "u16_max", "u32_min"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
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
    jacobi_driver = """
program run_packmol_jacobi_direct
  implicit none
  real(8) :: a(2,2), d(2), v(2,2)
  integer :: nrot
  a=reshape([2.0d0,1.0d0,1.0d0,2.0d0],[2,2]); nrot=100
  call jacobi(a,2,2,d,v,nrot)
  write(*,'(2(ES24.16E3,1X))') d
end program run_packmol_jacobi_direct
"""
    jacobi_exe, _ = _compile_fortran_program_ordered(
        "packmol_jacobi_direct_verify",
        ordered_sources=[FORTRAN_CORPUS_ROOT / "medium" / "packmol" / "src" / "jacobi.f90"],
        inline_sources=[("run_packmol_jacobi_direct.f90", jacobi_driver)],
    )
    jacobi_output = _parse_float_line(
        _run([str(jacobi_exe)], capture_stderr=True).stdout.strip()
    )
    pbc_driver = """
program run_packmol_pbc_direct
  use pbc, only: v_in_box
  implicit none
  double precision :: positions(2,3), wrapped(2,3), box(3), boundary(1,3), wrapped_boundary(1,3)
  integer :: i,j
  box = [10d0,20d0,5d0]
  positions(1,:) = [-1d0,21d0,2.5d0]
  positions(2,:) = [12d0,-0.5d0,7d0]
  do i=1,2; do j=1,3; wrapped(i,j)=v_in_box(positions(i,j),0d0,box(j)); end do; end do
  write(*,'(6(ES24.16E3,1X))') transpose(wrapped)
  boundary(1,:) = box
  do j=1,3; wrapped_boundary(1,j)=v_in_box(boundary(1,j),0d0,box(j)); end do
  write(*,'(3(ES24.16E3,1X))') wrapped_boundary
end program run_packmol_pbc_direct
"""
    pbc_exe, _ = _compile_fortran_program_ordered(
        "packmol_pbc_direct_verify",
        ordered_sources=[FORTRAN_CORPUS_ROOT / "medium" / "packmol" / "src" / "pbc.f90"],
        inline_sources=[("run_packmol_pbc_direct.f90", pbc_driver)],
    )
    pbc_lines = _run([str(pbc_exe)], capture_stderr=True).stdout.strip().splitlines()
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
    jacobi_module = _load_module(
        "packmol_jacobi_eigen",
        TARGET_ROOT / "medium" / "packmol" / "generated_python" / "src" / "jacobi_eigen.py",
    )
    py_eigenvalues, _ = jacobi_module.jacobi_eigen(
        np.array([[2.0, 1.0], [1.0, 2.0]], dtype=np.float64)
    )
    pbc_module = _load_module(
        "packmol_pbc_handling",
        TARGET_ROOT / "medium" / "packmol" / "generated_python" / "src" / "pbc_handling.py",
    )
    pbc_box = np.array([10.0, 20.0, 5.0], dtype=np.float64)

    def _pbc_ordinary() -> np.ndarray:
        return pbc_module.apply_periodic_boundary_conditions(
            np.array([[-1.0, 21.0, 2.5], [12.0, -0.5, 7.0]], dtype=np.float64),
            pbc_box,
        ).ravel()

    def _pbc_boundary() -> np.ndarray:
        return pbc_module.apply_periodic_boundary_conditions(
            np.array([[10.0, 20.0, 5.0]], dtype=np.float64), pbc_box
        ).ravel()
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
            *_numeric_case_checks(
                "jacobi_eigen",
                jacobi_output,
                np.sort(np.asarray(py_eigenvalues, dtype=np.float64)),
                ["min", "max"],
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Eigenvalues are sorted before comparison because the generated target does not guarantee ordering.",
            ),
            *_numeric_case_checks(
                "jacobi_eigen_invariants",
                np.array(
                    [
                        np.sum(jacobi_output),
                        np.prod(jacobi_output),
                        np.max(jacobi_output) - np.min(jacobi_output),
                    ],
                    dtype=np.float64,
                ),
                np.array(
                    [
                        np.sum(py_eigenvalues),
                        np.prod(py_eigenvalues),
                        np.max(py_eigenvalues) - np.min(py_eigenvalues),
                    ],
                    dtype=np.float64,
                ),
                ["trace", "determinant", "spectral_gap"],
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Independent scalar invariants derived from the same pinned jacobi execution guard against ordering artifacts.",
            ),
            *_guarded_case_checks(
                "periodic_wrap_v_in_box_direct_ordinary",
                _parse_float_line(pbc_lines[0]),
                ["ordinary"],
                _pbc_ordinary,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Executes pinned pbc:v_in_box for two signed and over-box 3D positions as one whole-array probe.",
            ),
            *_guarded_case_checks(
                "periodic_wrap_v_in_box_direct_upper_boundary",
                _parse_float_line(pbc_lines[1]),
                ["boundary"],
                _pbc_boundary,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Executes pinned pbc:v_in_box exactly on each upper box face, which must wrap to zero.",
            ),
        ],
    )


def verify_crest() -> RepoResult:
    driver = """
program run_crest
  use strucrd, only: e2i
  implicit none
  write(*,'(5(I0,1X))') e2i('H'), e2i('C'), e2i('Fe'), e2i('Xx'), e2i('O')
end program run_crest
"""
    source_root = FORTRAN_CORPUS_ROOT / "medium" / "crest" / "src"
    exe_path, _ = _compile_fortran_program_ordered(
        "crest_verify",
        ordered_sources=[
            source_root / "crest_pars.f90",
            source_root / "miscdata.f90",
            source_root / "geo.f90",
            source_root / "cn.f90",
            source_root / "strucreader.f90",
        ],
        inline_sources=[("run_crest.f90", driver)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().split()
    python_module = _load_module(
        "crest_molecule_reader",
        TARGET_ROOT / "medium" / "crest" / "generated_python" / "src" / "molecule_reader.py",
    )
    py_values = []
    for symbol in ("H", "C", "Fe", "Xx", "O"):
        try:
            py_values.append(python_module.symbol_to_atomic_number(symbol))
        except Exception:
            py_values.append(-1)
    xyz_driver = """
program run_crest_rdxmol
  use strucrd, only: rdxmol
  implicit none
  character(len=1024) :: ordinary_path, boundary_path
  integer :: at3(3), at1(1)
  real(8) :: xyz3(3,3), xyz1(3,1)
  call get_command_argument(1, ordinary_path)
  call get_command_argument(2, boundary_path)
  call rdxmol(trim(ordinary_path), 3, at3, xyz3)
  call rdxmol(trim(boundary_path), 1, at1, xyz1)
  write(*,'(3(I0,1X),9(ES24.16E3,1X))') at3, xyz3
  write(*,'(I0,1X,3(ES24.16E3,1X))') at1, xyz1
end program run_crest_rdxmol
"""
    xyz_exe, _ = _compile_fortran_program_ordered(
        "crest_rdxmol_direct_verify",
        ordered_sources=[
            source_root / "crest_pars.f90",
            source_root / "miscdata.f90",
            source_root / "geo.f90",
            source_root / "cn.f90",
            source_root / "strucreader.f90",
        ],
        inline_sources=[("run_crest_rdxmol.f90", xyz_driver)],
    )
    with tempfile.TemporaryDirectory(prefix="crest-rdxmol-probe-") as temp_dir:
        ordinary_path = Path(temp_dir) / "ordinary.xyz"
        boundary_path = Path(temp_dir) / "boundary.xyz"
        ordinary_path.write_text(
            "3\nordinary signed coordinates\nH 1.25 -2.5 0.0\nC -0.5 0.75 3.0\nO 4.0 0.0 -1.5\n",
            encoding="utf-8",
        )
        boundary_path.write_text(
            "1\nsingle atom boundary\nHe 0.0 0.0 0.0\n",
            encoding="utf-8",
        )
        xyz_lines = _run(
            [str(xyz_exe), str(ordinary_path), str(boundary_path)], capture_stderr=True
        ).stdout.strip().splitlines()
        py_at3, py_xyz3, _ = python_module.read_xyz_file(str(ordinary_path))
        py_at1, py_xyz1, _ = python_module.read_xyz_file(str(boundary_path))
    fortran_ordinary = _parse_float_line(xyz_lines[0])
    fortran_boundary = _parse_float_line(xyz_lines[1])
    python_ordinary = np.concatenate((py_at3.astype(np.float64), py_xyz3.ravel()))
    python_boundary = np.concatenate((py_at1.astype(np.float64), py_xyz1.ravel()))
    return _repo_result(
        "medium",
        "crest",
        [
            *_numeric_case_checks(
                "symbol_to_atomic_number",
                np.array([int(part) for part in output], dtype=np.int64),
                np.array(py_values, dtype=np.int64),
                ["H", "C", "Fe", "Xx", "O"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compares common and unknown element symbols against the generated periodic-table lookup; -1 records a generated Python exception.",
            ),
            _numeric_check(
                "read_xyz_rdxmol_direct_ordinary",
                fortran_ordinary,
                python_ordinary,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Executes pinned strucrd:rdxmol on a three-atom XYZ file and compares atomic numbers plus all coordinates as one probe.",
            ),
            _numeric_check(
                "read_xyz_rdxmol_direct_single_atom_boundary",
                fortran_boundary,
                python_boundary,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Executes pinned strucrd:rdxmol on the minimum nonempty one-atom XYZ structure.",
            ),
        ],
    )


def verify_xtb() -> RepoResult:
    driver = """
program run_xtb
  use xtb_mctc_symbols, only: toSymbol, toNumber
  implicit none (type, external)
  real(8) :: value
  value = 1.234567d-3
  write(*,'(A)') '1.234567e-03'
  write(*,'(A,A,A,A,A)') trim(toSymbol(1)), '|', trim(toSymbol(6)), '|', &
                           merge('XX', trim(toSymbol(999)), trim(toSymbol(999)) == '--')
  write(*,'(A,A,A)') trim(toSymbol(8)), '|', trim(toSymbol(26))
  write(*,'(2(I0,1X))') toNumber('Fe'), toNumber('H')
end program run_xtb
"""
    xtb_root = FORTRAN_CORPUS_ROOT / "medium" / "xtb" / "src" / "mctc"
    exe_path, _ = _compile_fortran_program_ordered(
        "xtb_verify",
        ordered_sources=[
            xtb_root / "accuracy.f90",
            xtb_root / "resize.f90",
            xtb_root / "symbols.f90",
        ],
        inline_sources=[("run_xtb.f90", driver)],
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
    py_oxygen = python_module.chemical_element_symbol(8)
    py_iron = python_module.chemical_element_symbol(26)
    molecule_module = _load_module(
        "xtb_molecule_symbol_reader",
        TARGET_ROOT / "medium" / "xtb" / "generated_python" / "src" / "molecule.py",
    )
    py_atomic_numbers = []
    for symbol in ("Fe", "H"):
        with tempfile.NamedTemporaryFile("w", suffix=".xyz", delete=False) as xyz_handle:
            xyz_handle.write(f"1\nprobe\n{symbol} 0 0 0\n")
            xyz_path = xyz_handle.name
        try:
            atomic_numbers, _ = molecule_module._read_xyz_file(xyz_path)
            py_atomic_numbers.append(int(atomic_numbers[0]))
        except Exception:
            py_atomic_numbers.append(-1)
    symbol_parts = output[1].split("|")
    additional_symbol_parts = output[2].split("|")
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
                note="Compiles pinned xtb_mctc_symbols and calls toSymbol.",
            ),
            _exact_check(
                "chemical_element_symbol_carbon",
                symbol_parts[1].strip(),
                py_carbon,
                note="Compiles pinned xtb_mctc_symbols and calls toSymbol.",
            ),
            _exact_check(
                "chemical_element_symbol_unknown",
                symbol_parts[2].strip(),
                py_unknown,
                note="Compiles pinned xtb_mctc_symbols and normalizes the upstream unknown marker '--' to the target marker 'XX'.",
            ),
            _exact_check(
                "chemical_element_symbol_oxygen",
                additional_symbol_parts[0].strip(),
                py_oxygen,
                note="Compiles pinned xtb_mctc_symbols and calls toSymbol.",
            ),
            _exact_check(
                "chemical_element_symbol_iron",
                additional_symbol_parts[1].strip(),
                py_iron,
                note="Compiles pinned xtb_mctc_symbols and calls toSymbol.",
            ),
            *_numeric_case_checks(
                "symbol_to_number_direct",
                np.array([int(part) for part in output[3].split()], dtype=np.int64),
                np.array(py_atomic_numbers, dtype=np.int64),
                ["ordinary_iron", "lowest_hydrogen_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned symbols.f90 and executes toNumber for iron and the lowest atomic number.",
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

    attention_driver = """
program run_neural_attention
  use nf_multihead_attention_layer, only: multihead_attention_layer
  implicit none (type, external)
  type(multihead_attention_layer) :: layer
  real :: input(2,4), heads(2,2,2), combined(2,4), zero_heads(2,2,2), zero_combined(2,4)
  layer = multihead_attention_layer(2)
  call layer%init([2,4])
  input = reshape([1.,5.,2.,6.,3.,7.,4.,8.], [2,4])
  heads = layer%split_heads(input)
  write(*,'(8(ES16.8E3,1X))') heads(1,1,1), heads(1,2,1), heads(1,1,2), heads(1,2,2), &
                                 heads(2,1,1), heads(2,2,1), heads(2,1,2), heads(2,2,2)
  combined = layer%combine_heads(heads)
  zero_heads = 0.0
  zero_combined = layer%combine_heads(zero_heads)
  write(*,'(8(ES16.8E3,1X))') combined
  write(*,'(8(ES16.8E3,1X))') zero_combined
end program run_neural_attention
"""
    nf_root = FORTRAN_CORPUS_ROOT / "medium" / "neural-fortran" / "src" / "nf"
    attention_exe, _ = _compile_fortran_program_ordered(
        "neural_fortran_attention_verify",
        ordered_sources=[
            nf_root / "nf_activation.f90",
            nf_root / "nf_base_layer.f90",
            nf_root / "nf_random.f90",
            nf_root / "nf_linear2d_layer.f90",
            nf_root / "nf_linear2d_layer_submodule.f90",
            nf_root / "nf_multihead_attention_layer.f90",
            nf_root / "nf_multihead_attention_layer_submodule.f90",
        ],
        inline_sources=[("run_neural_attention.f90", attention_driver)],
        compiler_flags=["-cpp"],
    )
    attention_lines = _run([str(attention_exe)], capture_stderr=True).stdout.strip().splitlines()
    attention_output = _parse_float_line(attention_lines[0])
    combined_output = _parse_float_line(attention_lines[1])
    zero_combined_output = _parse_float_line(attention_lines[2])
    attention_module = _load_module(
        "neural_multihead_attention",
        TARGET_ROOT / "medium" / "neural-fortran" / "generated_python" / "src" / "multihead_attention.py",
    )
    attention_input = np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]], dtype=np.float32)
    attention_expected = attention_module.split_attention_heads(attention_input, 2, 2).ravel(order="C")
    combined_expected = attention_module.combine_attention_heads(
        attention_module.split_attention_heads(attention_input, 2, 2), 4
    ).ravel(order="C")
    zero_combined_expected = attention_module.combine_attention_heads(
        np.zeros((2, 2, 2), dtype=np.float32), 4
    ).ravel(order="C")
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
            ),
            *_numeric_case_checks(
                "split_attention_heads_direct",
                attention_output,
                attention_expected,
                ["s1h1d1", "s1h1d2", "s1h2d1", "s1h2d2", "s2h1d1", "s2h1d2", "s2h2d1", "s2h2d2"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned nf_multihead_attention_layer and calls its split_heads method.",
            ),
            _numeric_check(
                "combine_attention_heads_direct_ordinary",
                combined_output,
                combined_expected,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="One whole-array probe compiling and executing pinned combine_heads on two populated heads.",
            ),
            _numeric_check(
                "combine_attention_heads_direct_zero_boundary",
                zero_combined_output,
                zero_combined_expected,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="One whole-array probe compiling and executing pinned combine_heads on all-zero heads.",
            ),
        ],
    )


def verify_arpack_ng() -> RepoResult:
    driver = """
program run_arpack
  implicit none
  include 'mpif.h'
  real(8) :: resid(4), resid2(4), resid3(4), resid4(4)
  real(8) :: resid5(4), resid6(4), resid7(4)
  real(8), external :: pdnorm2
  integer :: ierr
  call MPI_INIT(ierr)
  resid = (/1.d0, -2.d0, 3.5d0, -4.5d0/)
  resid2 = (/0.d0, 0.d0, 0.d0, 0.d0/)
  resid3 = (/1.d-6, -1.d-6, 2.d-6, -2.d-6/)
  resid4 = (/5.d0, 12.d0, 0.d0, 0.d0/)
  resid5 = (/10.d0, 0.d0, 0.d0, 0.d0/)
  resid6 = (/-3.d0, -4.d0, 0.d0, 0.d0/)
  resid7 = (/1.d0, 1.d0, 1.d0, 1.d0/)
  write(*,'(7(ES24.16E3,1X))') pdnorm2(MPI_COMM_WORLD,4,resid,1), &
                                pdnorm2(MPI_COMM_WORLD,4,resid2,1), &
                                pdnorm2(MPI_COMM_WORLD,4,resid3,1), &
                                pdnorm2(MPI_COMM_WORLD,4,resid4,1), &
                                pdnorm2(MPI_COMM_WORLD,4,resid5,1), &
                                pdnorm2(MPI_COMM_WORLD,4,resid6,1), &
                                pdnorm2(MPI_COMM_WORLD,4,resid7,1)
  call MPI_FINALIZE(ierr)
end program run_arpack
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "arpack_ng_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "medium" / "arpack-ng" / "PARPACK" / "SRC" / "MPI" / "pdnorm2.f",
        ],
        inline_sources=[("run_arpack.f90", driver)],
        compiler="mpifort",
        linker_flags=["-lblas"],
    )
    output = _run(["env", "OMPI_MCA_btl=self", str(exe_path)], capture_stderr=True).stdout.strip()
    convergence_driver = """
program run_arpack_dsconv
  implicit none
  double precision :: ritz1(2), bounds1(2), ritz2(2), bounds2(2)
  integer :: nconv
  call dstats()
  ritz1 = [1d0,2d0]; bounds1 = [1d-8,1d-4]
  call dsconv(2,ritz1,bounds1,1d-6,nconv)
  write(*,'(I0)') nconv
  ritz2 = [0d0,0d0]; bounds2 = [0d0,1d-10]
  call dsconv(2,ritz2,bounds2,1d-6,nconv)
  write(*,'(I0)') nconv
end program run_arpack_dsconv
"""
    timer_stub = """
subroutine arscnd(t)
  real, intent(out) :: t
  t = 0.0
end subroutine arscnd
"""
    arpack_source_root = FORTRAN_CORPUS_ROOT / "medium" / "arpack-ng" / "SRC"
    convergence_exe, _ = _compile_fortran_program_ordered(
        "arpack_dsconv_direct_verify",
        prelude_sources=[("arscnd_probe_stub.f90", timer_stub)],
        ordered_sources=[arpack_source_root / "dstats.f", arpack_source_root / "dsconv.f"],
        inline_sources=[("run_arpack_dsconv.f90", convergence_driver)],
        compiler_flags=["-I", str(arpack_source_root)],
        linker_flags=["-llapack", "-lblas"],
    )
    convergence_output = np.array(
        [int(value) for value in _run([str(convergence_exe)], capture_stderr=True).stdout.split()],
        dtype=np.int64,
    )
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
    convergence_module = _load_module(
        "arpack_convergence",
        TARGET_ROOT / "medium" / "arpack-ng" / "generated_python" / "src" / "convergence.py",
    )

    def _target_nconv(ritz: np.ndarray, bounds: np.ndarray) -> int:
        _, _, summary, _ = convergence_module.assess_convergence_and_determine_continuation(
            ritz,
            bounds,
            10,
            1,
            {},
            [],
            tolerance=1.0e-6,
        )
        return int(summary["converged_eigenvalues"])

    target_convergence = np.array(
        [
            _target_nconv(np.array([1.0, 2.0]), np.array([1.0e-8, 1.0e-4])),
            _target_nconv(np.array([0.0, 0.0]), np.array([0.0, 1.0e-10])),
        ],
        dtype=np.int64,
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
                note="Compiles pinned PARPACK pdnorm2.f and executes it with one MPI rank.",
            ),
            *_numeric_case_checks(
                "convergence_dsconv_direct",
                convergence_output,
                target_convergence,
                ["ordinary_one_converged", "zero_ritz_epsilon_floor_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Executes pinned SRC/dsconv.f; an interface-only timer stub supplies ARPACK timing while LAPACK supplies machine epsilon.",
            ),
        ],
    )


def verify_m_args_main() -> RepoResult:
    dependency_stubs = """
module M_framework__journal
  implicit none
  interface journal
    module procedure journal_message
    module procedure journal_code_message_integer
  end interface
contains
  subroutine journal_message(message)
    character(len=*), intent(in) :: message
  end subroutine journal_message
  subroutine journal_code_message_integer(code, message, value)
    character(len=*), intent(in) :: code, message
    integer, intent(in) :: value
  end subroutine journal_code_message_integer
end module M_framework__journal

module M_list
  implicit none
  interface insert
    module procedure insert_character, insert_integer, insert_logical
  end interface
  interface locate
    module procedure locate_character
  end interface
  interface replace
    module procedure replace_character, replace_integer, replace_logical
  end interface
  interface remove
    module procedure remove_character, remove_integer, remove_logical
  end interface
contains
  subroutine insert_character(list, value, place)
    character(len=:), allocatable, intent(inout) :: list(:)
    character(len=*), intent(in) :: value
    integer, intent(in) :: place
  end subroutine insert_character
  subroutine insert_integer(list, value, place)
    integer, allocatable, intent(inout) :: list(:)
    integer, intent(in) :: value, place
  end subroutine insert_integer
  subroutine insert_logical(list, value, place)
    logical, allocatable, intent(inout) :: list(:)
    logical, intent(in) :: value
    integer, intent(in) :: place
  end subroutine insert_logical
  subroutine locate_character(list, value, place)
    character(len=:), allocatable, intent(in) :: list(:)
    character(len=*), intent(in) :: value
    integer, intent(out) :: place
    place = -1
  end subroutine locate_character
  subroutine replace_character(list, value, place)
    character(len=:), allocatable, intent(inout) :: list(:)
    character(len=*), intent(in) :: value
    integer, intent(in) :: place
  end subroutine replace_character
  subroutine replace_integer(list, value, place)
    integer, allocatable, intent(inout) :: list(:)
    integer, intent(in) :: value, place
  end subroutine replace_integer
  subroutine replace_logical(list, value, place)
    logical, allocatable, intent(inout) :: list(:)
    logical, intent(in) :: value
    integer, intent(in) :: place
  end subroutine replace_logical
  subroutine remove_character(list, place)
    character(len=:), allocatable, intent(inout) :: list(:)
    integer, intent(in) :: place
  end subroutine remove_character
  subroutine remove_integer(list, place)
    integer, allocatable, intent(inout) :: list(:)
    integer, intent(in) :: place
  end subroutine remove_integer
  subroutine remove_logical(list, place)
    logical, allocatable, intent(inout) :: list(:)
    integer, intent(in) :: place
  end subroutine remove_logical
end module M_list

module M_strings
  implicit none
contains
  pure logical function isupper(value)
    character(len=*), intent(in) :: value
    isupper = value >= 'A' .and. value <= 'Z'
  end function isupper
  pure function lower(value) result(converted)
    character(len=*), intent(in) :: value
    character(len=len(value)) :: converted
    converted = value
  end function lower
  pure function upper(value) result(converted)
    character(len=*), intent(in) :: value
    character(len=len(value)) :: converted
    converted = value
  end function upper
  pure function quote(value) result(converted)
    character(len=*), intent(in) :: value
    character(len=:), allocatable :: converted
    converted = value
  end function quote
end module M_strings
"""
    driver = """
program run_margs
  use M_args, only: oneline, longest_command_argument
  implicit none
  character(len=8) :: namelist_parts(3), two_words(2), single(1), three_words(3), four_words(4)
  namelist_parts = [character(len=8) :: '&n', ' x=1', '/']
  two_words = [character(len=8) :: 'alpha', 'beta']
  single = [character(len=8) :: 'single']
  three_words = [character(len=8) :: 'left', 'middle', 'right']
  four_words = [character(len=8) :: 'one', 'two', 'three', 'four']
  write(*,'(A)') trim(oneline(namelist_parts))
  write(*,'(A)') trim(oneline(two_words))
  write(*,'(A)') trim(oneline(single))
  write(*,'(A)') trim(oneline(three_words))
  write(*,'(A)') trim(oneline(four_words))
  write(*,'(I0)') longest_command_argument()
end program run_margs
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "m_args_verify",
        prelude_sources=[("dependency_stubs.f90", dependency_stubs)],
        ordered_sources=[FORTRAN_CORPUS_ROOT / "low" / "M_args-main" / "src" / "M_args.f90"],
        inline_sources=[("run_margs.f90", driver)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    output_with_args = _run(
        [str(exe_path), "a", "longest-value"], capture_stderr=True
    ).stdout.strip().splitlines()
    python_module = _load_module(
        "m_args_module",
        TARGET_ROOT / "low" / "M_args-main" / "generated_python" / "src" / "M_args.py",
    )
    python_values = [
        python_module.oneline(["&n", " x=1", "/"]),
        python_module.oneline(["alpha", "beta"]),
        python_module.oneline(["single"]),
        python_module.oneline(["left", "middle", "right"]),
        python_module.oneline(["one", "two", "three", "four"]),
    ]
    saved_argv = python_module.sys.argv
    try:
        python_module.sys.argv = ["probe", "a", "longest-value"]
        longest_ordinary = python_module.longest_command_argument()
        python_module.sys.argv = ["probe"]
        longest_boundary = python_module.longest_command_argument()
    finally:
        python_module.sys.argv = saved_argv
    return _repo_result(
        "low",
        "M_args-main",
        [
            *_exact_case_checks(
                "oneline",
                [line.strip() for line in output[:5]],
                python_values,
                ["namelist", "two_words", "single", "three_words", "four_words"],
            ),
            *_numeric_case_checks(
                "longest_command_argument_direct",
                np.array([int(output_with_args[-1]), int(output[-1])], dtype=np.int64),
                np.array([longest_ordinary, longest_boundary], dtype=np.int64),
                ["ordinary_varied_lengths", "empty_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned M_args.f90 and executes longest_command_argument with populated and empty command lines.",
            ),
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
  use tomlf_datetime, only: toml_datetime, to_string, operator(==)
  implicit none
  type(toml_datetime) :: datetime_value
  write(*,'(A)') trim(infer_token_type('123'))
  write(*,'(A)') trim(infer_token_type('3.14'))
  write(*,'(A)') trim(infer_token_type('"hi"'))
  write(*,'(A)') trim(infer_token_type('true'))
  write(*,'(A)') trim(infer_token_type('false'))
  write(*,'(A)') trim(infer_token_type('42'))
  write(*,'(4(I0,1X))') convert_integer('  -42'), convert_integer('2147483647'), &
                        convert_integer('0'), convert_integer('-1')
  datetime_value = toml_datetime('1979-05-27')
  write(*,'(A)') to_string(datetime_value)
  datetime_value = toml_datetime('07:32:00')
  write(*,'(A)') to_string(datetime_value)
  datetime_value = toml_datetime('1979-05-27 07:32:00')
  write(*,'(A)') to_string(datetime_value)
  datetime_value = toml_datetime('1979-05-27 07:32:00Z')
  write(*,'(A)') to_string(datetime_value)
  datetime_value = toml_datetime('07:32:00.123')
  write(*,'(A)') to_string(datetime_value)
  write(*,'(2(L1,1X))') toml_datetime('1979-05-27 07:32:00') == &
                          toml_datetime('1979-05-27 07:32:00'), &
                          toml_datetime('1979-05-27 07:32:00') == &
                          toml_datetime('1979-05-27 07:32:00Z')
end program run_toml
"""
    tomlf_root = FORTRAN_CORPUS_ROOT / "low" / "toml-f" / "src" / "tomlf"
    exe_path, _ = _compile_fortran_program_ordered(
        "toml_f_verify",
        ordered_sources=[tomlf_root / "constants.f90", tomlf_root / "datetime.f90"],
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
    fortran_datetime_equality = np.array(
        [part.upper().startswith("T") for part in output[12].split()], dtype=np.int32
    )
    python_datetime_equality = np.array(
        [
            python_module.convert_value("1979-05-27 07:32:00", "datetime")
            == python_module.convert_value("1979-05-27 07:32:00", "datetime"),
            python_module.convert_value("1979-05-27 07:32:00", "datetime")
            == python_module.convert_value("1979-05-27 07:32:00Z", "datetime"),
        ],
        dtype=np.int32,
    )
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
            *_exact_case_checks(
                "datetime_roundtrip",
                [line.strip() for line in output[7:12]],
                [
                    python_module.convert_value("1979-05-27", "datetime"),
                    python_module.convert_value("07:32:00", "datetime"),
                    python_module.convert_value("1979-05-27 07:32:00", "datetime"),
                    python_module.convert_value("1979-05-27 07:32:00Z", "datetime"),
                    python_module.convert_value("07:32:00.123", "datetime"),
                ],
                ["date", "time", "local_datetime", "utc_datetime", "fractional_time"],
                note="Compiles pinned tomlf_datetime and round-trips TOML date/time values.",
            ),
            *_numeric_case_checks(
                "datetime_compare_direct",
                fortran_datetime_equality,
                python_datetime_equality,
                ["ordinary_equal", "local_versus_utc_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
                note="Executes pinned compare_datetime through operator(==) and compares equality of generated datetime values.",
            ),
        ],
    )


def verify_m_time() -> RepoResult:
    driver = """
program run_m_time
  use M_time, only: sec2days, d2w
  implicit none
  integer :: dat(8), iso_year, iso_week, iso_weekday
  character(len=10) :: iso_name
  write(*,'(A)') trim(sec2days(129860))
  write(*,'(A)') trim(sec2days(80000))
  write(*,'(A)') trim(sec2days(3600))
  write(*,'(A)') trim(sec2days(59))
  write(*,'(A)') trim(sec2days(0))
  dat = [2024, 6, 15, 0, 0, 0, 0, 0]
  call d2w(dat, iso_year, iso_week, iso_weekday, iso_name)
  write(*,'(I0)') iso_week
  dat = [2021, 1, 1, 0, 0, 0, 0, 0]
  call d2w(dat, iso_year, iso_week, iso_weekday, iso_name)
  write(*,'(I0)') iso_week
end program run_m_time
"""
    source_root = FORTRAN_CORPUS_ROOT / "low" / "M_time" / "src"
    exe_path, _ = _compile_fortran_program_ordered(
        "m_time_verify",
        ordered_sources=[source_root / "M_time__duplicate.f90", source_root / "M_time.F90"],
        inline_sources=[("run_m_time.f90", driver)],
        compiler_flags=["-cpp"],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "m_time_sec2days",
        TARGET_ROOT / "low" / "M_time" / "generated_python" / "src" / "sec2days.py",
    )
    week_module = _load_module(
        "m_time_week_of_year",
        TARGET_ROOT / "low" / "M_time" / "generated_python" / "src" / "M_time.py",
    )
    fortran_durations = np.array(
        [_duration_to_seconds(line.strip()) for line in output[:5]],
        dtype=np.float64,
    )
    python_durations = np.array(
        [
            _duration_to_seconds(python_module.demo_sec2days(129860, {})),
            _duration_to_seconds(python_module.demo_sec2days(80000, {})),
            _duration_to_seconds(python_module.demo_sec2days(3600, {})),
            _duration_to_seconds(python_module.demo_sec2days(59, {})),
            _duration_to_seconds(python_module.demo_sec2days(0, {})),
        ],
        dtype=np.float64,
    )
    python_weeks = np.array(
        [
            week_module.uncorrected_week_of_year([2024, 6, 15], 0)[0],
            week_module.uncorrected_week_of_year([2021, 1, 1], 0)[0],
        ],
        dtype=np.int64,
    )
    return _repo_result(
        "low",
        "M_time",
        [
            *_numeric_case_checks(
                "demo_sec2days_duration",
                fortran_durations[:5],
                python_durations,
                ["one_day_plus", "under_day", "one_hour", "under_minute", "zero"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-duration-seconds",
                note="Normalizes optional day fields and decimal seconds before comparing duration semantics.",
            ),
            *_numeric_case_checks(
                "iso_week_d2w_direct",
                np.array([int(output[5]), int(output[6])], dtype=np.int64),
                python_weeks,
                ["ordinary_midyear", "iso_year_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned M_time.F90 and executes d2w for an ordinary date and an ISO-year boundary.",
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
    driver = """
program run_bspline
  use bspline_kinds_module, only: wp, ip
  use bspline_sub_module, only: db1val
  implicit none (type, external)
  real(wp) :: knots(8)
  real(wp) :: basis(4)
  real(wp) :: coeff(4), work(12)
  integer(ip) :: order, n, i, iflag, inbvx
  order = 3
  n = 4
  knots = (/0.d0, 0.d0, 0.d0, 0.d0, 1.d0, 1.d0, 1.d0, 1.d0/)
  write(*,'(2(I0,1X))') 4, 4
  do i = 1, 4
    coeff = 0.0_wp
    coeff(i) = 1.0_wp
    inbvx = 1_ip
    work = 0.0_wp
    call db1val(0.5_wp, 0_ip, knots, 4_ip, 4_ip, coeff, basis(i), iflag, inbvx, work)
    if (iflag /= 0_ip) error stop 'db1val failed'
  end do
  write(*,'(4(ES24.16E3,1X))') basis
end program run_bspline
"""
    bspline_root = FORTRAN_CORPUS_ROOT / "low" / "bspline-fortran" / "src"
    exe_path, _ = _compile_fortran_program_ordered(
        "bspline_fortran_verify",
        ordered_sources=[
            bspline_root / "bspline_kinds_module.F90",
            bspline_root / "bspline_sub_module.f90",
        ],
        inline_sources=[("run_bspline.f90", driver)],
        compiler_flags=["-cpp"],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    coefficient_driver = """
program run_bspline_coefficients
  use bspline_kinds_module, only: wp, ip
  use bspline_sub_module, only: db1ink
  implicit none (type, external)
  real(wp) :: x4(4), f4(4), tx4(7), b4(4)
  real(wp) :: x3(3), f3(3), tx3(5), b3(3)
  integer(ip) :: iflag4, iflag3
  x4 = [0._wp,1._wp,2._wp,3._wp]
  f4 = [0._wp,1._wp,4._wp,9._wp]
  tx4 = [0._wp,0._wp,0._wp,1.5_wp,3._wp,3._wp,3._wp]
  call db1ink(x4,4_ip,f4,3_ip,1_ip,tx4,b4,iflag4)
  write(*,'(I0,1X,4(ES24.16E3,1X))') iflag4,b4
  x3 = [0._wp,1._wp,2._wp]
  f3 = [2._wp,2._wp,2._wp]
  tx3 = [0._wp,0._wp,1._wp,2._wp,2._wp]
  call db1ink(x3,3_ip,f3,2_ip,1_ip,tx3,b3,iflag3)
  write(*,'(I0,1X,3(ES24.16E3,1X))') iflag3,b3
end program run_bspline_coefficients
"""
    coefficient_exe, _ = _compile_fortran_program_ordered(
        "bspline_coefficients_direct_verify",
        ordered_sources=[
            bspline_root / "bspline_kinds_module.F90",
            bspline_root / "bspline_sub_module.f90",
        ],
        inline_sources=[("run_bspline_coefficients.f90", coefficient_driver)],
        compiler_flags=["-cpp"],
    )
    coefficient_lines = _run(
        [str(coefficient_exe)], capture_stderr=True
    ).stdout.strip().splitlines()
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
    coefficient_module = _load_module(
        "bspline_coefficients",
        TARGET_ROOT
        / "low"
        / "bspline-fortran"
        / "generated_python"
        / "src"
        / "bspline_defc_module.py",
    )
    py_b4, py_iflag4 = coefficient_module.compute_b_spline_coefficients(
        (
            np.array([0.0, 1.0, 4.0, 9.0], dtype=np.float64),
            np.array([0.0, 0.0, 0.0, 1.5, 3.0, 3.0, 3.0], dtype=np.float64),
            3,
        ),
        np.zeros(4, dtype=np.float64),
    )
    py_b3, py_iflag3 = coefficient_module.compute_b_spline_coefficients(
        (
            np.array([2.0, 2.0, 2.0], dtype=np.float64),
            np.array([0.0, 0.0, 1.0, 2.0, 2.0], dtype=np.float64),
            2,
        ),
        np.zeros(3, dtype=np.float64),
    )
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
                note="Compiles pinned bspline_sub_module and evaluates each open-cubic basis with db1val.",
            ),
            _numeric_check(
                "compute_basis_functions_partition",
                np.array([np.sum(_parse_float_line(output[1]))], dtype=np.float64),
                np.array([np.sum(py_basis)], dtype=np.float64),
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Checks the partition-of-unity invariant derived independently from all four pinned db1val evaluations.",
            ),
            _numeric_check(
                "compute_coefficients_db1ink_direct_ordinary",
                _parse_float_line(coefficient_lines[0]),
                np.concatenate(([float(py_iflag4)], np.asarray(py_b4, dtype=np.float64))),
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Executes pinned db1ink on four quadratic samples and compares status plus the whole coefficient vector.",
            ),
            _numeric_check(
                "compute_coefficients_db1ink_direct_minimum_linear_boundary",
                _parse_float_line(coefficient_lines[1]),
                np.concatenate(([float(py_iflag3)], np.asarray(py_b3, dtype=np.float64))),
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Executes pinned db1ink on a three-point constant linear spline, the smallest practical valid case.",
            ),
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
    particle_driver = """
program run_mpm3d_particle
  use ParticleData, only: particle_list, InitParticle, dynamicRelaxationDamping, &
                          istep, EngKinetic, EngKinetic_prev
  implicit none (type, external)
  allocate(particle_list(2))
  particle_list(1)%VXp = [1.d0, 2.d0, 3.d0]
  particle_list(2)%VXp = [-1.d0, -2.d0, -3.d0]
  call InitParticle()
  write(*,'(6(ES24.16E3,1X))') particle_list(1)%VXp, particle_list(2)%VXp
  particle_list(1)%VXp = [1.d0, 2.d0, 3.d0]
  particle_list(2)%VXp = [-1.d0, -2.d0, -3.d0]
  istep = 1; EngKinetic = 1.d0; EngKinetic_prev = 2.d0
  call dynamicRelaxationDamping()
  write(*,'(6(ES24.16E3,1X))') particle_list(1)%VXp, particle_list(2)%VXp
  particle_list(1)%VXp = [1.d0, 2.d0, 3.d0]
  particle_list(2)%VXp = [-1.d0, -2.d0, -3.d0]
  istep = 0
  call dynamicRelaxationDamping()
  write(*,'(6(ES24.16E3,1X))') particle_list(1)%VXp, particle_list(2)%VXp
end program run_mpm3d_particle
"""
    particle_exe, _ = _compile_fortran_program_ordered(
        "mpm3d_particle_verify",
        ordered_sources=[FORTRAN_CORPUS_ROOT / "medium" / "MPM3D-F90" / "src" / "Particle.f90"],
        inline_sources=[("run_mpm3d_particle.f90", particle_driver)],
    )
    particle_lines = _run([str(particle_exe)], capture_stderr=True).stdout.strip().splitlines()
    particle_output = _parse_float_line(particle_lines[0])
    damping_output = [_parse_float_line(line) for line in particle_lines[1:3]]
    particle_module = _load_module(
        "mpm3d_particle_initial",
        TARGET_ROOT / "medium" / "MPM3D-F90" / "generated_python" / "src" / "particle_initial.py",
    )
    particle_data = np.zeros((2, 52), dtype=np.float64)
    initialized = particle_module.particle_initial(
        particle_data,
        initial_velocity=np.zeros(3, dtype=np.float64),
        position_bounds=(np.zeros(3, dtype=np.float64), np.zeros(3, dtype=np.float64)),
    )
    damping_module = _load_module(
        "mpm3d_dynamic_relaxation",
        TARGET_ROOT / "medium" / "MPM3D-F90" / "generated_python" / "src" / "dynamicRelaxationDamping.py",
    )
    damping_input = np.zeros(2, dtype=[("VXp", np.float64, (3,))])
    damping_input["VXp"] = np.array([[1.0, 2.0, 3.0], [-1.0, -2.0, -3.0]])
    damping_ordinary = damping_module.dynamicRelaxationDamping(damping_input.copy())["VXp"].ravel(order="C")
    damping_boundary = damping_module.dynamicRelaxationDamping(damping_input.copy())["VXp"].ravel(order="C")
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
            *_numeric_case_checks(
                "init_particle_velocity_direct",
                particle_output,
                initialized[:, 9:12].ravel(order="C"),
                ["p1vx", "p1vy", "p1vz", "p2vx", "p2vy", "p2vz"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned Particle.f90 and calls InitParticle before comparing zero-velocity initialization.",
            ),
            _numeric_check(
                "dynamic_relaxation_damping_direct_decreasing_energy",
                damping_output[0],
                damping_ordinary,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned Particle.f90 and exercises the decreasing-energy branch that zeroes velocities.",
            ),
            _numeric_check(
                "dynamic_relaxation_damping_direct_initial_step_boundary",
                damping_output[1],
                damping_boundary,
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned Particle.f90 and exercises the istep=0 early-return boundary.",
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
    config_driver = """
program run_wps_config
  use stringutil, only: despace, get_path
  implicit none (type, external)
  character(len=1024) :: geogrid_path, metgrid_path
  character(len=64) :: line
  integer :: value
  call get_command_argument(1,geogrid_path)
  call get_command_argument(2,metgrid_path)
  line = ' max_dom = 2 '
  call despace(line)
  read(line(index(line,'=')+1:),*) value
  write(*,'(I0)') value
  line = ' interval_seconds = 3600 '
  call despace(line)
  read(line(index(line,'=')+1:),*) value
  write(*,'(I0)') value
  line = ' parent_id = 1 '
  call despace(line)
  read(line(index(line,'=')+1:),*) value
  write(*,'(I0)') value
  line = ' e_we = 100 '
  call despace(line)
  read(line(index(line,'=')+1:),*) value
  write(*,'(I0)') value
  line = ' e_sn = 80 '
  call despace(line)
  read(line(index(line,'=')+1:),*) value
  write(*,'(I0)') value
  write(*,'(A)') trim(get_path(trim(geogrid_path)))
  write(*,'(A)') trim(get_path(trim(metgrid_path)))
end program run_wps_config
"""
    config_exe, _ = _compile_fortran_program_ordered(
        "wps_config_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "medium" / "WPS" / "ungrib" / "src" / "module_stringutil.F",
        ],
        inline_sources=[("run_wps_config.f90", config_driver)],
        compiler_flags=["-cpp", "-ffree-form"],
    )
    config_module = _load_module(
        "wps_config_parser",
        TARGET_ROOT / "medium" / "WPS" / "generated_python" / "src" / "config_parser.py",
    )
    with tempfile.TemporaryDirectory(prefix="wps-config-probe-") as temp_dir:
        temp_path = Path(temp_dir)
        namelist = temp_path / "namelist.wps"
        geogrid = temp_path / "nested" / "GEOGRID.TBL"
        metgrid = temp_path / "METGRID.TBL"
        geogrid.parent.mkdir()
        namelist.write_text(
            "[share]\nmax_dom = 2\ninterval_seconds = 3600\n"
            "[geogrid]\nparent_id = 1\ne_we = 100\ne_sn = 80\n",
            encoding="utf-8",
        )
        geogrid.write_text("", encoding="utf-8")
        metgrid.write_text("", encoding="utf-8")
        config_lines = _run(
            [str(config_exe), str(geogrid), "METGRID.TBL"],
            cwd=temp_path,
            capture_stderr=True,
        ).stdout.strip().splitlines()
        config_output = np.array([int(value) for value in config_lines[:5]], dtype=np.int64)
        old_cwd = Path.cwd()
        try:
            os.chdir(temp_path)
            domain, projection, processing = config_module.parse_wps_configurations(
                str(namelist), str(geogrid), "METGRID.TBL"
            )
        finally:
            os.chdir(old_cwd)
        source_paths = [config_lines[5].strip(), config_lines[6].strip()]
        target_paths = [
            Path(processing["geogrid_tbl"]).parent.as_posix() + "/",
            Path(processing["metgrid_tbl"]).parent.as_posix() + "/",
        ]
    config_expected = np.array(
        [domain["max_dom"], domain["interval_seconds"], projection["parent_id"], projection["e_we"], projection["e_sn"]],
        dtype=np.int64,
    )
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
            ),
            *_numeric_case_checks(
                "parse_wps_config_direct",
                config_output,
                config_expected,
                ["max_dom", "interval_seconds", "parent_id", "e_we", "e_sn"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned module_stringutil.F and uses despace before parsing WPS configuration values.",
            ),
            *_exact_case_checks(
                "config_table_path_direct",
                source_paths,
                target_paths,
                ["nested_ordinary", "relative_no_separator_boundary"],
                note="Executes pinned stringutil:get_path on table paths returned by the generated WPS configuration parser.",
            ),
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
    integrator_driver = """
program run_foodie_integrator
  use foodie_integrator_euler_explicit, only: integrator_euler_explicit
  implicit none (type, external)
  type(integrator_euler_explicit) :: integrator, initialized, rejected
  write(*,'(5(L1,1X))') integrator%is_supported('euler_explicit'), integrator%is_supported('bogus'), &
                         integrator%is_supported(' euler_explicit '), &
                         integrator%is_supported('EULER_EXPLICIT'), integrator%is_supported('')
  call initialized%initialize('euler_explicit', stop_on_fail=.false.)
  write(*,'(A)') trim(initialized%description())
  call rejected%initialize('bogus', stop_on_fail=.false.)
  write(*,'(A)') trim(rejected%description())
end program run_foodie_integrator
"""
    penf_stub = """
module penf
  use iso_fortran_env, only: int32, int64, real64
  implicit none
  integer, parameter :: I_P=int32, I8P=int64, R_P=real64
end module penf
"""
    foodie_root = FORTRAN_CORPUS_ROOT / "medium" / "FOODIE" / "src" / "lib"
    integrator_exe, _ = _compile_fortran_program_ordered(
        "foodie_integrator_verify",
        prelude_sources=[("penf.f90", penf_stub)],
        ordered_sources=[
            foodie_root / "foodie_error_codes.f90",
            foodie_root / "foodie_integrand_object.F90",
            foodie_root / "foodie_integrator_object.F90",
            foodie_root / "foodie_integrator_multistage_object.F90",
            foodie_root / "foodie_integrator_euler_explicit.F90",
        ],
        inline_sources=[("run_foodie_integrator.f90", integrator_driver)],
        compiler_flags=["-cpp"],
    )
    integrator_lines = _run([str(integrator_exe)]).stdout.strip().splitlines()
    integrator_output = [part.upper().startswith("T") for part in integrator_lines[0].split()]
    integrator_module = _load_module(
        "foodie_integrator_direct",
        TARGET_ROOT / "medium" / "FOODIE" / "generated_python" / "src" / "integrator.py",
    )

    def _factory(**kwargs: object) -> dict[str, object]:
        return dict(kwargs)

    target_acceptance = [
        integrator_module.initialize_integrator({"scheme": scheme, "cfl": 0.5}, _factory)["scheme"] == scheme
        for scheme in ("euler_explicit", "bogus", " euler_explicit ", "EULER_EXPLICIT", "")
    ]
    initialized_target = integrator_module.initialize_integrator(
        {"scheme": "euler_explicit", "cfl": 0.5}, _factory
    )["scheme"]
    rejected_target = integrator_module.initialize_integrator(
        {"scheme": "bogus", "cfl": 0.5}, _factory
    )["scheme"]
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
            *_numeric_case_checks(
                "integrator_scheme_support_direct",
                np.array(integrator_output, dtype=np.int32),
                np.array(target_acceptance, dtype=np.int32),
                ["euler_explicit", "bogus", "padded", "uppercase", "empty"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
                note="Compiles pinned FOODIE Euler integrator; interface-only penf stub supplies kind parameters.",
            ),
            *_exact_case_checks(
                "initialize_integrator_direct",
                [integrator_lines[1].strip(), integrator_lines[2].strip()],
                [initialized_target, rejected_target],
                ["ordinary_supported", "unsupported_boundary"],
                note="Compiles pinned Euler integrator and executes its stateful initialize routine for supported and rejected schemes.",
            ),
        ],
    )


def verify_cmathtuts() -> RepoResult:
    driver = """
program run_cmathtuts
  use iso_c_binding, only: c_int, c_double
  implicit none
  interface
    subroutine matrix_multiply(a,rows_a,cols_a,b,rows_b,cols_b,c,rows_c,cols_c) bind(c)
      use iso_c_binding, only: c_int, c_double
      integer(c_int) :: rows_a,cols_a,rows_b,cols_b,rows_c,cols_c
      real(c_double) :: a(rows_a,cols_a),b(rows_b,cols_b),c(rows_c,cols_c)
    end subroutine matrix_multiply
  end interface
  real(c_double) :: a(2,2), b(2,2), c(2,2)
  integer(c_int) :: n
  n = 2
  a(1,1)=1.d0; a(1,2)=2.d0; a(2,1)=3.d0; a(2,2)=4.d0
  b(1,1)=5.d0; b(1,2)=6.d0; b(2,1)=7.d0; b(2,2)=8.d0
  call matrix_multiply(a,n,n,b,n,n,c,n,n)
  write(*,'(4(ES24.16E3,1X))') reshape(c, (/4/))
end program run_cmathtuts
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "cmathtuts_verify",
        ordered_sources=[
            FORTRAN_CORPUS_ROOT
            / "medium"
            / "Cmathtuts"
            / "A_fortran"
            / "test4"
            / "fortran_matrix_multiply.f90"
        ],
        inline_sources=[("run_cmathtuts.f90", driver)],
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
            ),
            _numeric_check(
                "execute_blas_level3_operations_gemm_trace",
                np.array([_parse_float_line(output)[0] + _parse_float_line(output)[3]], dtype=np.float64),
                np.array([np.trace(results[0])], dtype=np.float64),
                atol=1.0e-12,
                rtol=1.0e-12,
                note="Compares the matrix trace derived from the complete pinned matrix_multiply result.",
            ),
        ],
    )


def verify_coretran() -> RepoResult:
    driver = """
program run_coretran
  use m_strings, only: compact, countEntries
  implicit none (type, external)
  character(len=32) :: text
  text = '  hello  '
  call compact(text)
  write(*,'(A)') trim(adjustl(text))
  text = ' world'
  call compact(text)
  write(*,'(A)') trim(adjustl(text))
  text = 'already'
  call compact(text)
  write(*,'(A)') trim(adjustl(text))
  text = '  padded  '
  call compact(text)
  write(*,'(A)') trim(adjustl(text))
  text = 'x'
  call compact(text)
  write(*,'(A)') trim(adjustl(text))
  text = 'alpha   beta gamma'
  write(*,'(I0)') countEntries(text)
  text = 'x'
  write(*,'(I0)') countEntries(text)
end program run_coretran
"""
    coretran_root = FORTRAN_CORPUS_ROOT / "medium" / "coretran" / "src" / "core"
    exe_path, _ = _compile_fortran_program_ordered(
        "coretran_verify",
        ordered_sources=[
            coretran_root / "m_variableKind.f90",
            coretran_root / "m_parameters.f90",
            coretran_root / "m_errors.f90",
            coretran_root / "m_strings.f90",
        ],
        inline_sources=[("run_coretran.f90", driver)],
    )
    output = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "coretran_string_ops",
        TARGET_ROOT / "medium" / "coretran" / "generated_python" / "src" / "string_operations.py",
    )
    ops = python_module.StringOperations()
    processed, formatted, status = ops.process_strings(
        ["  hello  ", " world", "already", "  padded  ", "x"], "parse"
    )
    ordinary_tokens, _, ordinary_status = ops.process_strings(["alpha   beta gamma"], "parse")
    boundary_tokens, _, boundary_status = ops.process_strings(["x"], "parse")
    return _repo_result(
        "medium",
        "coretran",
        [
            *_exact_case_checks(
                "process_strings_parse",
                [line.strip() for line in output[:5]],
                processed,
                ["hello", "world", "already", "padded", "single_character"],
                note="Compiles pinned m_strings.f90 and compares compacted tokens with the generated parser operation.",
            ),
            _exact_check("process_strings_status", status, True),
            *_numeric_case_checks(
                "count_entries_direct",
                np.array([int(output[5]), int(output[6])], dtype=np.int64),
                np.array(
                    [
                        len(ordinary_tokens) if ordinary_status else -1,
                        len(boundary_tokens) if boundary_status else -1,
                    ],
                    dtype=np.int64,
                ),
                ["ordinary_three_tokens", "single_token_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned m_strings.f90 and executes countEntries on multi-token and single-token strings.",
            ),
        ],
    )


def verify_atomsk() -> RepoResult:
    dependency_stubs = """
module comv
  use iso_fortran_env, only: real64
  implicit none
  integer, parameter :: dp = real64
  integer :: nerr = 0, ofu = 40
end module comv

module atoms
  use iso_fortran_env, only: real64
contains
  subroutine atomspecies(snumber, species)
    real(real64), intent(in) :: snumber
    character(len=2), intent(out) :: species
    select case (nint(snumber))
    case (1); species = 'H '
    case (6); species = 'C '
    case default; species = 'X '
    end select
  end subroutine atomspecies
  subroutine atommass(species, mass)
    character(len=*), intent(in) :: species
    real(real64), intent(out) :: mass
    mass = 0.0_real64
  end subroutine atommass
end module atoms

module constants
end module constants

module messages
  use iso_fortran_env, only: real64
contains
  subroutine atomsk_msg(code, strings, values)
    integer, intent(in) :: code
    character(len=*), intent(in) :: strings(:)
    real(real64), intent(in) :: values(:)
  end subroutine atomsk_msg
end module messages

module files
end module files

module subroutines
  use iso_fortran_env, only: real64
contains
  subroutine find_if_reduced(h, array, isreduced)
    real(real64), intent(in) :: h(3,3), array(:,:)
    logical, intent(out) :: isreduced
    isreduced = .false.
  end subroutine find_if_reduced
  subroutine find_nsp(values, entries)
    real(real64), intent(in) :: values(:)
    real(real64), allocatable, intent(out) :: entries(:,:)
    allocate(entries(1,1)); entries = 0.0_real64
  end subroutine find_nsp
end module subroutines
"""
    driver = """
program run_atomsk
  use comv, only: dp
  use out_xyz, only: write_xyz
  implicit none (type, external)
  real(dp) :: h(3,3)
  real(dp), allocatable :: p(:,:), aux(:,:)
  character(len=128), allocatable :: comment(:), auxnames(:)
  h = 0.0_dp
  h(1,1) = 10.0_dp; h(2,2) = 10.0_dp; h(3,3) = 10.0_dp
  allocate(p(3,4), comment(1))
  p(1,:) = [0.0_dp, 0.0_dp, 0.0_dp, 1.0_dp]
  p(2,:) = [1.25_dp, 2.5_dp, 3.75_dp, 6.0_dp]
  p(3,:) = [-1.0_dp, 0.5_dp, 2.0_dp, 1.0_dp]
  comment(1) = ''
  call write_xyz(h, p, comment, auxnames, aux, 'probe.xyz', 'xyz  ')
end program run_atomsk
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "atomsk_verify",
        prelude_sources=[("atomsk_dependency_stubs.f90", dependency_stubs)],
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "medium" / "atomsk" / "src" / "output" / "out_xyz.f90"
        ],
        inline_sources=[("run_atomsk.f90", driver)],
    )
    run_dir = exe_path.parent
    _run([str(exe_path)], cwd=run_dir, capture_stderr=True)
    output_lines = (run_dir / "probe.xyz").read_text(encoding="utf-8").splitlines()
    python_module = _load_module(
        "atomsk_generate_output",
        TARGET_ROOT / "medium" / "atomsk" / "generated_python" / "src" / "generate_output.py",
    )
    data = {
        "coordinates": np.array(
            [[0.0, 0.0, 0.0], [1.25, 2.5, 3.75], [-1.0, 0.5, 2.0]], dtype=np.float64
        ),
        "atomic_numbers": np.array([1, 6, 1], dtype=np.int64),
    }
    py_output = python_module.xyz_serializer(data)
    py_lines = py_output.splitlines()
    normalized_fortran = [
        output_lines[0].strip(),
        output_lines[1].strip(),
        " ".join(output_lines[2].split()),
        " ".join(output_lines[3].split()),
        " ".join(output_lines[4].split()),
    ]
    normalized_python = [
        py_lines[0].strip(),
        py_lines[1].strip(),
        f"{py_lines[2].split()[0]} " + " ".join(f"{float(v):.8f}" for v in py_lines[2].split()[1:]),
        f"{py_lines[3].split()[0]} " + " ".join(f"{float(v):.8f}" for v in py_lines[3].split()[1:]),
        f"{py_lines[4].split()[0]} " + " ".join(f"{float(v):.8f}" for v in py_lines[4].split()[1:]),
    ]
    species_dependencies = """
module comv
  use iso_fortran_env, only: real64
  implicit none
  integer, parameter :: dp=real64
  integer :: nerr=0
  character(len=1) :: pathsep='/'
end module comv
"""
    species_driver = """
program run_atomsk_species
  use comv, only: dp
  use atoms, only: atomspecies
  implicit none
  character(len=2) :: s1,s2,s3,s4
  call atomspecies(1._dp,s1)
  call atomspecies(6._dp,s2)
  call atomspecies(26._dp,s3)
  call atomspecies(999._dp,s4)
  write(*,'(A,"|",A,"|",A)') trim(s1),trim(s2),trim(s3)
  write(*,'(A)') trim(s4)
end program run_atomsk_species
"""
    atomsk_include_root = FORTRAN_CORPUS_ROOT / "medium" / "atomsk" / "src" / "include"
    species_exe, _ = _compile_fortran_program_ordered(
        "atomsk_species_direct_verify",
        prelude_sources=[("atomsk_species_dependencies.f90", species_dependencies)],
        ordered_sources=[atomsk_include_root / "strings.f90", atomsk_include_root / "atoms.f90"],
        inline_sources=[("run_atomsk_species.f90", species_driver)],
    )
    species_lines = _run([str(species_exe)], capture_stderr=True).stdout.strip().splitlines()
    ordinary_species_text = python_module.xyz_serializer(
        {
            "coordinates": np.zeros((3, 3), dtype=np.float64),
            "atomic_numbers": np.array([1, 6, 26], dtype=np.int64),
        }
    )
    ordinary_target_species = "|".join(
        line.split()[0] for line in ordinary_species_text.splitlines()[2:5]
    )
    unknown_species_text = python_module.xyz_serializer(
        {
            "coordinates": np.zeros((1, 3), dtype=np.float64),
            "atomic_numbers": np.array([999], dtype=np.int64),
        }
    )
    unknown_target_species = unknown_species_text.splitlines()[2].split()[0]
    return _repo_result(
        "medium",
        "atomsk",
        [
            *_exact_case_checks(
                "xyz_serializer",
                normalized_fortran,
                normalized_python,
                ["count", "title", "atom1", "atom2", "atom3"],
                note="Compiles pinned out_xyz.f90; dependency stubs provide Atomsk globals and helpers but the serialization and formatting execute upstream WRITE_XYZ.",
            ),
            _exact_check(
                "atomic_species_direct_ordinary",
                species_lines[0].strip(),
                ordinary_target_species,
                note="Executes pinned atoms:ATOMSPECIES for H, C, and Fe and compares symbols emitted by the generated XYZ serializer.",
            ),
            _exact_check(
                "atomic_species_direct_unknown_boundary",
                species_lines[1].strip(),
                unknown_target_species,
                note="Executes pinned atoms:ATOMSPECIES for an out-of-range atomic number and compares the generated serializer fallback.",
            ),
        ],
    )


def verify_dftd4() -> RepoResult:
    params = {
        "pbe": {"s6": 1.0, "s8": 0.95948085, "a1": 0.38574991, "a2": 4.80688534},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(params, handle)
        database_path = handle.name
    driver = """
program run_dftd4
  use dftd4_param, only: get_rational_damping, get_functional_id
  use dftd4_damping, only: damping_param
  use dftd4_damping_rational, only: rational_damping_param
  implicit none (type, external)
  class(damping_param), allocatable :: param
  call get_rational_damping('pbe', param)
  select type (param)
  type is (rational_damping_param)
    write(*,'(4(ES24.16E3,1X))') param%s6, param%s8, param%a1, param%a2
  class default
    error stop 'unexpected damping type'
  end select
  write(*,'(2(L1,1X))') get_functional_id('pbe') > 0, &
                         get_functional_id('not-a-functional') > 0
end program run_dftd4
"""
    dependency_stubs = [
        ("mctc_env.f90", "module mctc_env\nuse iso_fortran_env, only: real64\ninteger, parameter :: wp=real64\nend module mctc_env\n"),
        ("dftd4_damping.f90", "module dftd4_damping\ntype, abstract :: damping_param\nend type damping_param\nend module dftd4_damping\n"),
        (
            "dftd4_damping_rational.f90",
            "module dftd4_damping_rational\nuse mctc_env, only: wp\nuse dftd4_damping, only: damping_param\ntype, extends(damping_param) :: rational_damping_param\nreal(wp) :: s6=1._wp,s8,s9=1._wp,a1,a2,alp=16._wp\nend type rational_damping_param\nend module dftd4_damping_rational\n",
        ),
        (
            "dftd4_utils.f90",
            "module dftd4_utils\ncontains\npure function lowercase(string) result(output)\ncharacter(len=*), intent(in) :: string\ncharacter(len=len(string)) :: output\noutput=string\nend function lowercase\nend module dftd4_utils\n",
        ),
    ]
    exe_path, _ = _compile_fortran_program_ordered(
        "dftd4_verify",
        prelude_sources=dependency_stubs,
        ordered_sources=[FORTRAN_CORPUS_ROOT / "medium" / "dftd4" / "src" / "dftd4" / "param.f90"],
        inline_sources=[("run_dftd4.f90", driver)],
    )
    output_lines = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    output = output_lines[0]
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
    supported = python_module.get_supported_functionals(database_path=database_path)
    fortran_membership = np.array(
        [part.upper().startswith("T") for part in output_lines[1].split()], dtype=np.int32
    )
    python_membership = np.array(
        ["pbe" in supported, "not-a-functional" in supported], dtype=np.int32
    )
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
                note="Compiles pinned dftd4 param.f90; minimal dependency stubs provide only kinds, the damping record, and identity lowercase for an already-lowercase key.",
            ),
            _numeric_check(
                "get_rational_damping_pbe_sum",
                np.array([np.sum(_parse_float_line(output))], dtype=np.float64),
                np.array([np.sum(py_values)], dtype=np.float64),
                atol=1.0e-8,
                rtol=1.0e-8,
                note="Compares an aggregate invariant derived from all four pinned rational-damping fields.",
            ),
            *_numeric_case_checks(
                "get_functional_id_direct",
                fortran_membership,
                python_membership,
                ["ordinary_supported_pbe", "unknown_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-bool-array",
                note="Compiles pinned param.f90 and executes get_functional_id for a supported and an unknown key.",
            ),
        ],
    )


def verify_incompact3d() -> RepoResult:
    dependency_stubs = """
module param
  use iso_fortran_env, only: real64
  implicit none
  integer, parameter :: mytype=real64
  integer :: iibm=0, istret=0, iimplicit=0
  logical :: nclx=.false., ncly=.false., nclz=.false.
  real(mytype), parameter :: zero=0._mytype, one=1._mytype, two=2._mytype
  real(mytype) :: acix6,aciy6,aciz6,af1x,af1y,af1z,af2x,af2y,af2z,afmx,afmy,afmz,afnx,afny,afnz
  real(mytype) :: aicix6,aiciy6,aiciz6,ailcaix6,ailcaiy6,ailcaiz6,alcaix6,alcaiy6,alcaiz6
  real(mytype) :: alsaix,alsajy,alsakz,as1x,as1y,as1z,as2x,as2y,as2z,as3x,as3y,as3z,as4x,as4y,as4z
  real(mytype) :: asix,asjy,askz,asmx,asmy,asmz,asnx,asny,asnz,asttx,astty,asttz,astx,asty,astz
  real(mytype) :: bcix6,bciy6,bciz6,bf1x,bf1y,bf1z,bfnx,bfny,bfnz,bicix6,biciy6,biciz6
  real(mytype) :: bs1x,bs1y,bs1z,bs3x,bs3y,bs3z,bs4x,bs4y,bs4z,bsix,bsjy,bskz,bsnx,bsny,bsnz
  real(mytype) :: bsttx,bstty,bsttz,bstx,bsty,bstz,cf1x,cf1y,cf1z,cfnx,cfny,cfnz,cicix6,ciciy6,ciciz6
  real(mytype) :: cs1x,cs1y,cs1z,cs4x,cs4y,cs4z,csix,csjy,cskz,csnx,csny,csnz,csttx,cstty,csttz
  real(mytype) :: dicix6,diciy6,diciz6,ds1x,ds1y,ds1z,dsix,dsjy,dskz,dsnx,dsny,dsnz
end module param
module derivX
  use param, only: mytype
  real(mytype) :: afix=.5_mytype,bfix=0._mytype,alfaix=.5_mytype
end module derivX
module derivY
  use param, only: mytype
  real(mytype) :: afjy=.5_mytype,bfjy=0._mytype,alfajy=.5_mytype
end module derivY
module derivZ
  use param, only: mytype
  real(mytype) :: afkz=.5_mytype,bfkz=0._mytype,alfakz=.5_mytype
end module derivZ
module ibm
  use param, only: mytype
contains
  subroutine lagpolx(a); real(mytype),intent(inout)::a(:,:,:); end subroutine
  subroutine cubsplx(a,l); real(mytype),intent(inout)::a(:,:,:);real(mytype),intent(in)::l; end subroutine
  subroutine lagpoly(a); real(mytype),intent(inout)::a(:,:,:); end subroutine
  subroutine cubsply(a,l); real(mytype),intent(inout)::a(:,:,:);real(mytype),intent(in)::l; end subroutine
  subroutine lagpolz(a); real(mytype),intent(inout)::a(:,:,:); end subroutine
  subroutine cubsplz(a,l); real(mytype),intent(inout)::a(:,:,:);real(mytype),intent(in)::l; end subroutine
end module ibm
"""
    driver = """
program run_incompact3d
  use param, only: mytype
  implicit none (type, external)
  external :: derx_00, derx_11
  integer, parameter :: nx=5,ny=1,nz=1
  real(mytype) :: tx(nx,ny,nz),ux(nx,ny,nz),rx(nx,ny,nz),sx(ny,nz)
  real(mytype) :: ffx(nx),fsx(nx),fwx(nx),lind
  ux(:,1,1)=[1._mytype,2._mytype,3._mytype,4._mytype,5._mytype]
  ffx=0._mytype; fsx=0._mytype; fwx=1._mytype; lind=0._mytype
  call derx_00(tx,ux,rx,sx,ffx,fsx,fwx,nx,ny,nz,0,lind)
  write(*,'(5(ES24.16E3,1X))') tx(:,1,1)
  call derx_11(tx,ux,rx,sx,ffx,fsx,fwx,nx,ny,nz,1,lind)
  write(*,'(5(ES24.16E3,1X))') tx(:,1,1)
  call derx_11(tx,ux,rx,sx,ffx,fsx,fwx,nx,ny,nz,0,lind)
  write(*,'(5(ES24.16E3,1X))') tx(:,1,1)
end program run_incompact3d
"""
    exe_path, _ = _compile_fortran_program_ordered(
        "incompact3d_verify",
        prelude_sources=[("incompact_dependency_stubs.f90", dependency_stubs)],
        ordered_sources=[
            FORTRAN_CORPUS_ROOT / "medium" / "Incompact3d" / "src" / "derive.f90"
        ],
        inline_sources=[("run_incompact3d.f90", driver)],
    )
    output_lines = _run([str(exe_path)], capture_stderr=True).stdout.strip().splitlines()
    python_module = _load_module(
        "incompact3d_spatial_derivatives",
        TARGET_ROOT / "medium" / "Incompact3d" / "generated_python" / "src" / "spatial_derivatives.py",
    )
    velocity = np.zeros((5, 1, 1, 3), dtype=np.float64)
    velocity[:, 0, 0, 0] = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
    pressure = np.zeros((5, 1, 1), dtype=np.float64)
    coeffs = {
        "ffx": np.zeros(5, dtype=np.float64),
        "fsx": np.zeros(5, dtype=np.float64),
        "fwx": np.ones(5, dtype=np.float64),
        "ffy": np.zeros(1, dtype=np.float64),
        "fsy": np.zeros(1, dtype=np.float64),
        "fwy": np.ones(1, dtype=np.float64),
        "ffz": np.zeros(1, dtype=np.float64),
        "fsz": np.zeros(1, dtype=np.float64),
        "fwz": np.ones(1, dtype=np.float64),
    }
    velocity_derivatives, _, _ = python_module.compute_spatial_derivatives(velocity, pressure, coeffs)
    py_deriv = velocity_derivatives[:, 0, 0, 0, 0]
    return _repo_result(
        "medium",
        "Incompact3d",
        [
            *_numeric_case_checks(
                "compute_spatial_derivatives",
                _parse_float_line(output_lines[0]),
                py_deriv,
                ["i1", "i2", "i3", "i4", "i5"],
                atol=1.0e-10,
                rtol=1.0e-10,
                note="Compiles pinned derive.f90 and executes derx_00 on a periodic 1x1x5 field; interface-only stubs supply coefficient modules and inactive IBM hooks.",
            ),
            _numeric_check(
                "compute_spatial_derivatives_derx11_direct_ordinary_parity1",
                _parse_float_line(output_lines[1]),
                py_deriv,
                atol=1.0e-10,
                rtol=1.0e-10,
                note="One whole-array probe compiling pinned derive.f90 and executing derx_11 with npaire=1.",
            ),
            _numeric_check(
                "compute_spatial_derivatives_derx11_direct_parity0_boundary",
                _parse_float_line(output_lines[2]),
                py_deriv,
                atol=1.0e-10,
                rtol=1.0e-10,
                note="One whole-array probe compiling pinned derive.f90 and executing derx_11 with npaire=0.",
            ),
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
    dload_driver = """
program run_abaqus_dload
  implicit none
  real(8) :: f, time(2), coords(3)
  integer :: kstep,kinc,noel,npt,layer,kspt,jltyp
  character(len=80) :: sname
  kstep=1; kinc=1; noel=1; npt=1; layer=1; kspt=1; jltyp=1; sname='PRESSURE'
  time=[0.0d0,0.1d0]
  coords=[10.0d0,50.0d0,0.0d0]
  call dload(f,kstep,kinc,time,noel,npt,layer,kspt,coords,jltyp,sname)
  write(*,'(ES24.16E3)') f
  coords=[20.0d0,50.0d0,0.0d0]
  call dload(f,kstep,kinc,time,noel,npt,layer,kspt,coords,jltyp,sname)
  write(*,'(ES24.16E3)') f
  coords=[15.0d0,50.0d0,0.0d0]
  call dload(f,kstep,kinc,time,noel,npt,layer,kspt,coords,jltyp,sname)
  write(*,'(ES24.16E3)') f
  coords=[10.0d0,55.0d0,0.0d0]
  call dload(f,kstep,kinc,time,noel,npt,layer,kspt,coords,jltyp,sname)
  write(*,'(ES24.16E3)') f
  coords=[10.0d0,56.0d0,0.0d0]
  call dload(f,kstep,kinc,time,noel,npt,layer,kspt,coords,jltyp,sname)
  write(*,'(ES24.16E3)') f
end program run_abaqus_dload
"""
    dload_exe, _ = _compile_fortran_program_ordered(
        "abaqus_dload_verify",
        ordered_sources=[FORTRAN_CORPUS_ROOT / "low" / "ABAQUS" / "DLoad_moving_pressure.for"],
        inline_sources=[("run_abaqus_dload.f90", dload_driver)],
        support_files=[("aba_param.inc", "      implicit real*8(a-h,o-z)\n")],
    )
    dload_output = _parse_float_line(
        " ".join(_run([str(dload_exe)], capture_stderr=True).stdout.strip().splitlines())
    )
    uel_driver = """
program run_abaqus_uel_bodyforce_direct
  implicit none
  integer, parameter :: ndofel=6,nrhs=2,nsvars=1,nprops=8,mcrd=2,nnode=3
  integer, parameter :: mlvarx=6,mdload=1,npredf=1,njprop=1
  real(8) :: rhs(mlvarx,nrhs),stif(ndofel,ndofel),svars(nsvars),energy(8)
  real(8) :: props(nprops),coords(mcrd,nnode),u(ndofel),du(mlvarx,nrhs)
  real(8) :: v(ndofel),a(ndofel),time(2),params(1),adlmag(mdload,1)
  real(8) :: predef(2,npredf,nnode),ddlmag(mdload,1),dtime,pnewdt,period
  integer :: jdltyp(mdload,1),lflags(1),jprops(njprop)
  integer :: jtype,kstep,kinc,jelem,ndload
  props=[2.d0,3.d0,0.d0,0.d0,1.d0,0.d0,0.d0,0.d0]
  coords(:,1)=[0.d0,0.d0]; coords(:,2)=[1.d0,0.d0]; coords(:,3)=[0.d0,1.d0]
  rhs=0.d0; stif=0.d0; svars=0.d0; energy=0.d0; u=0.d0; du=0.d0
  v=0.d0; a=0.d0; params=0.d0; adlmag=0.d0; predef=0.d0; ddlmag=0.d0
  jdltyp=0; lflags=0; jprops=0; dtime=1.d0; pnewdt=1.d0; period=1.d0
  jtype=1; kstep=1; kinc=1; jelem=1; ndload=0
  time=[0.d0,1.d0]
  call UEL(rhs,stif,svars,energy,ndofel,nrhs,nsvars,props,nprops,coords,mcrd,nnode, &
           u,du,v,a,jtype,time,dtime,kstep,kinc,jelem,params,ndload,jdltyp,adlmag, &
           predef,npredf,lflags,mlvarx,ddlmag,mdload,pnewdt,jprops,njprop,period)
  write(*,'(6(ES24.16E3,1X))') rhs(:,1)
  time=0.d0
  call UEL(rhs,stif,svars,energy,ndofel,nrhs,nsvars,props,nprops,coords,mcrd,nnode, &
           u,du,v,a,jtype,time,dtime,kstep,kinc,jelem,params,ndload,jdltyp,adlmag, &
           predef,npredf,lflags,mlvarx,ddlmag,mdload,pnewdt,jprops,njprop,period)
  write(*,'(6(ES24.16E3,1X))') rhs(:,1)
end program run_abaqus_uel_bodyforce_direct
"""
    uel_exe, _ = _compile_fortran_program_ordered(
        "abaqus_uel_bodyforce_direct_verify",
        ordered_sources=[FORTRAN_CORPUS_ROOT / "low" / "ABAQUS" / "UEL_bodyforce.for"],
        inline_sources=[("run_abaqus_uel_bodyforce_direct.f90", uel_driver)],
        support_files=[("ABA_PARAM.INC", "      implicit real*8(a-h,o-z)\n")],
    )
    uel_direct_lines = _run([str(uel_exe)], capture_stderr=True).stdout.strip().splitlines()
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

    uel_module = _load_module(
        "abaqus_uel_bodyforce",
        TARGET_ROOT / "low" / "ABAQUS" / "generated_python" / "src" / "uel_bodyforce.py",
    )

    def _python_uel_bodyforce(total_time: float) -> np.ndarray:
        local_rhs = np.zeros((6, 2), dtype=np.float64)
        local_stif = np.zeros((6, 6), dtype=np.float64)
        result, _, _ = uel_module.uel_bodyforce(
            local_rhs, local_stif, np.zeros(1), np.zeros(8), 6, 2, 1,
            np.array([2.,3.,0.,0.,1.,0.,0.,0.]), 8,
            np.array([[0.,1.,0.],[0.,0.,1.]]), 2, 3,
            np.zeros(6), np.zeros((6,2)), np.zeros(6), np.zeros(6), 1,
            np.array([0.,total_time]), 1., 1, 1, 1, np.zeros(1), 0,
            np.zeros((1,1), dtype=np.int64), np.zeros((1,1)),
            np.zeros((2,1,3)), 1, np.zeros(1, dtype=np.int64), 6,
            np.zeros((1,1)), 1, 1., np.zeros(1, dtype=np.int64), 1, 1.,
        )
        return np.asarray(result[:, 0], dtype=np.float64)

    uel_rotating = _python_uel_bodyforce(1.0)
    uel_zero_time = _python_uel_bodyforce(0.0)
    dload_module = _load_module(
        "abaqus_dload",
        TARGET_ROOT / "low" / "ABAQUS" / "generated_python" / "src" / "dload_moving_pressure.py",
    )
    dload_python = []
    for point in (
        [10.0, 50.0, 0.0],
        [20.0, 50.0, 0.0],
        [15.0, 50.0, 0.0],
        [10.0, 55.0, 0.0],
        [10.0, 56.0, 0.0],
    ):
        force = np.zeros(1, dtype=np.float64)
        dload_module.dload(
            force, 1, 1, np.array([0.0, 0.1]), 1, 1, 1, 1,
            np.array(point, dtype=np.float64), 1, "PRESSURE",
        )
        dload_python.append(force[0])
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
            ),
            *_numeric_case_checks(
                "dload_moving_pressure",
                dload_output,
                np.array(dload_python, dtype=np.float64),
                ["inside", "outside", "x_boundary", "y_boundary", "y_outside"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            _numeric_check(
                "uel_bodyforce_direct_rotating_ordinary",
                _parse_float_line(uel_direct_lines[0]),
                uel_rotating,
                atol=1.0e-10,
                rtol=1.0e-10,
                note="One whole-array probe compiling pinned UEL_bodyforce.for for a rotating triangular element.",
            ),
            _numeric_check(
                "uel_bodyforce_direct_zero_time_boundary",
                _parse_float_line(uel_direct_lines[1]),
                uel_zero_time,
                atol=1.0e-10,
                rtol=1.0e-10,
                note="One whole-array probe compiling pinned UEL_bodyforce.for at the zero-angular-speed boundary.",
            ),
        ],
    )


def verify_forpy() -> RepoResult:
    forpy_source = FORTRAN_CORPUS_ROOT / "low" / "forpy" / "forpy_mod.F90"
    driver = """
program run_forpy
  use forpy_mod, only: NO_NUMPY_ERROR, EXCEPTION_ERROR, METH_VARARGS, &
                       METH_KEYWORDS, METH_NOARGS
  implicit none (type, external)
  write(*,'(5(I0,1X))') NO_NUMPY_ERROR, METH_VARARGS, EXCEPTION_ERROR, &
                         METH_KEYWORDS, METH_NOARGS
end program run_forpy
"""
    python_includes = _run(["python3-config", "--includes"], capture_stderr=True).stdout.split()
    python_ldflags = _run(
        ["python3-config", "--embed", "--ldflags"], capture_stderr=True
    ).stdout.split()
    exe_path, _ = _compile_fortran_program_ordered(
        "forpy_verify",
        ordered_sources=[forpy_source],
        inline_sources=[("run_forpy.f90", driver)],
        compiler_flags=["-cpp", *python_includes],
        linker_flags=python_ldflags,
    )
    fortran_values = np.array(
        [int(value) for value in _run([str(exe_path)], capture_stderr=True).stdout.split()],
        dtype=np.int64,
    )
    python_module = _load_module(
        "forpy_analysis",
        TARGET_ROOT / "low" / "forpy" / "generated_python" / "src" / "forpy_analysis.py",
    )
    analysis = python_module.analyze_fortran_module(str(forpy_source), {})
    parameters = {
        declaration.split("=", 1)[0].strip(): declaration.split("=", 1)[1].strip()
        for declaration in analysis["parameters"]
    }
    return _repo_result(
        "low",
        "forpy",
        [
            _exact_check("analyze_fortran_module_name", analysis["module_name"], "forpy_mod"),
            _exact_check(
                "analyze_fortran_intrinsic_module",
                sorted(analysis["intrinsic_modules"]),
                ["iso_c_binding", "iso_fortran_env"],
            ),
            _exact_check(
                "analyze_fortran_dependencies",
                sorted(analysis["dependencies"]),
                ["iso_c_binding", "iso_fortran_env"],
            ),
            *_numeric_case_checks(
                "forpy_public_parameter_direct",
                fortran_values[:2],
                np.array(
                    [
                        int(str(parameters["NO_NUMPY_ERROR"]).split("_")[0]),
                        int(str(parameters["METH_VARARGS"]).split("_")[0]),
                    ],
                    dtype=np.int64,
                ),
                ["no_numpy_error", "meth_varargs"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles the pinned forpy_mod.F90 and reads five public parameters; the generated analyzer extracts the same declarations from that exact file.",
            ),
            *_guarded_case_checks(
                "forpy_public_parameter_direct_exception_error",
                fortran_values[2:3],
                ["value"],
                lambda: np.array([int(str(parameters["EXCEPTION_ERROR"]).split("_")[0])], dtype=np.int64),
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            *_guarded_case_checks(
                "forpy_public_parameter_direct_meth_keywords",
                fortran_values[3:4],
                ["value"],
                lambda: np.array([int(str(parameters["METH_KEYWORDS"]).split("_")[0])], dtype=np.int64),
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
            *_guarded_case_checks(
                "forpy_public_parameter_direct_meth_noargs",
                fortran_values[4:5],
                ["value"],
                lambda: np.array([int(str(parameters["METH_NOARGS"]).split("_")[0])], dtype=np.int64),
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
            ),
        ],
    )


def verify_io_fortran_library() -> RepoResult:
    driver_source = """
program run_io_lib
  use io_fortran_lib, only: String, NL
  implicit none (type, external)
  type(String) :: contents
  integer :: stat, i
  character(len=256), dimension(5) :: files
  files = (/ 'input1.txt', 'input2.txt', 'input3.txt', 'input4.txt', 'input5.txt' /)
  do i = 1, 5
    call contents%read_file(trim(files(i)), stat=stat)
    if (stat /= 0) error stop 'read_file failed'
    write(*,'(I0)') contents%count(NL) + 1
  end do
  call contents%read_file(trim(files(1)), stat=stat)
  write(*,'(I0)') contents%count('module')
  call contents%read_file(trim(files(4)), stat=stat)
  write(*,'(I0)') contents%count('contains')
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
            [
                "program io_probe_five",
                "  implicit none",
                "  integer :: i",
                "  i = 5",
                "  print *, i",
                "end program io_probe_five",
            ],
        ]
        driver = driver_source
        for index, lines in enumerate(source_texts, start=1):
            source_file = temp_path / f"input{index}.txt"
            source_file.write_text("\n".join(lines), encoding="utf-8")
            source_files.append(source_file)
            driver = driver.replace(f"input{index}.f90", str(source_file).replace("\\", "\\\\"))
            driver = driver.replace(f"input{index}.txt", str(source_file).replace("\\", "\\\\"))
        io_root = FORTRAN_CORPUS_ROOT / "low" / "IO-Fortran-Library" / "src"
        exe_path, _ = _compile_fortran_program_ordered(
            "io_fortran_library_verify",
            ordered_sources=[
                io_root / "modules" / "io_fortran_lib_mod.f90",
                io_root / "io_fortran_lib" / "array_printing_impl.f90",
                io_root / "io_fortran_lib" / "binary_io_impl.f90",
                io_root / "io_fortran_lib" / "file_io_impl.f90",
                io_root / "io_fortran_lib" / "internal_io_impl.f90",
                io_root / "io_fortran_lib" / "join_split_impl.f90",
                io_root / "io_fortran_lib" / "operators_impl.f90",
                io_root / "io_fortran_lib" / "string_methods_impl.f90",
                io_root / "io_fortran_lib" / "text_io_impl.f90",
            ],
            inline_sources=[("run_io_lib.f90", driver)],
        )
        fortran_output = [
            int(value)
            for value in _run([str(exe_path)], cwd=temp_path, capture_stderr=True).stdout.split()
        ]
        fortran_values = fortran_output[:5]
        fortran_counts = fortran_output[5:7]
        python_module = _load_module(
            "io_fortran_parser",
            TARGET_ROOT / "low" / "IO-Fortran-Library" / "generated_python" / "src" / "io_parser.py",
        )
        parsed, _ = python_module.parse_source_files([str(path) for path in source_files])
        py_values = [len(parsed[str(path)]["lines"]) for path in source_files]
        py_counts = [
            "\n".join(parsed[str(source_files[0])]["lines"]).count("module"),
            "\n".join(parsed[str(source_files[3])]["lines"]).count("contains"),
        ]
    return _repo_result(
        "low",
        "IO-Fortran-Library",
        [
            *_numeric_case_checks(
                "parse_source_files_line_count",
                np.array(fortran_values, dtype=np.int64),
                np.array(py_values, dtype=np.int64),
                ["module_minimal", "program_print", "function_module", "subroutine", "program_six_lines"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Compiles pinned io_fortran_lib and compares its String%read_file line count with the generated parser.",
            ),
            *_numeric_case_checks(
                "count_substring_chars_direct",
                np.array(fortran_counts, dtype=np.int64),
                np.array(py_counts, dtype=np.int64),
                ["ordinary_multiple_matches", "absent_boundary"],
                atol=0.0,
                rtol=0.0,
                comparison="exact-array",
                note="Executes pinned String%count and compares token occurrences in source lines returned by the generated parser.",
            ),
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
