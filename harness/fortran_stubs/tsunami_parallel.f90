!  tsunami_parallel.f90
!  Extract the pure (non-coarray) helpers num_tiles, tile_indices_1d
!  from tsunami's mod_parallel so they can be called from Python via f2py.
!
!  Source: tsunami/src/ch08/mod_parallel.f90 (Curcic, Modern Fortran).
!  Only the pieces that do not reference num_images()/this_image()
!  are reproduced here. Default `integer` (int32 on current
!  toolchains) is used so that f2py's wrapper generator does not
!  need to import a kind parameter from iso_fortran_env.

module tsunami_parallel
    implicit none
    private
    public :: num_tiles, tile_indices_1d
contains

    pure function num_tiles(n) result(tiles)
        integer, intent(in) :: n
        integer :: tiles(2)
        integer :: denoms(n)
        integer :: dim1(n*n), dim2(n*n)
        integer :: i, j, ndenoms, npairs
        real :: n1, n2

        ndenoms = 0
        do i = 1, n
            if (mod(n, i) == 0) then
                ndenoms = ndenoms + 1
                denoms(ndenoms) = i
            end if
        end do

        npairs = 0
        do j = 1, ndenoms
            do i = 1, ndenoms
                if (denoms(i) * denoms(j) == n) then
                    npairs = npairs + 1
                    dim1(npairs) = denoms(i)
                    dim2(npairs) = denoms(j)
                end if
            end do
        end do

        tiles = [dim1(1), dim2(1)]
        do i = 2, npairs
            n1 = norm2(real([dim1(i), dim2(i)]) - sqrt(real(n)))
            n2 = norm2(real(tiles) - sqrt(real(n)))
            if (n1 < n2) tiles = [dim1(i), dim2(i)]
        end do
    end function num_tiles

    pure function tile_indices_1d(dims, i, n) result(indices)
        integer, intent(in) :: dims, i, n
        integer :: indices(2)
        integer :: offset, tile_size

        tile_size = dims / n
        indices(1) = (i - 1) * tile_size + 1
        indices(2) = indices(1) + tile_size - 1
        offset = n - mod(dims, n)
        if (i > offset) then
            indices(1) = indices(1) + i - offset - 1
            indices(2) = indices(2) + i - offset
        end if
    end function tile_indices_1d

end module tsunami_parallel
