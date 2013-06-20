from allsky import AllSkyCamera
import matplotlib
matplotlib.use('Qt4Agg')

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

import matplotlib.pyplot as plt
import aplpy

import sys
from PySide import QtGui
from PySide.QtUiTools import QUiLoader

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
    def setImage(self, filename):
        gc = aplpy.FITSFigure(filename, figure=self._fig)
        gc.show_grayscale()

    def takeImage(self):
        cam = AllSkyCamera('/dev/tty.usbserial')
        storage = '/home/allsky/images'
        image = cam.get_image(exposure=0.1)


class MainWindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.ui = QUiLoader().load('viewer.ui')
        self.fits = FitsView()
        self.ui.fitsLayout.addWidget(self.fits)
        self.ui.show()
        self.fits.setImage('/Users/tom/test.fits')

def main():
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    app.exec_()

if __name__ == '__main__':
    main()


