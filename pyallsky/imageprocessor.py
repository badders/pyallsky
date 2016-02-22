#!/usr/bin/env python

'''
Image processing for SBIG AllSky 340/340C
'''

import logging
from collections import namedtuple

import fitsio
import numpy

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageOps

from colour_demosaicing import demosaicing_CFA_Bayer_Malvar2004

# A container for all device configuration information
AllSkyDeviceConfiguration = namedtuple('AllSkyDeviceConfiguration', [
    'device',           # device file
    'exposure',         # nominal exposure time
    'dark',             # take dark current images
    'debayer',          # apply debayer filter (color ccd)
    'grayscale',        # convert JPEG to grayscale
    'postprocess',      # improve brightness and contrast
    'rotate180',        # rotate the image 180 degrees
    'overlay',          # add image overlay (date, time, exposure)
])

class AllSkyImageProcessor(object):
    '''Image processing for SBIG AllSky 340/340C camera'''

    def __init__(self, image, device_config, dark=None):
        '''
        Create an AllSkyImageProcessor

        image -- an instance of AllSkyImage
        device_config -- an instance of AllSkyDeviceConfiguration
        dark -- an optional instance of AllSkyImage containing dark current only
        '''
        self.image = image
        self.config = device_config
        self.fits_headers = []

        # standard FITS headers
        self.add_fits_header('DATAMODE', '1X1 BIN', 'Data Mode')
        self.add_fits_header('EXPOSURE', '%f' % image.exposure, '[s] Exposure length')
        self.add_fits_header('EXPTIME',  '%f' % image.exposure, '[s] Exposure length')
        self.add_fits_header('DATE-OBS', image.timestamp.isoformat(), '[UTC] Date of observation')

        # start with the raw ccd data
        data = image.data

        # subtract the dark if present
        if dark:
            data = data - dark.data

        # convert to numpy array and rotate correctly
        data = numpy.frombuffer(data, dtype=numpy.uint16)
        data = data.reshape((480, 640))

        # debayer for color ccd
        if device_config.debayer:
            data = demosaicing_CFA_Bayer_Malvar2004(data, 'BGGR')

        # rotate180 for mis-mounted cameras
        if device_config.rotate180:
            data = numpy.rot90(numpy.rot90(data))

        # store our processed data for later
        self.data = data

    def add_fits_header(self, name, value, comment):
        '''Add an extra header to FITS files'''
        d = {
            'name': name,
            'value': value,
            'comment': comment,
        }

        self.fits_headers.append(d)

    def save(self, filename):
        '''Write the image to the file, using the appropriate type'''
        if not is_supported_file_type(filename):
            raise RuntimeError('Unsupported file type: ' + filename)

        lowercase = filename.lower()
        if lowercase.endswith('.raw'):
            self.save_raw(filename)
        elif lowercase.endswith('.fit') or lowercase.endswith('.fits'):
            self.save_fits(filename)
        elif lowercase.endswith('.fz'):
            self.save_fits(filename, compress=True)
        elif lowercase.endswith('.jpg') or lowercase.endswith('.jpeg'):
            self.save_jpeg(filename)
        else:
            raise RuntimeError('Unsupported file type: %s' % filename)

    def save_raw(self, filename):
        '''Write the raw CCD output to a file without any manipulation'''
        with open(filename, 'wb') as f:
            f.write(self.image.data.tostring())

    def save_fits(self, filename, compress=False):
        '''
        Write the image to a file in FITS format

        compress -- compress the FITS image with RICE compression (lossless)
        '''
        # copy the image so we don't change the internal data
        data = self.data.copy()

        # debayered images need to be turned into grayscale for FITS
        if data.shape[-1] == 3:
            data = rgb2gray_uint16(data)

        # FITS needs some rotation
        data = numpy.flipud(data)

        # write out the FITS file
        compress = 'RICE' if compress else None
        fitsio.write(filename, data, compress=compress, header=self.fits_headers)

    def save_jpeg(self, filename):
        '''Write the image to a file in JPEG format'''
        # copy the image so we don't change the internal data
        data = self.data.copy()

        # improve brightness and contrast
        if self.config.postprocess:
            mask = create_circle_mask(data)
            data = maximize_dynamic_range(data, mask)

        # scale to 8 bit
        data = scale_to_8bit(data)

        # convert to PIL Image
        image = Image.fromarray(data)

        # convert to grayscale
        if self.config.grayscale:
            image = ImageOps.grayscale(image)

        # add overlay
        if self.config.overlay:
            # three lines: date, time, exposure
            label_text = self.image.timestamp.strftime('%F\n%T\n') + ('%f s' % self.image.exposure)

            font = ImageFont.truetype('DejaVuSansMono.ttf', 16)
            d = ImageDraw.Draw(image)
            d.text((4, 4), label_text, font=font, fill='white')

        # write the image
        image.save(filename, quality=95, optimize=True, progressive=True)

def create_circle_mask(data, rad_frac=0.92):
    '''
    Create the mask needed to retrieve pixels inside and outside of a circular
    area over the center of the image. This is used to retrieve the pixels from
    within the "area of interest" (the sky) in the center of the image,
    excluding the borders.

    Arguments:
        data     - a numpy.ndarray(dtype=numpy.uint16) representing the image
        rad_frac - the fraction of the image to use as the radius of the circle

    Returns:
        A numpy.ndarray(dtype=bool) with the same shape as the input, where a
        True value represents a pixel inside the circle
    '''
    # Pixel coordinates
    ny, nx = data.shape[0:2]
    xx, yy = numpy.meshgrid(1 + numpy.arange(nx), 1 + numpy.arange(ny))

    # Image center
    xp_mid = 0.5 * (nx + 1)
    yp_mid = 0.5 * (ny + 1)

    # Pick a radius
    x_rad = 0.5 * nx * rad_frac
    y_rad = 0.5 * ny * rad_frac
    pix_rad = max(x_rad, y_rad)

    # Select inner/outer pixels
    xsep2 = (xx - xp_mid)
    ysep2 = (yy - yp_mid)
    rsep2 = numpy.sqrt(xsep2 ** 2 + ysep2 ** 2)

    return (rsep2 <= pix_rad)

def maximize_dynamic_range(data, mask=None, pct=(2.5, 97.5)):
    '''
    Use the percentile method to maximize dynamic range of the image.

    Arguments:
        data   - a numpy.ndarray(dtype=numpy.uint16) representing the image
        mask   - a numpy.ndarray(dtype=bool) mask where True represents the
                 pixels that should be used when calculating the histogram
        pct    - the lower and upper percentiles to use

    Returns:
        A copy of the input image which has been transformed to maximize the
        dynamic range
    '''
    if type(data) is not numpy.ndarray:
        raise TypeError('Input was not a numpy.ndarray')

    if str(data.dtype) != 'uint16':
        raise TypeError('Input did not have type numpy.uint16: was %s' % str(data.dtype))

    # if no mask was given, use all pixels
    if mask is None:
        mask = numpy.ones(data.shape, dtype=bool)

    # make a copy of the data (as float32)
    image = data.astype(numpy.float32)

    # calculate the percentiles on the pixels we are interested in
    lower, upper = numpy.percentile(image[mask], pct)

    # make the darkest colored pixel in the usable area of the image black
    image -= lower

    # make the brightest pixel in the usable area of the image white
    image /= (upper - lower)

    # clamp any pixel values to within the [0.0, 1.0] range
    image[(image > 1.0)] = 1.0
    image[(image < 0.0)] = 0.0

    # scale back to the numpy.uint16 data type
    image *= 65535.0
    return image.astype(numpy.uint16)

def scale_to_8bit(data):
    '''Scale a 16-bit image to an 8-bit image'''
    if str(data.dtype) != 'uint16':
        raise TypeError('Input did not have type numpy.uint16: was %s' % str(data.dtype))

    return numpy.array(data / 256.0, dtype=numpy.uint8)

def rgb2gray_uint16(data):
    '''Flatten a 16-bit debayered image into a grayscale image'''
    if str(data.dtype) != 'uint16':
        raise TypeError('Input did not have type numpy.uint16: was %s' % str(data.dtype))

    return numpy.dot(data[...,:3], [0.299, 0.587, 0.114])

def is_supported_file_type(extension):
    '''Is the extension one that is supported by pyallsky'''
    extension = extension.lower()

    if extension.endswith('.raw'):
        return True
    if extension.endswith('.fit') or extension.endswith('.fits'):
        return True
    if extension.endswith('.fz'):
        return True
    if extension.endswith('.jpg') or extension.endswith('.jpeg'):
        return True

    # not one we support
    return False
