import os
import sys
import time

from azcam_itl.detectors import detector_asi2600MM
from azcam_ascom.controller_ascom import ControllerASCOM
from azcam_ascom.exposure_ascom import ExposureASCOM
from azcam_ascom.tempcon_ascom import TempConASCOM

import azcam
from azcam.tools.system import System

# from azcam.tools.instrument import Instrument
from azcam_itl.instruments.instrument_qb import InstrumentQB
from azcam.tools.tempcon import TempCon
from azcam_ds9.ds9display import Ds9Display
from azcam_imageserver.sendimage import SendImage

# ****************************************************************
# controller
# ****************************************************************
controller = ControllerASCOM()
controller.driver = "ASCOM.ASICamera2.Camera"
# init now due to threading issue
try:
    controller.nx = 6248
    controller.ny = 4176
    controller.initialize()
    controller.camera.Gain = 100
    controller.camera.Offset = 1
except Exception as e:
    print(e)
    print("could not initialize camera")
    print("Gain:", azcam.db.tools["controller"].camera.Gain)
    print("Offset:", azcam.db.tools["controller"].camera.Offset)
    azcam.db.tools["controller"].nx = 6248
    azcam.db.tools["controller"].ny = 4176
    # azcam.db.tools["controller"].camera.Gain = 120
    # azcam.db.tools["controller"].camera.Offset = 10

"""
ZWO ASI2600MM data
self.camera.Offset = 10
self.camera.Gain = 120  # 0.20 e/DN, 1.4 e noise
self.camera.Gain = 100  # 0.25 e/DN, 1.6 e noise
self.camera.Gain = 80   # 0.32 e/DN, 3.6 e noise
self.camera.Gain = 60   # 0.40 e/DN, 3.5 e noise
self.camera.Gain = 20   # 0.60 e/DN, 3.5 e noise
"""

# ****************************************************************
# instrument
# ****************************************************************
# instrument = Instrument()
instrument = InstrumentQB()

# ****************************************************************
# temperature controller
# ****************************************************************
tempcon = TempConASCOM()
tempcon.control_temperature = -20
try:
    tempcon.initialize()
except Exception:
    pass

# ****************************************************************
# exposure
# ****************************************************************
exposure = ExposureASCOM()
filetype = "FITS"  # BIN FITS
exposure.filetype = exposure.filetypes[filetype]
exposure.image.filetype = exposure.filetypes[filetype]
exposure.image.filename = "/data/ASI2600MM/image.fits"  # .bin .fits

# ****************************************************************
# system header
# ****************************************************************
template = os.path.join(azcam.db.datafolder, "templates", "fits_template_ASI2600MM.txt")
system = System("ASI2600MM", template)

# ****************************************************************
# detector
# ****************************************************************
try:
    exposure.set_detpars(detector_asi2600MM)
except Exception:
    pass

# ****************************************************************
# define display
# ****************************************************************
display = Ds9Display()