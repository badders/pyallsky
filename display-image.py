from allsky import AllSkyCamera
import matplotlib
matplotlib.use('Qt4Agg')

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import aplpy

import sys
from PyQt4 import QtGui, uic

from collections import OrderedDict

class QtMatplotlibGraph(FigureCanvasQTAgg):
    def __init__(self):
        self._fig = Figure(dpi=96)
        FigureCanvasQTAgg.__init__(self, self._fig)
        FigureCanvasQTAgg.setSizePolicy(self,
                                        QtGui.QSizePolicy.Expanding,
                                        QtGui.QSizePolicy.Expanding)
        self._fig.set_facecolor('white')

    def _layoutChange(self):
        try:
            self._fig.tight_layout()
        except ValueError:
            pass  # Discard matplotlib errors for very small graphs

    def resizeEvent(self, re):
        FigureCanvasQTAgg.resizeEvent(self, re)
        self._layoutChange()

class FitsView(QtMatplotlibGraph):
    def __init__(self):
        QtMatplotlibGraph.__init__(self)
        self.__taking = False
        self._scale = 'linear'
        self.scales = OrderedDict()
        self.scales['Linear'] =  'linear'
        self.scales['Square Root'] = 'sqrt'
        self.scales['Power'] = 'power'
        self.scales['Logarithmic'] = 'log'
        self.scales['Arc Sinh'] = 'arcsinh'
        self.gc = None
        self.cuts = 99.75

    def setImage(self, filename):
        self.gc = aplpy.FITSFigure(filename, figure=self._fig)
        self.updateDisplay()

    def takeImage(self, exposure, progress):
        if self.__taking:
            return
        self._taking = True
        cam = AllSkyCamera('/dev/tty.usbserial')
        storage = '/home/allsky/images'
        image = cam.get_image(exposure=exposure, progress_callback=progress)
        self._max = image.data.max()
        self.gc = aplpy.FITSFigure(image, figure=self._fig)
        self.updateDisplay()
        self._taking = False

    def updateDisplay(self):
        if self.gc is not None:
            self.gc.show_grayscale(pmin=100-self.cuts, pmax=self.cuts, stretch=self._scale)
            self.gc.axis_labels.hide()
            self.gc.tick_labels.hide()

    def setCuts(self, value):
        self.cuts = value
        self.updateDisplay()

    def getScales(self):
        return self.scales

    def setScale(self, key):
        self._scale = self.scales[str(key)]
        self.updateDisplay()

class MainWindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.ui = uic.loadUi('viewer.ui')
        self.fits = FitsView()
        self.ui.fitsLayout.addWidget(self.fits)
        self.ui.show()
        self.ui.takeImage.clicked.connect(self.takeImage)
        self.ui.normalisation.addItems(self.fits.getScales().keys())
        self.ui.normalisation.currentIndexChanged.connect(self.scaleChange)
        self.ui.cutValue.valueChanged.connect(self.fits.setCuts)
        self.fits.setImage('/Users/tom/test.fits')
        self.fits._layoutChange()

    def scaleChange(self, index):
        self.fits.setScale(self.ui.normalisation.itemText(index))

    def takeImage(self):
        self.progress = QtGui.QProgressDialog('Downloading Image from Camera ...', '', 0, 0)
        self.progress.setCancelButton(None)
        self.progress.setValue(0)
        self.progress.setMinimum(0)
        self.progress.setMaximum(100.0)
        self.progress.setModal(True)
        self.progress.show()
        QtGui.QApplication.processEvents()
        self.fits.takeImage(self.ui.exposureTime.value(), self._takeImageProgress)
        self.progress.hide()

    def _takeImageProgress(self, percent):
        self.progress.setValue(percent)
        QtGui.QApplication.processEvents()

def main():
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    app.exec_()

if __name__ == '__main__':
    main()


