program f2x50_root_bisection
  use root_module, wp => root_module_rk
  implicit none
  real(wp) :: xzero, fzero
  integer :: iflag

  call root_scalar('bisection', objective, 1.0_wp, 2.0_wp, xzero, fzero, iflag)
  write(*,'(2(ES24.16E3,1X),I0)') xzero, fzero, iflag

contains

  function objective(x) result(y)
    real(wp), intent(in) :: x
    real(wp) :: y
    y = x*x - 2.0_wp
  end function objective
end program f2x50_root_bisection
