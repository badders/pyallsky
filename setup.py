#!/usr/bin/env python

from setuptools import setup

setup(
    name = 'pyallsky',
    version = '0.2',
    description = 'Python Control of SBIG AllSky 340/340C Camera',
    url = 'http://www.lcogt.net',
    author = 'Ira W. Snyder',
    author_email = 'isnyder@lcogt.net',
    license = 'LGPL',
    packages = ['pyallsky'],
    install_requires = [
        'astropy',
        'colour_demosaicing',
        'Pillow',
        'numpy',
        'pyserial',
    ],
    scripts = [
        'bin/allsky_capture_image',
        'bin/allsky_check_communications',
        'bin/allsky_get_version',
        'bin/allsky_heater_control',
        'bin/allsky_set_baudrate',
        'bin/allsky_shutter_control',
    ],
    zip_safe = False
)
