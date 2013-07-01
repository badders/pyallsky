from setuptools import setup, find_packages

setup(
    name = 'pyallsky',
    version = '0.1dev',
    entry_points = {
        'console_scripts': [
            'fits-capture = fits_capture:main'
        ]
    },
    packages = find_packages(exclude='web')
)
