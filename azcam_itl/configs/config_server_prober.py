import os

import azcam
from azcam.header import System
from azcam.tools.archon.controller_archon import ControllerArchon
from azcam.tools.archon.exposure_archon import ExposureArchon

from azcam_itl.detectors import detector_sta4150_4amp, detector_sta4150_2amp_left

# ****************************************************************
# controller
# ****************************************************************
controller = ControllerArchon()
controller.camserver.port = 4242
controller.camserver.host = "10.0.2.13"  # prober Archon

# ****************************************************************
# exposure
# ****************************************************************
exposure = ExposureArchon()
exposure.fileconverter.set_detector_config(detector_sta4150_4amp)
filetype = "MEF"
exposure.filetype = exposure.filetypes[filetype]
exposure.image.filetype = exposure.filetypes[filetype]
exposure.add_extensions = 0
exposure.image.focalplane.gains = 4 * [2.8]
exposure.image.focalplane.rdnoises = 4 * [5.0]

tempcon = azcam.db.tools["tempcon"]
tempcon.control_temperature = +25.0
tempcon.temperature_ids = [3, 1]

# ****************************************************************
# system header
# ****************************************************************
template = os.path.join(azcam.db.datafolder, "templates", "fits_template_prober.txt")
system = System("Prober", template)

# ****************************************************************
# detector
# ****************************************************************
exposure.set_detpars(detector_sta4150_4amp)
