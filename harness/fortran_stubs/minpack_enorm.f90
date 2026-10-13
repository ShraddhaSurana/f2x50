!  minpack_enorm.f90
!  Standalone extraction of enorm() from minpack/src/minpack.f90
!  (BSD-licensed). Double-precision only, so we use real(kind=8)
!  directly to keep f2py's wrapper generator happy (no module-scope
!  wp parameter inside the function signature).

pure real(kind=8) function enorm(n, x)
    implicit none
    integer, intent(in) :: n
    real(kind=8), intent(in) :: x(n)

    integer :: i
    real(kind=8) :: agiant, s1, s2, s3, xabs, x1max, x3max
    real(kind=8), parameter :: zero   = 0.0d0
    real(kind=8), parameter :: one    = 1.0d0
    real(kind=8), parameter :: rdwarf = 3.834d-20
    real(kind=8), parameter :: rgiant = 1.304d19

    s1 = zero
    s2 = zero
    s3 = zero
    x1max = zero
    x3max = zero
    agiant = rgiant / real(n, kind=8)
    do i = 1, n
        xabs = abs(x(i))
        if (xabs > rdwarf .and. xabs < agiant) then
            s2 = s2 + xabs**2
        elseif (xabs <= rdwarf) then
            if (xabs <= x3max) then
                if (xabs /= zero) s3 = s3 + (xabs/x3max)**2
            else
                s3 = one + s3*(x3max/xabs)**2
                x3max = xabs
            end if
        elseif (xabs <= x1max) then
            s1 = s1 + (xabs/x1max)**2
        else
            s1 = one + s1*(x1max/xabs)**2
            x1max = xabs
        end if
    end do

    if (s1 /= zero) then
        enorm = x1max*sqrt(s1 + (s2/x1max)/x1max)
    elseif (s2 == zero) then
        enorm = x3max*sqrt(s3)
    else
        if (s2 >= x3max) then
            enorm = sqrt(s2*(one + (x3max/s2)*(x3max*s3)))
        else
            enorm = sqrt(x3max*((s2/x3max) + (x3max*s3)))
        end if
    end if
end function enorm
