#!/usr/bin/env python

from setuptools import setup

setup(
    name = 'pyallsky',
    version = '1.3.1',
    description = 'Python Control of SBIG AllSky 340/340C Camera',
    url = 'https://github.com/LCOGT/pyallsky',
    author = 'Las Cumbres Observatory Software Team',
    author_email = 'softies@lco.global',
    license = 'LGPL',
    packages = ['pyallsky'],
    python_requires = '>=2.7.6, <3',
    install_requires = [
        'colour-demosaicing==0.1.3',
        'daemonize~=2.5.0',
        'fitsio~=1.0.5',
        'numpy>=1.16.0,<1.17.0',
        'Pillow~=6.2.0',
        'pyephem~=3.7.7.0',
        'pyserial>=2.7,<3.0',
        # The scipy dependency isn't used directly by this code: it is a
        # transient dependency of the colour-demosaicing module. Either
        # Python, setuptools, or pip has a bug handling transient dependencies
        # on Python 2.7, and attempts to install a version of scipy which
        # is not compatible with Python 2.7. Adding an explicit version
        # dependency fixes the issue. Remove this when the project is upgraded
        # to use Python 3.
        'scipy<1.3.0',
        # The colour-science dependency isn't used directly by this code: it is
        # a transient dependency of the colour-demosaicing module. We specify
        # the version explicitly to avoid a numpy version dependency problem in
        # newer versions. We can't upgrade numpy because we can't upgrade Python.
        'colour-science==0.3.11',
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
