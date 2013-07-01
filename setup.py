from setuptools import setup, find_packages

setup(
    name = 'pyallsky',
    version = '0.1dev',
    packages = find_packages(exclude='web')
)
