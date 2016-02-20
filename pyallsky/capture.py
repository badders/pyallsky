#!/usr/bin/env python

'''
Capture an image in RAW/JPG/FITS format from an SBIG AllSky 340/340C
'''

import cv2
import array
import logging
import numpy
from astropy.io import fits

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
        self.pixels = array.array('B')
        self.monochrome_image = numpy.zeros(0)
        self.color_image = numpy.zeros(0)

    def save_raw(self, filename):
        '''Write the raw CCD output to a file without any manipulation'''
        with open(filename, 'wb') as f:
            f.write(self.pixels.tostring())

    def save_fits(self, filename):
        '''Write the image to a file in FITS format'''
        # add information to FITS header
        header = fits.Header()
        header['DATAMODE'] = ('1X1 BIN', 'Data Mode')
        header['EXPOSURE'] = ('%f' % self.exposure, '[s] Exposure length')
        header['EXPTIME']  = ('%f' % self.exposure, '[s] Exposure length')
        header['DATE-OBS'] = (self.timestamp.isoformat(), '[UTC] Date of observation')

        # FITS needs some rotation
        data = self.monochrome_image.copy()
        data = numpy.flipud(data)

        hdu = fits.PrimaryHDU(data, header=header)
        hdu.writeto(filename)

    def save_other(self, filename, postprocess=True, overlay=True):
        '''
        Write the image to a file in JPEG/PNG format

        postprocess -- boost the image's brightness and contrast
        overlay -- add an overlay with timestamp and exposure information
        '''
        # copy the image so we don't change the internal data
        image = self.color_image.copy()

        if postprocess:
            mask = create_circle_mask(image)
            image = maximize_dynamic_range(image, mask)

        # scale to 8 bit
        image = scale_to_8bit(image)

        if overlay:
            # small white font about 10 px tall
            font = cv2.FONT_HERSHEY_PLAIN
            scale = 1
            color = (255, 255, 255)
            position = [0, 0]

            # line 1: date
            position[1] += 16
            text = self.timestamp.strftime('%F')
            cv2.putText(image, text, tuple(position), font, scale, color)

            # line 2: time
            position[1] += 16
            text = self.timestamp.strftime('%T')
            cv2.putText(image, text, tuple(position), font, scale, color)

            # line 3: exposure
            position[1] += 16
            text = '%f s' % self.exposure
            cv2.putText(image, text, tuple(position), font, scale, color)

        # write the image
        cv2.imwrite(filename, image)

def show_progress(pct):
    '''Method to display image transfer progress depending on logging level'''
    logging.info('Transfer progress: %.2f%%', pct)

def capture_image(device, exposure_time, debayer=False, rotate180=False):
    '''
    High level method to capture an image from the SBIG AllSky 340/340C camera

    If a color camera is being used (AllSky 340C), then the debayer parameter
    should be used in order to interpret the color CCD information correctly.

    device -- the device node to use (for example, /dev/ttyUSB0)
    exposure_time -- the exposure time to use (in seconds)
    debayer -- use the de-Bayer function to interpret color CCD data
    rotate180 -- rotate the image 180 degrees: some cameras are installed upside down

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
    image.pixels = cam.xfer_image(progress_callback=show_progress)

    # convert to numpy array and rotate correctly
    data = numpy.frombuffer(image.pixels, dtype=numpy.uint16)
    data = data.reshape((480, 640))

    # make copies of the CCD data
    image.monochrome_image = numpy.copy(data)
    image.color_image = numpy.copy(data)

    # color CCDs need de-Bayer
    if debayer:
        image.monochrome_image = cv2.cvtColor(data, cv2.COLOR_BAYER_BG2GRAY)
        image.color_image = cv2.cvtColor(data, cv2.COLOR_BAYER_BG2RGB)

    # some cameras are installed upside down, so we can optionally rotate
    # this must happen after the debayer, otherwise the colors get messed up
    # due to changing the pixel ordering
    if rotate180:
        image.monochrome_image = numpy.rot90(numpy.rot90(image.monochrome_image))
        image.color_image = numpy.rot90(numpy.rot90(image.color_image))

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
