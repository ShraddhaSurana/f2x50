#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/fortran_stubs"

python -m numpy.f2py -c --backend meson dasum.f -m dasum_f
python -m numpy.f2py -c --backend meson dcopy.f -m dcopy_f
python -m numpy.f2py -c --backend meson ddot.f -m ddot_f
python -m numpy.f2py -c --backend meson dnrm2.f90 -m dnrm2_f
python -m numpy.f2py -c --backend meson dscal.f -m dscal_f
python -m numpy.f2py -c --backend meson minpack_enorm.f90 -m enorm_f
python -m numpy.f2py -c --backend meson tsunami_parallel.f90 -m tsunami_f
