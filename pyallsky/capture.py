#!/usr/bin/env python

'''
Capture an image in RAW/JPG/FITS format from an SBIG AllSky 340/340C
'''

import array
import datetime
import logging
import numpy

from astropy.io import fits

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageOps

from colour_demosaicing import demosaicing_CFA_Bayer_Malvar2004

from pyallsky import AllSkyCamera

class AllSkyImage(object):
    '''
    Class to hold all of the data about an exposure taken by the
    SBIG AllSky 340/340C camera. The images can be saved to the filesystem
    in several different standard formats.
    '''

    def __init__(self):
        self.timestamp = 'UNSET'
        self.exposure = 0.0
        self.raw_pixels = array.array('B')
        self.raw_image = numpy.zeros(0)

    def debayer(self):
        '''Demosaic (debayer) the image'''
        self.raw_image = demosaicing_CFA_Bayer_Malvar2004(self.raw_image, 'BGGR')

    def rotate180(self):
        '''Rotate the image by 180 degrees'''
        self.raw_image = numpy.rot90(numpy.rot90(self.raw_image))

    def save_raw(self, filename):
        '''Write the raw CCD output to a file without any manipulation'''
        with open(filename, 'wb') as f:
            f.write(self.raw_pixels.tostring())

    def save_fits(self, filename):
        '''Write the image to a file in FITS format'''
        # copy the image so we don't change the internal data
        image = self.raw_image.copy()

        # debayered images need to be turned into grayscale for FITS
        if image.shape[-1] == 3:
            image = rgb2gray_uint16(image)

        # FITS needs some rotation
        image = numpy.flipud(image)

        # add information to FITS header
        header = fits.Header()
        header['DATAMODE'] = ('1X1 BIN', 'Data Mode')
        header['EXPOSURE'] = ('%f' % self.exposure, '[s] Exposure length')
        header['EXPTIME']  = ('%f' % self.exposure, '[s] Exposure length')
        header['DATE-OBS'] = (self.timestamp.isoformat(), '[UTC] Date of observation')

        hdu = fits.PrimaryHDU(image, header=header)
        hdu.writeto(filename)

    def save_other(self, filename, monochrome=False, postprocess=True, overlay=True):
        '''
        Write the image to a file in JPEG/PNG format

        monochrome -- save the image in monochrome (grayscale)
        postprocess -- boost the image's brightness and contrast
        overlay -- add an overlay with timestamp and exposure information
        '''
        # copy the image so we don't change the internal data
        image = self.raw_image.copy()

        # improve brightness and contrast
        if postprocess:
            mask = create_circle_mask(image)
            image = maximize_dynamic_range(image, mask)

        # scale to 8 bit
        image = scale_to_8bit(image)

        # convert to PIL Image
        image = Image.fromarray(image)

        # convert to monochrome
        if monochrome:
            image = ImageOps.grayscale(image)

        if overlay:
            # line 1: date
            # line 2: time
            # line 3: exposure
            label_text = self.timestamp.strftime('%F\n%T\n') + ('%f s' % self.exposure)

            font = ImageFont.truetype('DejaVuSansMono.ttf', 16)
            d = ImageDraw.Draw(image)
            d.text((4, 4), label_text, font=font, fill='white')

        # write the image
        image.save(filename, quality=95, optimize=True, progressive=True)

def show_progress(pct):
    '''Method to display image transfer progress depending on logging level'''
    logging.info('Transfer progress: %.2f%%', pct)

def capture_image(device, exposure_time):
    '''
    High level method to capture an image from the SBIG AllSky 340/340C camera

    If a color camera is being used (AllSky 340C), then the debayer parameter
    should be used in order to interpret the color CCD information correctly.

    device -- the device node to use (for example, /dev/ttyUSB0)
    exposure_time -- the exposure time to use (in seconds)

    Exceptions:
    serial.serialutil.SerialException -- exception raised by pyserial
    AllSkyException -- exception raised by pyallsky

    Returns an instance of AllSkyImage
    '''
    logging.info('Connecting to camera')
    cam = AllSkyCamera(device)

    # create image storage
    image = AllSkyImage()
    image.exposure = exposure_time

    logging.info('Taking exposure')
    image.timestamp = cam.take_image(exposure=exposure_time)

    logging.info('Downloading image')
    image.raw_pixels = cam.xfer_image(progress_callback=show_progress)

    # convert to numpy array and rotate correctly
    image.raw_image = numpy.frombuffer(image.raw_pixels, dtype=numpy.uint16)
    image.raw_image = image.raw_image.reshape((480, 640))

    return image

def load_raw(filename, exposure_time=30.0, timestamp=None):
    '''
    Load a RAW image into an AllSkyImage object

    This is primarily meant to be used to debug the image postprocessing code
    without requiring the camera hardware.
    '''
    # fake timestamp data if not specified
    if not timestamp:
        timestamp = datetime.datetime.utcnow()

    data = array.array('B')
    with open(filename, 'r') as f:
        data = array.array('B', f.read())

    image = AllSkyImage()
    image.exposure = exposure_time
    image.timestamp = timestamp
    image.raw_pixels = data

    # convert to numpy array and rotate correctly
    image.raw_image = numpy.frombuffer(image.raw_pixels, dtype=numpy.uint16)
    image.raw_image = image.raw_image.reshape((480, 640))

    return image

def create_circle_mask(pixels, rad_frac=0.92):
    '''
    Create the mask needed to retrieve pixels inside and outside of a circular
    area over the center of the image. This is used to retrieve the pixels from
    within the "area of interest" (the sky) in the center of the image,
    excluding the borders.

    Arguments:
        pixels   - a numpy.ndarray(dtype=numpy.uint16) representing the image
        rad_frac - the fraction of the image to use as the radius of the circle

    Returns:
        A numpy.ndarray(dtype=bool) with the same shape as the input, where a
        True value represents a pixel inside the circle
    '''
    # Pixel coordinates
    ny, nx = pixels.shape[0:2]
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

def maximize_dynamic_range(pixels, mask=None, pct=[2.5, 97.5]):
    '''
    Use the percentile method to maximize dynamic range of the image.

    Arguments:
        pixels - a numpy.ndarray(dtype=numpy.uint16) representing the image
        mask   - a numpy.ndarray(dtype=bool) mask where True represents the
                 pixels that should be used when calculating the histogram
        pct    - the lower and upper percentiles to use

    Returns:
        A copy of the input image which has been transformed to maximize the
        dynamic range
    '''
    if type(pixels) is not numpy.ndarray:
        raise TypeError('Input was not a numpy.ndarray')

    if str(pixels.dtype) != 'uint16':
        raise TypeError('Input did not have type numpy.uint16: was %s' % str(pixels.dtype))

    # if no mask was given, use all pixels
    if mask is None:
        mask = numpy.ones(pixels.shape, dtype=bool)

    # make a copy of the data (as float32)
    image = pixels.astype(numpy.float32)

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

def scale_to_8bit(image):
    '''Scale a 16-bit image to an 8-bit image'''
    if str(image.dtype) != 'uint16':
        raise TypeError('Input did not have type numpy.uint16: was %s' % str(image.dtype))

    return numpy.array(image / 256.0, dtype=numpy.uint8)

def rgb2gray_uint16(image):
    '''Flatten a 16-bit debayered image into a grayscale image'''
    if str(image.dtype) != 'uint16':
        raise TypeError('Input did not have type numpy.uint16: was %s' % str(image.dtype))

    return numpy.dot(image[...,:3], [0.299, 0.587, 0.114])
