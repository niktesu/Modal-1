import os
import errno

import argparse
import configparser

from Functions.Mesh import OfMesh
from Functions.FieldData import OfData
from Functions.ModalAnalysis import ResolventMode as Resolvent
from Functions.ModalAnalysis import LinearStabilityMode as LSMode


def main(mode, param_file='Parameter.dat', profile='Default'):
    if not os.path.exists(param_file):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), param_file)

    if profile == 'Default':
        profile = mode + profile  # "StabilityDefault" or "ResolventDefault"

    profiles = configparser.ConfigParser()
    profiles.read(param_file, encoding='utf-8')
    params = profiles[profile]

    case_dir = params.get('CaseDir')
    time_dir = params.get('TimeDir')
    operator_name = params.get('Operator')
    save_name = params.get('SaveName')
    k = int(params.get('ModeNum'))

    if mode == 'Stability':
        sigma = params.get('Sigma')
        if sigma is not None:
            sigma = complex(sigma)
        which = params.get('Which')

        CalcStability(case_dir, time_dir, operator_name, save_name, k=k, sigma=sigma, which=which)

    elif mode == 'Resolvent':
        omega = float(params.get('Omega'))
        alpha = float(params.get('Alpha'))
        mode = params.get('ResolventMode')

        CalcResolvent(case_dir, time_dir, operator_name, save_name, k=k, omega=omega, alpha=alpha, mode=mode)


def CalcStability(case_dir, time, operator_name, save_name, k=3, sigma=None, which='LM'):
    mesh = OfMesh(case_dir, time + 'C', time + 'V', time + 'U', time + 'p')

    ls_mode = LSMode(mesh, operator_name, k=k)
    ls_mode.solve(sigma=sigma, which=which)
    ls_mode.save_data(save_name + '.pickle')
    ls_mode.vis_tecplot(save_name + '.dat')


def CalcResolvent(case_dir, time, operator_name, save_name, k=3, omega=0.0, alpha=0.0, mode=None):
    mesh = OfMesh(case_dir, time + 'C', time + 'V', time + 'U', time + 'p')
    ave_field = OfData(mesh, case_dir + time, 'UMean', 'pMean', 'rhoMean', add_e=True, add_temp=True)

    resolvent_mode = Resolvent(mesh, ave_field, operator_name, k=k, omega=omega, alpha=alpha, mode=mode)
    resolvent_mode.solve()
    resolvent_mode.save_data(save_name + '.pickle')
    resolvent_mode.vis_tecplot(save_name + '.dat')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Modal analysis.')

    parser.add_argument('mode', help='Calculation mode. "Stability" or "Resolvent"')
    parser.add_argument('-f', '--filename', default='Parameter.dat', help='Parameter file for the calculation.')
    parser.add_argument('-p', '--profile', default='Default', help='Profile for the parameters.')
    args = parser.parse_args()

    main(mode=args.mode, param_file=args.filename, profile=args.profile)