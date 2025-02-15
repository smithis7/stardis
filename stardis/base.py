import os

import numpy as np

from tardis.io.atom_data import AtomData
from tardis.io.config_validator import validate_yaml, validate_dict
from tardis.io.config_reader import Configuration

from astropy import units as u

from stardis.model import read_marcs_to_fv
from stardis.plasma import create_stellar_plasma
from stardis.opacities import calc_alphas
from stardis.transport import raytrace


base_dir = os.path.abspath(os.path.dirname(__file__))
schema = os.path.join(base_dir, "config_schema.yml")


def run_stardis(config_fname, tracing_lambdas_or_nus):
    """
    Runs a STARDIS simulation.

    Parameters
    ----------
    config_fname : str
        Filepath to the STARDIS configuration. Must be a YAML file.
    tracing_lambdas_or_nus : astropy.units.Quantity
        Numpy array of the frequencies or wavelengths to calculate the
        spectrum for. Must have units attached to it, with dimensions
        of either length or inverse time.

    Returns
    -------
    stardis.base.STARDISOutput
        Contains all the key outputs of the STARDIS simulation.
    """

    tracing_lambdas = tracing_lambdas_or_nus.to(u.AA, u.spectral())
    tracing_nus = tracing_lambdas_or_nus.to(u.Hz, u.spectral())

    config_dict = validate_yaml(config_fname, schemapath=schema)
    config = Configuration(config_dict)

    adata = AtomData.from_hdf(config.atom_data)

    stellar_model = read_marcs_to_fv(
        config.model.fname, adata, final_atomic_number=config.model.final_atomic_number
    )
    adata.prepare_atom_data(stellar_model.abundances.index.tolist())

    stellar_plasma = create_stellar_plasma(stellar_model, adata)

    alphas, gammas, doppler_widths = calc_alphas(
        stellar_plasma=stellar_plasma,
        stellar_model=stellar_model,
        tracing_nus=tracing_nus,
        opacity_config=config.opacity,
    )

    F_nu = raytrace(
        stellar_model, alphas, tracing_nus, no_of_thetas=config.no_of_thetas
    )

    return STARDISOutput(
        stellar_plasma, stellar_model, alphas, gammas, doppler_widths, F_nu, tracing_nus
    )


class STARDISOutput:
    """
    Class containing all the key outputs of a STARDIS simulation.

    Parameters
    ----------
    stellar_plasma : tardis.plasma.base.BasePlasma
    stellar_model : stardis.model.base.StellarModel
    alphas : numpy.ndarray
    gammas : numpy.ndarray
    doppler_widths : numpy.ndarray
    F_nu : numpy.ndarray
    nus: astropy.units.Quantity

    Attributes
    ----------
    stellar_plasma : tardis.plasma.base.BasePlasma
    stellar_model : stardis.model.base.StellarModel
    alphas : numpy.ndarray
        Array of shape (no_of_shells, no_of_frequencies). Total opacity in
        each shell for each frequency in tracing_nus.
    gammas : numpy.ndarray
        Array of shape (no_of_lines, no_of_shells). Collisional broadening
        parameter of each line in each shell.
    doppler_widths : numpy.ndarray
        Array of shape (no_of_lines, no_of_shells). Doppler width of each
        line in each shell.
    F_nu : numpy.ndarray
        Array of shape (no_of_shells + 1, no_of_frequencies). Output flux with
        respect to frequency at each shell boundary for each frequency.
    F_lambda : numpy.ndarray
        Array of shape (no_of_shells + 1, no_of_frequencies). Output flux with
        respect to wavelength at each shell boundary for each wavelength.
    spectrum_nu : numpy.ndarray
        Output flux with respect to frequency at the outer boundary for each
        frequency.
    spectrum_lambda : numpy.ndarray
        Output flux with respect to wavelength at the outer boundary for each
        wavelength.
    nus : astropy.units.Quantity
        Numpy array of frequencies used for spectrum with units of Hz.
    lambdas : astropy.units.Quantity
        Numpy array of wavelengths used for spectrum with units of Angstroms.
    """

    def __init__(
        self, stellar_plasma, stellar_model, alphas, gammas, doppler_widths, F_nu, nus
    ):

        self.stellar_plasma = stellar_plasma
        self.stellar_model = stellar_model
        self.alphas = alphas
        self.gammas = gammas
        self.doppler_widths = doppler_widths

        length = len(F_nu)
        lambdas = nus.to(u.AA, u.spectral())
        F_lambda = F_nu * nus / lambdas
        # TODO: Units
        self.F_nu = F_nu
        self.F_lambda = F_lambda.value
        self.spectrum_nu = F_nu[length - 1]
        self.spectrum_lambda = F_lambda[length - 1]
        self.nus = nus
        self.lambdas = lambdas
