pyallsky
========

A Python class for intefacing with the SBIG AllSky 340/340C camera.

Created using the [SBIG Serial Protocol Specification](ftp://sbig.com/pub/devsw/SG4_AllSky-340_SerialSpec.pdf).

Works on Linux (including Raspberry Pi) and Mac OSX, untested on Windows but no reason it shouldn't work.

Requirements
------------
* [OSX USB to Serial driver](http://plugable.com/drivers/prolific/)
* [Python 2.7](http://python.org)

Python package requirements
-------------------
* [colour_demosaicing](https://pypi.python.org/pypi/colour-demosaicing)
* [pyephem](http://rhodesmill.org/pyephem/)
* [fitsio](https://pypi.python.org/pypi/fitsio/)
* [NumPy](http://www.numpy.org/)
* [Pillow](http://python-pillow.org/)
* [pyserial](http://pyserial.sourceforge.net/)

Everything is avalable using pip/easy_install.

LCOGT AllSky Scheduler
----------------------

LCOGT runs installations consisting of two SBIG AllSky cameras within a single
enclosure. These are placed at each LCOGT telescope site, and the data is used
for weather information. An SBIG AllSky 340C is used during the day, and an SBIG
AllSky 340 is used during the night. This setup gives the best images available
at all times of day.

Since this hardware lacks a light meter, the exposure time is chosen based on
the position of the Sun. An experimentally tuned curve is used to gradually
adjust exposure time near sunset and sunrise.

To maximize the astronomical usefulness of the data, dark current subtraction
can be enabled. This will only activate when the full exposure length is
reached. It will not run during the sunset and sunrise exposure length ramp.
