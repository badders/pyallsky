pyallsky
========

A Python class for intefacing with the SBIG AllSky 340/340C camera.

Created using the [SBIG Serial Protocol Specification](ftp://sbig.com/pub/devsw/SG4_AllSky-340_SerialSpec.pdf).

Works on Linux (including Raspberry Pi) and Mac OSX, untested on Windows but no reason it shouldn't work.

Requirements
------------
* [OSX Usb to Serial driver](http://plugable.com/drivers/prolific/)
* [Python 2.7](http://python.org)

Python package requirements
-------------------
* [pyserial](http://pyserial.sourceforge.net/)
* [NumPy](http://www.numpy.org/)
* [astropy](https://astropy.readthedocs.org/en/stable/)
* [OpenCV 2 Python Bindings](http://opencv.org/)

If you are running under the Anaconda Python Distribution, use "conda install opencv"
to install the OpenCV 2 bindings. On CentOS 7, the "opencv-python" package has them.

Everything else is avalable using pip/easy_install.
