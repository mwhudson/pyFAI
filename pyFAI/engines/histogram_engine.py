#
#    Copyright (C) 2019-2022 European Synchrotron Radiation Facility, Grenoble, France
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#  .
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#  .
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#  THE SOFTWARE.

"""simple histogram rebinning engine implemented in pure python (with the help of numpy !) 
"""

__author__ = "Jerome Kieffer"
__contact__ = "Jerome.Kieffer@ESRF.eu"
__license__ = "MIT"
__copyright__ = "European Synchrotron Radiation Facility, Grenoble, France"
__date__ = "29/06/2022"
__status__ = "development"

import logging
logger = logging.getLogger(__name__)
import numpy
from ..utils import EPS32
from .preproc import preproc as preproc_np
try:
    from ..ext.preproc import preproc as preproc_cy
except ImportError as err:
    logger.warning("ImportError pyFAI.ext.preproc %s", err)
    preproc = preproc_np
else:
    preproc = preproc_cy

from ..containers import Integrate1dtpl, Integrate2dtpl, ErrorModel


def histogram1d_engine(radial, npt,
                       raw,
                       dark=None,
                       flat=None,
                       solidangle=None,
                       polarization=None,
                       absorption=None,
                       mask=None,
                       dummy=None,
                       delta_dummy=None,
                       normalization_factor=1.0,
                       empty=None,
                       split_result=False,
                       variance=None,
                       dark_variance=None,
                       error_model=ErrorModel.NO, 
                       radial_range=None
                       ):
    """Implementation of rebinning engine using pure numpy histograms
    
    :param radial: radial position 2D array (same shape as raw)   
    :param npt: number of points to integrate over
    :param raw: 2D array with the raw signal
    :param dark: array containing the value of the dark noise, to be subtracted
    :param flat: Array containing the flatfield image. It is also checked for dummies if relevant.
    :param solidangle: the value of the solid_angle. This processing may be performed during the rebinning instead. left for compatibility
    :param polarization: Correction for polarization of the incident beam
    :param absorption: Correction for absorption in the sensor volume
    :param mask: 2d array of int/bool: non-null where data should be ignored
    :param dummy: value of invalid data
    :param delta_dummy: precision for invalid data
    :param normalization_factor: final value is divided by this
    :param empty: value to be given for empty bins
    :param variance: provide an estimation of the variance
    :param dark_variance: provide an estimation of the variance of the dark_current,
    :param error_model: Use the provided ErrorModel, only "poisson" and "variance" is valid 


    NaN are always considered as invalid values

    if neither empty nor dummy is provided, empty pixels are left at 0.
    
    Nota: "azimuthal_range" has to be integrated into the 
           mask prior to the call of this function 
    
    :return: Integrate1dtpl named tuple containing: 
            position, average intensity, std on intensity, 
            plus the various histograms on signal, variance, normalization and count.  
                                               
    """
    prep = preproc(raw,
                   dark=dark,
                   flat=flat,
                   solidangle=solidangle,
                   polarization=polarization,
                   absorption=absorption,
                   mask=mask,
                   dummy=dummy,
                   delta_dummy=delta_dummy,
                   normalization_factor=normalization_factor,
                   split_result=4,
                   variance=variance,
                   dark_variance=dark_variance,
                   error_model=error_model,
                   empty=0
                   )
    radial = radial.ravel()
    prep.shape = -1, 4
    assert prep.shape[0] == radial.size
    if radial_range is None:
        radial_range = (radial.min(), radial.max() * EPS32)

    histo_signal, _ = numpy.histogram(radial, npt, weights=prep[:, 0], range=radial_range)
    if error_model == ErrorModel.AZIMUTHAL:
        raise NotImplementedError("Numpy histogram are not able to assess variance in azimuthal bins")
    elif error_model: #Variance, Poisson and Hybrid
        histo_variance, _ = numpy.histogram(radial, npt, weights=prep[:, 1], range=radial_range)
        histo_normalization2, _ = numpy.histogram(radial, npt, weights=prep[:, 2]**2, range=radial_range)
    else: # No error propagated
        histo_variance = None
        histo_normalization2 = None
    histo_normalization, _ = numpy.histogram(radial, npt, weights=prep[:, 2], range=radial_range)
    histo_count, position = numpy.histogram(radial, npt, weights=prep[:, 3], range=radial_range)
    positions = (position[1:] + position[:-1]) / 2.0

    mask_empty = histo_count == 0
    if dummy is not None:
        empty = dummy
    with numpy.errstate(divide='ignore', invalid='ignore'):
        intensity = histo_signal / histo_normalization
        intensity[mask_empty] = empty
        if histo_variance is None:
            std = sem = None
        else:
            std = numpy.sqrt(histo_variance / histo_normalization2)
            sem = numpy.sqrt(histo_variance) / histo_normalization
            std[mask_empty] = empty
            sem[mask_empty] = empty
    return Integrate1dtpl(positions, intensity, sem, histo_signal, histo_variance, histo_normalization, histo_count,
                          std, sem, histo_normalization2)


def histogram2d_engine(radial, azimuthal, npt,
                       raw,
                       dark=None,
                       flat=None,
                       solidangle=None,
                       polarization=None,
                       absorption=None,
                       mask=None,
                       dummy=None,
                       delta_dummy=None,
                       normalization_factor=1.0,
                       empty=None,
                       split_result=False,
                       variance=None,
                       dark_variance=None,
                       error_model=ErrorModel.NO,
                       radial_range=None,
                       azimuth_range=None
                       ):
    """Implementation of 2D rebinning engine using pure numpy histograms
    
    :param radial: radial position 2D array (same shape as raw)
    :param azimuthal: azimuthal position 2D array (same shape as raw)
    :param npt: number of points to integrate over in (radial, azimuthal) dimensions
    :param raw: 2D array with the raw signal
    :param dark: array containing the value of the dark noise, to be subtracted
    :param flat: Array containing the flatfield image. It is also checked for dummies if relevant.
    :param solidangle: the value of the solid_angle. This processing may be performed during the rebinning instead. left for compatibility
    :param polarization: Correction for polarization of the incident beam
    :param absorption: Correction for absorption in the sensor volume
    :param mask: 2d array of int/bool: non-null where data should be ignored
    :param dummy: value of invalid data
    :param delta_dummy: precision for invalid data
    :param normalization_factor: final value is divided by this
    :param empty: value to be given for empty bins
    :param variance: provide an estimation of the variance
    :param dark_variance: provide an estimation of the variance of the dark_current,
    :param error_model: set to "poisson" for assuming the detector is poissonian and variance = raw + dark


    NaN are always considered as invalid values

    if neither empty nor dummy is provided, empty pixels are left at 0.
    
    Nota: "azimuthal_range" has to be integrated into the 
           mask prior to the call of this function 
    
    :return: Integrate1dtpl named tuple containing: 
            position, average intensity, std on intensity, 
            plus the various histograms on signal, variance, normalization and count.  
                                               
    """
    prep = preproc(raw,
                   dark=dark,
                   flat=flat,
                   solidangle=solidangle,
                   polarization=polarization,
                   absorption=absorption,
                   mask=mask,
                   dummy=dummy,
                   delta_dummy=delta_dummy,
                   normalization_factor=normalization_factor,
                   split_result=4,
                   variance=variance,
                   dark_variance=dark_variance,
                   error_model=error_model,
                   empty=0
                   )
    radial = radial.ravel()
    azimuthal = azimuthal.ravel()
    prep.shape = -1, 4
    assert prep.shape[0] == radial.size
    assert prep.shape[0] == azimuthal.size
    npt = tuple(max(1, i) for i in npt)
    rng = [radial_range, azimuth_range]
    histo_signal, _, _ = numpy.histogram2d(radial, azimuthal, npt, weights=prep[:, 0], range=rng)
    histo_normalization, _, _ = numpy.histogram2d(radial, azimuthal, npt, weights=prep[:, 2], range=rng)
    histo_count, position_rad, position_azim = numpy.histogram2d(radial, azimuthal, npt, weights=prep[:, 3], range=rng)

    histo_signal = histo_signal.T
    histo_normalization = histo_normalization.T
    histo_count = histo_count.T
    if error_model:
        histo_variance, _, _ = numpy.histogram2d(radial, azimuthal, npt, weights=prep[:, 1], range=rng)
        histo_variance = histo_variance.T
    else:
        histo_variance = None

    bins_azim = 0.5 * (position_azim[1:] + position_azim[:-1])
    bins_rad = 0.5 * (position_rad[1:] + position_rad[:-1])

    with numpy.errstate(divide='ignore', invalid='ignore'):
        intensity = histo_signal / histo_normalization
        if histo_variance is None:
            error = None
        else:
            error = numpy.sqrt(histo_variance) / histo_normalization
    mask_empty = histo_count == 0
    if dummy is not None:
        empty = dummy
    intensity[mask_empty] = empty
    if error is not None:
        error[mask_empty] = empty
        error = error
    return Integrate2dtpl(bins_rad, bins_azim, intensity, error, histo_signal, histo_variance, histo_normalization, histo_count)
