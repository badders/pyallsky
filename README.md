pyallsky
========

A python class for interfacing with the SBIG All Sky 340 camera. Using the [SBIG Serial Protocol Specification](ftp://sbig.com/pub/devsw/SG4_AllSky-340_SerialSpec.pdf).

/viewer/ contains a Qt4 interface for viewing fits files

/web/ constains a simple web.py program for taking images through a web interface.

Requirements
------------
* [OSX Usb to Serial driver](http://plugable.com/drivers/prolific/)
* [Qt library v4](http://qt-project.org/downloads)
* Python 2.7

Python package requirements
-------------------
* [PyQt4](http://www.riverbankcomputing.com/software/pyqt/download)
* [NumPy](http://www.numpy.org/)
* [matplotlib](http://matplotlib.org/)
* [astropy](https://astropy.readthedocs.org/en/stable/)
* [APLpy](http://aplpy.github.io/)
