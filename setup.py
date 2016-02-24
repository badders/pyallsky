#!/usr/bin/env python

from setuptools import setup

setup(
    name = 'pyallsky',
    version = '0.5',
    description = 'Python Control of SBIG AllSky 340/340C Camera',
    url = 'http://www.lcogt.net',
    author = 'Ira W. Snyder',
    author_email = 'isnyder@lcogt.net',
    license = 'LGPL',
    packages = ['pyallsky'],
    install_requires = [
        'colour_demosaicing',
        'daemonize',
        'fitsio',
        'numpy',
        'Pillow',
        'pyephem',
        'pyserial<3.0',
    ],
    scripts = [
        'bin/allsky_capture_image',
        'bin/allsky_check_communications',
        'bin/allsky_get_version',
        'bin/allsky_heater_control',
        'bin/allsky_set_baudrate',
        'bin/allsky_scheduler',
        'bin/allsky_shutter_control',
    ],
    zip_safe = False
)
