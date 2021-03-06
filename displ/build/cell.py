import os
import numpy as np
import ase.db

def get_layer_system(db, formula, phase):
    system_list = list(db.select('formula={},xc=PBE,phase={}'.format(formula, phase)))
    if len(system_list) > 1:
        # TODO - handle this better
        raise ValueError("found multiple matches for {}, PBE, {} phase".format(formula, phase))
    elif len(system_list) == 0:
        raise ValueError("found no matches for {}, PBE, {} phase".format(formula, phase))

    layer_system = system_list[0].toatoms()

    return layer_system

# Consistent ordering of lattice vectors and atoms for (Mo,W)(S,Se,Te)2 family.
def a_from_2H(layer_system):
    cell = layer_system.get_cell()
    a = cell[0][0]

    return a

def h_from_2H(layer_system):
    pos = layer_system.get_positions()
    c_S2 = pos[2][2]
    c_S1 = pos[1][2]
    
    return c_S2 - c_S1

def symbols_from_2H(layer_system):
    at_syms = layer_system.get_chemical_symbols()
    # Consistent M, X, X order.
    return at_syms[0], at_syms[1]

def make_cell(db, syms, c_sep, vacuum_dist, AB_stacking=True, layer_shifts=None):
    layer_systems = [get_layer_system(db, sym, 'H') for sym in syms]

    # Choose lattice constant from first layer.
    a = a_from_2H(layer_systems[0])

    hs = [h_from_2H(layer_system) for layer_system in layer_systems]

    # Setyawan and Curtarolo 2010 basis
    a1 = a * np.array([1/2, -float(np.sqrt(3)/2), 0.0])
    a2 = a * np.array([1/2, float(np.sqrt(3)/2), 0.0])
    latvecs_2D = np.array([a1[:2], a2[:2]]) # 2D part of D^T

    # Relative shifts of each layer. By default, do not shift.
    if layer_shifts is None:
        layer_shifts = [(0.0, 0.0)] * len(layer_systems)

    base_z, base_pos = 0.0, 'A'
    at_syms, cartpos = [], []
    for layer_system, h, layer_shift in zip(layer_systems, hs, layer_shifts):
        # Add [X, M, X] to list of atomic symbols.
        layer_M_sym, layer_X_sym = symbols_from_2H(layer_system)
        at_syms.extend([layer_X_sym, layer_M_sym, layer_X_sym])

        # z axis coordinates for this layer.
        X1_z = base_z
        M_z = base_z + h/2
        X2_z = base_z + h

        # Shift of this layer, if any.
        d_a, d_b = layer_shift

        # In-plane coordinates for this layer.
        if base_pos == 'A':
            X1_lat = np.array([(0.0 + d_a) % 1, (0.0 + d_b) % 1])
            M_lat = np.array([(1/3 + d_a) % 1, (2/3 + d_b) % 1])
            X2_lat = X1_lat
        else:
            X1_lat = np.array([(1/3 + d_a) % 1, (2/3 + d_b) % 1])
            M_lat = np.array([(0.0 + d_a) % 1, (0.0 + d_b) % 1])
            X2_lat = X1_lat

        layer_cartpos_2D = [np.dot(atpos_lat, latvecs_2D)
                for atpos_lat in [X1_lat, M_lat, X2_lat]]

        # 3D Cartesian coordinates for this layer.
        cartpos.extend([np.array([pos[0], pos[1], z_pos])
                for pos, z_pos in zip(layer_cartpos_2D, [X1_z, M_z, X2_z])])

        base_z += h + c_sep

        # Two stacking modes: AB (2H) and AA (1T).
        # In AB-stacking mode, alternate base_pos between TMD layers.
        # in AA-stacking mode, keep base_pos constant.
        if AB_stacking:
            if base_pos == 'A':
                base_pos = 'B'
            else:
                base_pos = 'A'

    # Assume atoms are given in order of z value.
    # TODO - enforce this?
    a3 = np.array([0.0, 0.0, cartpos[-1][2] + vacuum_dist])
    latvecs = np.array([a1, a2, a3])

    return latvecs, at_syms, cartpos
