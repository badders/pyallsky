from allsky import AllSkyCamera
import matplotlib
matplotlib.use('Qt4Agg')

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import aplpy

import sys
from PyQt4 import QtGui, QtCore, uic

from collections import OrderedDict

class FitsView(FigureCanvasQTAgg):
    """
    A FITS imageviewer base on matplotlib, rendering is done using the astropy
    library.
    """
    def __init__(self):
        self._fig = Figure(dpi=96)
        FigureCanvasQTAgg.__init__(self, self._fig)
        FigureCanvasQTAgg.setSizePolicy(self,
                                        QtGui.QSizePolicy.Expanding,
                                        QtGui.QSizePolicy.Expanding)
        self._fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.__taking = False
        self._scale = 'linear'
        self.scales = OrderedDict()
        self.scales['Linear'] =  'linear'
        self.scales['Square Root'] = 'sqrt'
        self.scales['Power'] = 'power'
        self.scales['Logarithmic'] = 'log'
        self.scales['Arc Sinh'] = 'arcsinh'
        self.gc = None
        self.upperCut = 99.75
        self.lowerCut = 0.25
        self.cmap = 'gray'

    def loadImage(self, filename):
        """
        Load a fits image from disk
        filename -- full path to the image file
        """
        self.gc = aplpy.FITSFigure(filename, figure=self._fig)
        self._updateDisplay()

    def takeImage(self, exposure, progress, dev='/dev/tty.usberial'):
        """
        Take an image using the All Sky camera
        exposure -- Desired exposure time
        progress -- Function for progress update callback
        dev -- Path to serial device
        """
        if self.__taking:
            return
        self._taking = True
        cam = AllSkyCamera(dev)
        image = cam.get_image(exposure=exposure, progress_callback=progress)
        self._max = image.data.max()
        self.gc = aplpy.FITSFigure(image, figure=self._fig)
        self._updateDisplay()
        self._taking = False

    def _updateDisplay(self):
        if self.gc is not None:
            self.gc.show_colorscale(pmin=self.lowerCut, pmax=self.upperCut,
                                    stretch=self._scale, aspect='auto',
                                    cmap=self.cmap)
            self.gc.axis_labels.hide()
            self.gc.tick_labels.hide()

    def setCMAP(self, cmap):
        """
        Set the colourmap for the image display
        cmap -- colourmap name (see matplotlib.cm)
        """
        self.cmap = cmap
        self._updateDisplay()

    def setUpperCut(self, value):
        """
        Set the upper limit for display cut
        value -- percentage for upper limit
        """
        self.upperCut = value
        self._updateDisplay()

    def setLowerCut(self, value):
        """
        Set the lower limit for display cut
        value -- percentage for the lower limit
        """
        self.lowerCut = value
        self._updateDisplay()

    def getScales(self):
        """
        return the available normalisation scales
        """
        return self.scales

    def setScale(self, scale):
        """
        Set normalisation scale
        scale -- desired scale
        """
        self._scale = self.scales[str(scale)]
        self._updateDisplay()

class MainWindow(QtGui.QMainWindow):
    """
    Application User interface
    """
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.ui = uic.loadUi('viewer.ui')
        self.fits = FitsView()
        self.ui.fitsLayout.addWidget(self.fits)
        self.ui.show()
        self.ui.takeImage.clicked.connect(self.takeImage)
        self.ui.normalisation.addItems(self.fits.getScales().keys())
        self.ui.normalisation.currentIndexChanged.connect(self.scaleChange)

        self.ui.colourMap.addItems(matplotlib.cm.datad.keys())
        self.ui.colourMap.setCurrentIndex(matplotlib.cm.datad.keys().index('gray'))

        self.ui.colourMap.currentIndexChanged.connect(self.cmapChange)
        self.ui.cutUpperValue.valueChanged.connect(self.fits.setUpperCut)
        self.ui.cutLowerValue.valueChanged.connect(self.fits.setLowerCut)

        self.ui.loadButton.clicked.connect(self.loadImage)

    def cmapChange(self, index):
        self.fits.setCMAP(matplotlib.cm.datad.keys()[index])

    def scaleChange(self, index):
        self.fits.setScale(self.ui.normalisation.itemText(index))

    def loadImage(self):
        filen = QtGui.QFileDialog.getOpenFileName(caption='Load Fits File', filter='*.fits')
        self.fits.loadImage(str(filen))

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


