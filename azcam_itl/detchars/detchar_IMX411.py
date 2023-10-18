import datetime
import fnmatch
import ftplib
import glob
import os
import re
import shutil
import subprocess
import time

import keyring

import azcam
import azcam_console
from azcam_console.tools.testers.detchar import DetChar
from azcam_itl import itlutils


class IMX411DetChar(DetChar):
    def __init__(self):
        super().__init__()

        self.imsnap_scale = 1.0
        self.start_temperature = -10.0

        self.operator = "Lesser"
        self.itl_sn = -1

        self.system = ""
        self.customer = ""

        self.report_date = ""
        self.report_id = ""
        self.report_comment = ""

        self.start_delay = 5

        # report parameters
        self.create_html = 1
        self.report_file = ""
        self.summary_report_file = ""
        self.report_names = [
            "bias",
            "gain",
            "prnu",
            "ptc",
            "linearity",
            "qe",
            "dark",
            "defects",
        ]
        self.report_files = {
            "bias": "bias/bias",
            "gain": "gain/gain",
            "prnu": "prnu/prnu",
            "ptc": "ptc/ptc",
            "linearity": "ptc/linearity",
            "qe": "qe/qe",
            "dark": "dark/dark",
            "defects": "defects/defects",
        }

    def acquire(self, itlsn="unknown"):
        """
        Acquire sensor characterization data.
        """

        print("Starting acquisition sequence")
        print("")

        if not self.is_setup:
            self.setup(itlsn)

        (
            gain,
            bias,
            detcal,
            superflat,
            ptc,
            qe,
            dark,
            defects,
            dark,
        ) = azcam_console.utils.get_tools(
            [
                "gain",
                "bias",
                "detcal",
                "superflat",
                "ptc",
                "qe",
                "dark",
                "defects",
                "dark",
            ]
        )
        exposure, tempcon = azcam_console.utils.get_tools(
            [
                "exposure",
                "tempcon",
            ]
        )

        # *************************************************************************
        # wait for temperature
        # *************************************************************************
        if self.start_temperature != -1000:
            while True:
                t = tempcon.get_temperatures()[0]
                print("Current temperature: %.1f" % t)
                if t <= self.start_temperature + 0.5:
                    break
                else:
                    time.sleep(10)

        print(f"Testing device {itlsn}")

        # *************************************************************************
        # save current image parameters
        # *************************************************************************
        impars = {}
        azcam.db.parameters.save_imagepars(impars)

        # *************************************************************************
        # read most recent detcal info
        # *************************************************************************
        detcal.read_datafile(detcal.data_file)
        detcal.mean_electrons = {int(k): v for k, v in detcal.mean_electrons.items()}
        detcal.mean_counts = {int(k): v for k, v in detcal.mean_counts.items()}

        # *************************************************************************
        # Create and move to a report folder
        # *************************************************************************
        currentfolder, reportfolder = azcam_console.utils.make_file_folder(
            "report", 1, 1
        )  # start with report1
        azcam.utils.curdir(reportfolder)

        # *************************************************************************
        # Acquire data
        # *************************************************************************
        azcam.db.parameters.set_par("imagesequencenumber", 1)  # uniform image sequence numbers

        try:
            # reset camera
            print("Reset and Flush sensor")
            exposure.reset()
            exposure.roi_reset()
            exposure.test(0)  # flush

            # clear device after reset delay
            print("Delaying start for %.0f seconds (to settle)..." % self.start_delay)
            time.sleep(self.start_delay)
            exposure.test(0)  # flush

            # bias images
            bias.acquire()
            itlutils.imsnap(self.imsnap_scale, "last")

            # gain images
            # gain.find()
            gain.acquire()

            # Prnu images
            azcam.db.tools["prnu"].acquire()

            # superflat sequence
            superflat.acquire()

            # PTC and linearity
            ptc.acquire()

            # QE
            qe.acquire()

            if 0:
                # Dark signal
                exposure.test(0)
                dark.acquire()
            else:
                print("Close shutter and run dark.acquire()")

        finally:
            azcam.db.parameters.restore_imagepars(impars)
            azcam.utils.curdir(currentfolder)

        print("acquire sequence finished")

        return

    def analyze(self, report_id="unknown"):
        """
        Analyze data.
        """

        rootfolder = azcam.utils.curdir()

        (
            exposure,
            gain,
            bias,
            detcal,
            superflat,
            ptc,
            qe,
            dark,
            defects,
            linearity,
        ) = azcam_console.utils.get_tools(
            [
                "exposure",
                "gain",
                "bias",
                "detcal",
                "superflat",
                "ptc",
                "qe",
                "dark",
                "defects",
                "linearity",
            ]
        )

        if not self.is_setup:
            self.setup(report_id)

        # analyze bias
        azcam.utils.curdir("bias")
        bias.analyze()
        azcam.utils.curdir(rootfolder)
        print("")

        # analyze gain
        azcam.utils.curdir("gain")
        gain.analyze()
        azcam.utils.curdir(rootfolder)
        print("")

        # analyze superflats
        azcam.utils.curdir("superflat1")
        superflat.analyze()
        azcam.utils.curdir(rootfolder)
        print("")

        # analyze PTC
        azcam.utils.curdir("ptc")
        ptc.analyze()
        azcam.utils.curdir(rootfolder)
        print("")

        # analyze linearity from PTC data
        azcam.utils.curdir("ptc")
        linearity.analyze()
        azcam.utils.curdir(rootfolder)
        print("")

        # analyze darks
        azcam.utils.curdir("dark")
        dark.analyze()
        azcam.utils.curdir(rootfolder)
        print("")

        # analyze defects
        defects.dark_filename = dark.dark_filename
        azcam.utils.curdir("dark")
        defects.analyze_bright_defects()
        defects.copy_data_files()
        azcam.utils.curdir(rootfolder)

        defects.flat_filename = superflat.superflat_filename
        azcam.utils.curdir("superflat1")
        defects.analyze_dark_defects()
        defects.copy_data_files()
        azcam.utils.curdir(rootfolder)

        azcam.utils.curdir("defects")
        azcam.db.tools["defects"].analyze()
        azcam.utils.curdir(rootfolder)
        print("")

        # analyze qe
        azcam.utils.curdir("qe")
        azcam.db.tools["qe"].analyze()
        azcam.utils.curdir(rootfolder)
        print("")

        # analyze prnu
        azcam.utils.curdir("prnu")
        azcam.db.tools["prnu"].analyze()
        azcam.utils.curdir(rootfolder)
        print("")

        # make report
        self.report_summary()
        self.report()

        return

    def report(self):
        """
        Make sensor characterization report.
        Run setup() first.
        """

        if not self.is_setup:
            self.setup()

        folder = azcam.utils.curdir()
        self.report_folder = folder
        report_name = f"ASI6200MM_report_{self.report_id}.pdf"

        print("")
        print(f"Generating report for {self.report_id}")
        print("")

        # *********************************************
        # Combine PDF report files for each tool
        # *********************************************
        rfiles = [self.summary_report_file + ".pdf"]
        for r in self.report_names:  # add pdf extension
            f1 = self.report_files[r] + ".pdf"
            f1 = os.path.abspath(f1)
            if os.path.exists(f1):
                rfiles.append(f1)
            else:
                print("Report file not found: %s" % f1)
        self.merge_pdf(rfiles, report_name)

        # open report
        with open(os.devnull, "w") as fnull:
            s = "%s" % self.report_file
            subprocess.Popen(s, shell=True, cwd=folder, stdout=fnull, stderr=fnull)
            fnull.close()

        return

    def report_summary(self):
        """
        Create a ID and summary report.
        """
        # get current date
        self.report_date = datetime.datetime.now().strftime("%b-%d-%Y")

        lines = []

        lines.append("# ITL Sensor Characterization Report")
        lines.append("")
        lines.append("|||")
        lines.append("|:---|:---|")
        lines.append("|**Identification**||")
        lines.append(f"|Customer       |UArizona|")
        lines.append(f"|Project        |Oracle Search Sensor-1|")
        lines.append(f"|System         |Sony IMX455|")
        lines.append(f"|Camera SN      |{self.itl_sn}|")
        lines.append(f"|Report ID      |{self.report_id}|")
        lines.append(f"|Report Date    |{self.report_date}|")
        lines.append(f"|Author         |{self.operator}|")
        lines.append("")

        # add superflat image
        f1 = os.path.abspath("./superflat1/superflatimage.png")
        s = f"<img src={f1} width=350>"
        lines.append(s)
        # lines.append(f"![Superflat Image]({os.path.abspath('./superflat1/superflatimage.png')})  ")
        lines.append("")
        lines.append("*Superflat Image.*")
        # lines.append("")

        # Make report files
        self.write_report(self.summary_report_file, lines)

        return

    def copy_files(self):
        """
        Copy both report and flats
        """

        # azcam.utils.curdir("..")
        itlutils.cleanup_files()
        self.copy_reports()
        self.copy_flats()

        return

    def copy_flats(self):
        """
        Find all qe.0004 flat field files from current folder tree and copy them to
        the folder two levels up (run from report) with new name.
        Rather dumb, needs 5 digit SN for now...
        """

        folder = azcam.utils.curdir()
        dest_folder = azcam.utils.curdir()
        azcam.utils.curdir(folder)
        matches = []
        for root, dirnames, filenames in os.walk(folder):
            for filename in fnmatch.filter(filenames, "qe.0004.fits"):
                matches.append(os.path.join(root, filename))

        for t in matches:
            match = re.search("sn", t)
            if match is not None:
                start = match.start()
                sn = t[start : start + 7]
                print("Found: ", t)
                print("Press y or enter to copy this file...")
                key = azcam.utils.check_keyboard(1)
                if key == "y" or key == "\r":
                    print()
                    shutil.copy(t, os.path.join(dest_folder, "%s_flat.fits" % (sn)))
                else:
                    print("File not copied")

        return

    def copy_reports(self):
        """
        Find all qe.0004 flat field files from current folder tree and copy them to
        the folder two levels up (run from report) with new name.
        Rather dumb, needs 5 digit SN for now...
        """

        folder = azcam.utils.curdir()
        dest_folder = azcam.utils.curdir()
        azcam.utils.curdir(folder)
        matches = []
        for root, dirnames, filenames in os.walk(folder):
            for filename in fnmatch.filter(filenames, "ASI6200MM_Report_*.pdf"):
                matches.append(os.path.join(root, filename))

        for t in matches:
            print("Found: ", t)
            print("Press y or enter to copy this file...")
            key = azcam.utils.check_keyboard(1)
            if key == "y" or key == "\r":
                shutil.copy(t, dest_folder)
            else:
                print("File not copied")

        return

    def setup(self, report_id=None):
        self.report_id = azcam.utils.prompt("Enter report ID", report_id)

        # sponsor/report info
        self.customer = "UArizona"
        self.system = "ASI6200MM"
        self.itl_sn = "361d940d2d010900"
        qe.plot_title = "ASI6200MM Quantum Efficiency"
        self.summary_report_file = f"SummaryReport_{self.report_id}"
        self.report_file = f"ASI6200MM{self.report_id}.pdf"

        self.is_setup = 1

        return

    def upload_prep(self, shipdate: str):
        """
        Prepare a dataset for upload by creating an archive file.
        file.  Start in the _shipment folder.
        """

        startdir = azcam.utils.curdir()
        shipdate = os.path.basename(startdir)
        idstring = f"{shipdate}"

        # cleanup folder
        azcam.log("cleaning dataset folder")
        itlutils.cleanup_files()

        # move one folder above report folder
        # azcam.utils.curdir(reportfolder)
        # azcam.utils.curdir("..")

        self.copy_files()

        # copy files to new folder and archive
        azcam.log(f"copying dataset to {idstring}")
        currentfolder, newfolder = azcam_console.utils.make_file_folder(idstring)

        copy_files = glob.glob("*.pdf")
        for f in copy_files:
            shutil.move(f, newfolder)
        copy_files = glob.glob("*.fits")
        for f in copy_files:
            shutil.move(f, newfolder)
        copy_files = glob.glob("*.csv")
        for f in copy_files:
            shutil.move(f, newfolder)

        azcam.utils.curdir(newfolder)

        # make archive file
        azcam.utils.curdir(currentfolder)
        azcam.log("making archive file")
        archivefile = itlutils.archive(idstring, "zip")
        shutil.move(archivefile, newfolder)

        # delete data files from new folder
        azcam.utils.curdir(newfolder)
        [os.remove(x) for x in glob.glob("*.pdf")]
        [os.remove(x) for x in glob.glob("*.fits")]
        [os.remove(x) for x in glob.glob("*.csv")]

        azcam.utils.curdir(startdir)

        self.remote_upload_folder = idstring

        return archivefile


# create instance
detchar = IMX411DetChar()

(
    exposure,
    gain,
    bias,
    detcal,
    superflat,
    ptc,
    qe,
    dark,
    defects,
    linearity,
    prnu,
) = azcam_console.utils.get_tools(
    [
        "exposure",
        "gain",
        "bias",
        "detcal",
        "superflat",
        "ptc",
        "qe",
        "dark",
        "defects",
        "linearity",
        "prnu",
    ]
)

detchar.start_temperature = +10.0
# ***********************************************************************************
# parameters
# ***********************************************************************************
# azcam_console.utils.set_image_roi([[4000, 4100, 3000, 3100], [4000, 4100, 3000, 3100]])
azcam_console.utils.set_image_roi([[1000, 1100, 1000, 1100], [1000, 1100, 1000, 1100]])

# detcal
detcal.wavelengths = [
    350,
    400,
    450,
    500,
    550,
    600,
    650,
    700,
    750,
    800,
    850,
    900,
    950,
    1000,
]
# values below estimates for unbinned values, 5000 DN, gain=1, 0.8 e/DN
ref_gain = 0.8  # reference gain used for dict below
new_gain = 1.0  # for other settings
scale = ref_gain / new_gain
detcal.exposure_times = {
    350: 220.0 * scale,
    400: 14.0 * scale,
    450: 10.0 * scale,
    500: 8.7 * scale,
    550: 12.2 * scale,
    600: 12.6 * scale,
    650: 23.2 * scale,
    700: 40.0 * scale,
    750: 72.3 * scale,
    800: 157.0 * scale,
    850: 103.0 * scale,
    900: 122.0 * scale,
    950: 243.0 * scale,
    1000: 453.0 * scale,
}
detcal.data_file = os.path.join(azcam.db.datafolder, "detcal_asi6200mm.txt")
detcal.mean_count_goal = 5000
detcal.range_factor = 1.3

# bias
bias.number_images_acquire = 10
bias.overscan_correct = 0

# gain
gain.number_pairs = 1
gain.exposure_time = 5.0
gain.wavelength = 500
gain.video_processor_gain = []

# dark
dark.number_images_acquire = 3
dark.exposure_time = 600.0
dark.dark_fraction = -1  # no spec on individual pixels
dark.use_edge_mask = 0
dark.bright_pixel_reject = 20.0 / 3600 * 10  # clip, 10x mean dark current [e/pix/sec]
dark.overscan_correct = 0  # flag to overscan correct images
dark.zero_correct = 0  # flag to correct with bias residuals
dark.fit_order = 0
dark.report_dark_per_hour = 1  # report per hour

# superflats
superflat.exposure_levels = [20000]  # electrons
superflat.wavelength = 500
superflat.number_images_acquire = [3]
superflat.zero_correct = 0
superflat.overscan_correct = 0

# ptc
ptc.wavelength = 500
ptc.gain_range = [0.4, 1.2]
ptc.overscan_correct = 0
ptc.zero_correct = 1
ptc.fit_line = True
ptc.fullwell_estimate = 54000 / 0.8  # counts
ptc.fit_min = ptc.fullwell_estimate * 0.10
ptc.fit_max = ptc.fullwell_estimate * 0.90

ptc.exposure_times = []
# ptc.max_exposures = 40
# ptc.number_images_acquire = 40
ptc.exposure_levels = [
    500,
    1000,
    1500,
    2000,
    2500,
    3000,
    3500,
    4000,
    4500,
    5000,
    5500,
    6000,
    6500,
    7000,
    8000,
    9000,
    10000,
    15000,
    20000,
    25000,
    30000,
    35000,
    40000,
    45000,
    50000,
    55000,
    60000,
    63000,
]

# linearity
linearity.wavelength = 500
linearity.use_ptc_data = 1
linearity.fullwell_estimate = 54000 / 0.8  # counts
linearity.fit_all_data = 0
linearity.fit_min = 0.05
linearity.fit_max = 0.90  # .95 too close to ADC limit

linearity.max_allowed_linearity = -1
linearity.plot_specifications = 1
linearity.plot_limits = [-4.0, +4.0]
linearity.overscan_correct = 0
linearity.zero_correct = 1
linearity.use_weights = 1

# QE
qe.cal_scale = 0.985
qe.global_scale = 1.0
qe.pixel_area = 0.00376**2
qe.flux_cal_folder = "/data/IMX411"
qe.plot_limits = [[300.0, 1000.0], [0.0, 100.0]]
qe.plot_title = "IMX411 Quantum Efficiency"
qe.qeroi = []
qe.overscan_correct = 0
qe.zero_correct = 1
qe.flush_before_exposure = 0
qe.grade_sensor = 0
qe.create_reports = 1
qe.use_exposure_levels = 1
qe.exptime_offset = 0.00
el = 5000.0
qe.exposure_levels = {
    350: el,
    400: el,
    450: el,
    500: el,
    550: el,
    600: el,
    650: el,
    700: el,
    750: el,
    800: el,
    850: el,
    900: el,
    950: el,
    1000: el,
}
if 1:
    qe.window_trans = {
        300: 1.0,
        1000: 1.0,
    }
else:
    # from online plot
    qe.window_trans = {
        350: 0.25,
        400: 0.95,
        450: 0.99,
        500: 0.99,
        550: 0.99,
        600: 0.99,
        650: 0.99,
        700: 0.95,
        750: 0.93,
        800: 0.90,
        850: 0.85,
        950: 0.78,
        1000: 0.75,
    }

# prnu
prnu.root_name = "prnu."
prnu.use_edge_mask = 0
prnu.overscan_correct = 0
prnu.zero_correct = 1
el = 5000.0
prnu.exposure_levels = {
    350: el,
    400: el,
    450: el,
    500: el,
    550: el,
    600: el,
    650: el,
    700: el,
    750: el,
    800: el,
    850: el,
    900: el,
    950: el,
    1000: el,
}
prnu.mean_count_goal = 5000.0

# defects
defects.use_edge_mask = 0
defects.bright_pixel_reject = 20.0 / 3600 * 10  # 10x mean dark current [e/pix/sec]
defects.dark_pixel_reject = 0.80  # below mean