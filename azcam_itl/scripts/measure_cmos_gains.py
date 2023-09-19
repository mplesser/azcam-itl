from statistics import mean
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

import azcam
import azcam_console.plot


class MeasureCmosGains(object):
    """
    Get instrument pressures and plot.
    """

    def __init__(self) -> None:
        self.gains = {}

        self.ax = None
        self.lines = None
        self.delay = 0.0

        self.x_plot = []
        self.y_plot = []

        self.datafilename = "camera_gains.txt"

        plt.ion()

    def setup(self):
        """
        Setup plot and data output header.
        """

        self.fig, self.ax = azcam_console.plot.plt.subplots()
        self.fig.subplots_adjust(left=0.18, bottom=0.20, right=0.95, top=0.9)
        self.ax.grid(1)
        self.ax.xaxis.set_major_locator(MaxNLocator(20))

        plt.title("Measured System Gain")
        plt.ylabel("Gain [e/DN]")
        plt.xlabel("Camera Gain Setting")
        plt.xticks(rotation=45, ha="right")
        plt.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

        plt.ylim(0, 2)
        plt.xlim(0, 200)

        self.ax.plot([], [])

        data_txt_hdr = "Gain_Setting\tSystem_Gain"
        self.datafile = open(self.datafilename, "a+")
        self.datafile.write("# " + data_txt_hdr + "\n")

        azcam_console.plot.move_window(1, 100, 100)
        azcam_console.plot.update()

        return

    def measure(self, gain_settings: list):
        """
        Measure and record system gain.
        """

        self.setup()

        self.gains = {}
        self.x_plot = []
        self.y_plot = []

        for gain_setting in gain_settings:
            # set gain here
            azcam.log(f"Settin camera gain to {gain_setting}")
            azcam.db.tools["parameters"].set_par("cmos_gain", gain_setting)

            # measure gain
            try:
                azcam.db.tools["gain"].find()
                gains = azcam.db.tools["gain"].system_gain
            except Exception as e:
                print(e)
                return

            azcam.log(f"Measure gain [e/DN]: {gains}")
            self.gains[gain_setting] = gains

            s = f"{gain_setting}\t\t{[float(f'{g:1.2f}') for g in gains]}"

            if not self.datafile.closed:
                self.datafile.write(s + "\n")
            else:
                self.datafile = open(self.datafilename, "a+")
                self.datafile.write(s + "\n")

            self.y_plot.append(gains)
            self.x_plot.append(gain_setting)

            # self.ax.cla()
            self.ax.plot(self.x_plot, self.y_plot, "b.")

            azcam_console.plot.update()

        self.datafile.close()

        azcam_console.plot.plt.show()
        fignum = self.fig.number
        azcam_console.plot.save_figure(fignum, "camera_gains.png")

        return


def measure_cmos_gains(gain_settings: list = [1, 100]):
    """
    Measure CMOS gains.
    """

    measurecmosgains = MeasureCmosGains()
    measurecmosgains.measure(gain_settings)

    return measurecmosgains