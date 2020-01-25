import time

import itertools
import numpy as np
from scipy.sparse import lil_matrix, csr_matrix

from Variables import Variables
# from Functions.Identity import Identity


class MatMaker:
    def __init__(self, target, n_cell, n_val, ave_field=None, mpi_comm=None):
        self._comm = mpi_comm
        if mpi_comm is not None:
            self._size = mpi_comm.Get_size()
            self._rank = mpi_comm.Get_rank()
            self._mpi = True
        else:
            self._size = 1
            self._rank = 0
            self._mpi = False
        self._leader = (self._mpi and self._rank == 0) or not self._mpi

        self.n_cell = n_cell
        self.n_val = n_val
        self.n_size_in = n_cell * n_val

        # self.mesh = mesh
        # self.flow_data = flow_data

        self._variables = target
        # self._check_target()
        self.n_return = self._variables.n_return
        self.n_size_out = n_cell * self.n_return

        if self._leader:
            self.operator = lil_matrix((self.n_size_out, self.n_size_in), dtype=np.float64)
        else:
            self.operator = None

        if ave_field is None:
            n_val_ph = 5  # rho, u, v, w, pressure
        else:
            n_val_ph = 7  # add energy and temperature
        self._ph = PlaceHolder(n_cell, n_val_ph, ave_field)

    def _check_target(self):
        if not issubclass(self._variables, Variables):
            raise TypeError

    def get_mat(self):
        t_start = time.time()

        i_start = self._rank % self._size
        i_step = self._size

        val_array = np.empty((0, 5), dtype=np.float64)
        for id_cell in range(i_start, self.n_cell, i_step):
            for val in self._calc_values(id_cell):
                np.append(val_array, val.reshape(1, 5), axis=0)
            if self._leader:
                self._print_progress(id_cell, t_start)

        if self._mpi and self._rank == 0:
            array_list = self._comm.gather(val_array, root=0)
            self._set_mat(np.vstack(array_list))
        elif not self._mpi:
            self._set_mat(val_array)
        else:
            pass

        t_end = time.time() - t_start
        if self._leader:
            print('Done. Elapsed time: {:.0f}'.format(t_end))
            return csr_matrix(self.operator)
        else:
            return None

    def _print_progress(self, id_cell, t_start):
        interval = 10

        prog_0 = int(100.0 * (id_cell - 1) / self.n_cell)
        prog_1 = int(100.0 * id_cell / self.n_cell)

        if prog_0 % interval == interval - 1 and prog_1 % interval == 0:
            t_elapse = time.time() - t_start
            print(str(prog_1) + ' %, Elapsed time: {:.0f}'.format(t_elapse) + ' [sec]')

    def _set_mat(self, val_array):
        for id_cell, id_val, ref_cell, ref_val, val in val_array:
            i_row = id_cell * self.n_return + id_val
            i_col = ref_cell * self.n_val + ref_val
            self.operator[i_row, i_col] = val

    def _calc_values(self, id_cell):
        ref_cells = self._variables.get_leaves(id_cell)
        for ref_cell, ref_val in itertools.product(ref_cells, range(self.n_val)):
            self._ph.set_ph(ref_cell, ref_val)
            func_val = self._variables.formula(self._ph, id_cell)
            for id_val, val in enumerate(func_val):
                yield np.array([id_cell, id_val, ref_cell, ref_val, val], dtype=np.float64)


class PlaceHolder:
    def __init__(self, n_cell, n_val, ave_field=None):
        self._gamma = 1.4
        self._gamma_2 = 1.0 / (1.4 - 1.0)

        self.n_cell = n_cell
        self.n_val = n_val
        self.shape = (self.n_cell, self.n_val)

        self.i_cell = -1
        self.i_val = -1

        self._ave_field = ave_field

        if n_val > 5 and ave_field is None:
            # For calculating energy and temperature
            raise Exception

    def set_ph(self, i_cell, i_val):
        self.i_cell = i_cell
        self.i_val = i_val

    def __getitem__(self, x):
        i_cell = x[0]
        i_val = x[1]

        if 0 <= i_val < 5:
            # for Rho, u vel, v vel, w vel, pressure
            return float(i_cell == self.i_cell and i_val == self.i_val)
        elif i_val == 5:
            # for energy
            return self._calc_energy(i_cell)
        elif i_val == 6:
            # for temperature
            return self._calc_temperature(i_cell)
        else:
            raise Exception

    def _calc_energy(self, i_cell):
        # for energy variation
        g2 = self._gamma_2

        rho = self[i_cell, 0]
        u = self[i_cell, 1]
        v = self[i_cell, 2]
        w = self[i_cell, 3]
        p = self[i_cell, 4]

        ave = self._ave_field.data
        rho_ave = ave[i_cell, 0]
        u_ave = ave[i_cell, 1]
        v_ave = ave[i_cell, 2]
        w_ave = ave[i_cell, 3]

        e = g2 * p
        e += 0.5 * rho * (u_ave * u_ave + v_ave * v_ave + w_ave * w_ave)
        e += rho_ave * (u * u_ave + v * v_ave + w * w_ave)

        return e

    def _calc_temperature(self, i_cell):
        # for temperature variation
        g1 = self._gamma

        rho = self[i_cell, 0]
        p = self[i_cell, 4]

        ave = self._ave_field.data
        rho_ave = ave[i_cell, 0]
        p_ave = ave[i_cell, 4]

        t = g1 * p / rho_ave
        t += g1 * p_ave * rho / (rho_ave * rho_ave)

        return t
