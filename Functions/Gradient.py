from itertools import product

import numpy as np
from scipy import linalg

from Variables import Variables


class Gradient(Variables):
    def __init__(self, mesh, flow_data, bd_cond, sub_list=None):
        super(Gradient, self).__init__(mesh, flow_data, sub_list)

        self.bd_cond = bd_cond

        # Least Square matrix
        n_cell = mesh.n_cell
        self.matLU1 = np.zeros((n_cell, 3, 3), dtype=np.float64)
        self.matLU2 = np.zeros((n_cell, 3), dtype=np.float64)
        self._set_left_mat()

    def return_ref_cells(self, id_cell):
        cell_list = [id_cell] + self.mesh.cell_neighbours(id_cell)
        ref_cells = [i_cell for i_cell in cell_list if i_cell >= 0]

        return list(set(ref_cells))

    def formula(self, data, id_cell, id_val, axis=None):
        vec_rhs = self._set_rhs(data, id_cell, id_val)
        grad = linalg.lu_solve(self.matLU1[id_cell], self.matLU2[id_cell], vec_rhs)

        if axis is not None:
            return grad[axis]
        else:
            return grad

    def _set_left_mat(self):
        n_cell = self.mesh.n_cell
        # n_face = self.mesh.n_face

        for id_cell in range(n_cell):
            matA = self._set_left_mat_by_cell(id_cell)
            self.matLU1[id_cell], self.matLU2[id_cell] = linalg.lu_factor(matA)

    def _set_left_mat_by_cell(self, id_cell):
        # Left side matrix for the least square method.
        nb_cells = self.mesh.cell_neighbours(id_cell)
        faces = self.mesh.cell_faces[id_cell]

        mat_cell = np.zeros((3, 3), dtype=np.float64)
        for id_nb, id_face in zip(nb_cells, faces):
            vec_lr = self._get_pos_diff(id_cell, id_nb, id_face)

            for axis_0, axis_k in product(range(3), range(3)):
                mat_cell += vec_lr[axis_0] * vec_lr[axis_k]

        return mat_cell

    def _get_pos_diff(self, id_0, id_k, id_k_face):
        centers = self.mesh.centers

        if id_k >= 0:  # For inner cells
            vec_lr = centers[id_k] - centers[id_0]
        else:  # For boundary cells
            face_vec_n = self.mesh.face_vec_n
            face_centers = self.mesh.face_centers

            vec_n = face_vec_n[id_k_face]
            dist_fc = np.linalg.norm(face_centers[id_k_face] - centers[id_0])

            vec_lr = 2.0 * vec_n * np.tile(dist_fc, 3)

        return vec_lr

    def _set_rhs(self, data, id_cell, id_val):
        nb_cells = self.mesh.cell_neighbours(id_cell)
        faces = self.mesh.cell_faces[id_cell]

        rhs_vec = np.zeros(3, np.float64)
        for id_nb, id_face in zip(nb_cells, faces):
            vec_lr = self._get_pos_diff(id_cell, id_nb, id_face)
            val_diff = self._get_val_diff(data, id_cell, id_nb, id_face, id_val)

            rhs_vec += vec_lr * np.tile(val_diff, 3)

        return rhs_vec

    def _get_val_diff(self, data, id_0, id_k, id_k_face, id_val):
        if id_k >= 0:  # For inner cells
            val_0 = data[id_0, id_val]
            val_k = data[id_k, id_val]

            val_diff = val_k - val_0
        else:  # For boundary cells
            val_vec = data[id_0]
            id_bd = id_k

            val_bd = self.bd_cond.get_bd_val(val_vec, id_k_face, id_bd)

            val_diff = val_bd[id_val] - val_vec[id_val]

        return val_diff
