#!/usr/bin/env python
# coding: utf-8
#
#    Project: Azimuthal integration
#             https://github.com/silx-kit/pyFAI
#
#    Copyright (C) 2015-2018 European Synchrotron Radiation Facility, Grenoble, France
#
#    Principal author:       Jérôme Kieffer (Jerome.Kieffer@ESRF.eu)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Dummy test to run first to check for relative imports
"""

__author__ = "Jérôme Kieffer"
__contact__ = "Jerome.Kieffer@ESRF.eu"
__license__ = "MIT"
__copyright__ = "European Synchrotron Radiation Facility, Grenoble, France"
__date__ = "12/07/2022"

import unittest
import sys
import logging
logger = logging.getLogger(__name__)
import numpy
from ..utils.mathutil import cormap
from ..detectors import Detector
from ..azimuthalIntegrator import AzimuthalIntegrator
from ..method_registry import IntegrationMethod


class TestErrorModel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestErrorModel, cls).setUpClass()
        #synthetic dataset
        pix = 100e-6
        shape = (256, 256)
        npt = 100
        wl = 1e-10
        I0 = 1e2
        flat = numpy.random.random(shape) + 1
        cls.kwargs = {"npt":npt,
         "correctSolidAngle":True,
         "polarization_factor":0.99,
         "safe":False,
         "error_model": "poisson",
         "method":("full", "csr", "cython"),
         "normalization_factor": 1e-6
         }
        detector = Detector(pix, pix)
        detector.shape = detector.max_shape = shape
        ai_init = {"dist":1.0,
           "poni1":0.0,
           "poni2":0.0,
           "rot1":-0.01,
           "rot2":+0.01,
           "rot3":0.0,
           "detector":detector,
           "wavelength":wl}
        cls.ai = AzimuthalIntegrator(**ai_init)
        # Generation of a "SAXS-like" curve with the shape of a lorentzian curve
        unit="q_nm^-1"
        q = numpy.linspace(0, cls.ai.array_from_unit(unit=unit).max(), npt)
        I = I0/(1+q**2)
        #Reconstruction of diffusion image:
        img_theo = cls.ai.calcfrom1d(q, I, dim1_unit="q_nm^-1",
                         correctSolidAngle=True,
                         polarization_factor=None,
                         flat=flat)
        cls.kwargs["flat"] = flat
        img = numpy.random.poisson(img_theo)
        cls.kwargs["data"] = img
          
        
    @classmethod
    def tearDownClass(cls):
        super(TestErrorModel, cls).tearDownClass()
        cls.ai = cls.npt = cls.kwargs = None 

    def test(self):
        epsilon = 1e-3 if sys.platform == "win32" else 1e-2
        results = {}
        for error_model in ("poisson", "azimuthal", "hybrid"):
            for impl in ("python", "cython", "opencl"):
                kw = self.kwargs.copy()
                kw["method"] = ("full", "csr", impl)
                kw["error_model"] = "poisson"
                results[error_model, impl, "integrate"] = self.ai.integrate1d_ng(**kw)
                try:
                    results[error_model, impl, "clip"] = self.ai.sigma_clip_ng(**kw)
                except RuntimeError as err:
                    logger.error(f"({error_model}, {impl}, 'clip') ended in RuntimError: probably bot implemented: {err}")
        # test integrate
        ref =  results[ "poisson", "python", "integrate"]
        for k in results:
            if k[2] == "integrate":
                res = results[k]
                if res is ref: 
                    continue 
                for array in ("count", "sum_signal", "sum_normalization", "sum_variance"): 
                    # print(k, array, cormap(ref.__getattribute__(array), res.__getattribute__(array)))
                    self.assertGreaterEqual(cormap(ref.__getattribute__(array), res.__getattribute__(array)), epsilon, f"array {array} matches for {k} vs numpy")
        # test clip
        ref =  results[ "poisson", "python", "clip"]
        for k in results:
            if k[2] == "clip":
                res = results[k]
                if res is ref: 
                    continue 
                for array in ("count", "sum_signal", "sum_normalization", "sum_variance"): 
                    # print(k, array, cormap(ref.__getattribute__(array), res.__getattribute__(array)))
                    self.assertGreaterEqual(cormap(ref.__getattribute__(array), res.__getattribute__(array)), epsilon, f"array {array} matches for {k} vs numpy")

        # raise 
def suite():
    testsuite = unittest.TestSuite()
    loader = unittest.defaultTestLoader.loadTestsFromTestCase
    testsuite.addTest(loader(TestErrorModel))
    return testsuite


if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())
