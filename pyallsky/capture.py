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
        header['DATAMODE'] = '1X1 BIN'
        header['EXPOSURE'] = '%f' % self.exposure
        header['DATE-OBS'] = self.timestamp.isoformat()

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
            image = maximize_dynamic_range(image)
            image = scale_to_8bit(image)
            image = clahe(image)

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

    logging.info('Opening shutter')
    cam.open_shutter()

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

def maximize_dynamic_range(image):
    '''
    Maximize the dynamic range of the image by taking the darkest pixel and
    making it black, and finding the brightest pixel and making it white
    '''
    if type(image) is not numpy.ndarray:
        raise TypeError('Input was not a numpy.ndarray')

    # the maximum value of the data type that makes up this image
    # 255 for 8-bit, 65535 for 16-bit, etc.
    typeMax = numpy.iinfo(image.dtype).max

    image = numpy.copy(image)

    # make the darkest colored pixel in the image black
    minValue = numpy.amin(image)
    image -= minValue

    # make the brightest colored pixel in the image white
    maxValue = numpy.amax(image)
    image *= (float(typeMax) / maxValue)

    return image

def scale_to_8bit(image):
    '''Scale a 16-bit image to an 8-bit image'''
    if str(image.dtype) != 'uint16':
        raise TypeError('Input did not have type numpy.uint16: was %s' % str(image.dtype))

    return numpy.array(image / 256.0, dtype=numpy.uint8)

def cvclahe(image, clipLimit=2.0, gridSize=4):
    '''
    Use the OpenCV Contrast Limited Adaptive Histogram Equalization algorithm
    to improve the brightness and contrast of the image
    '''
    if type(image) is not numpy.ndarray:
        raise TypeError('Input was not a numpy.ndarray')

    if str(image.dtype) != 'uint8':
        raise TypeError('Input did not have type numpy.uint8: was %s' % str(image.dtype))

    clahe = cv2.createCLAHE(clipLimit=clipLimit, tileGridSize=(gridSize, gridSize))

    # handle both color and monochrome images
    if image.shape[-1] == 3:
        planes = cv2.split(image)
        planes = map(clahe.apply, planes)
        return cv2.merge(planes)
    else:
        return clahe.apply(image)

def skclahe(image):
    '''
    SciKit-Image based CLAHE algorithm, used when OpenCV package is too old

    Scales the image in a bizarre way as compared to OpenCV. We compensate for
    the scaling by multiplying the image from floats in the range [0.0, 1.0]
    back into uint8 values.
    '''
    import skimage.exposure
    image = skimage.exposure.equalize_adapthist(image, ntiles_x=16, ntiles_y=16)
    image *= 255.0
    return image

def clahe(image, clipLimit=2.0, gridSize=4):
    ''' Wrapper around multiple possible CLAHE algorithms'''

    try:
        logging.info('Trying OpenCV CLAHE')
        return cvclahe(image, clipLimit, gridSize)
    except AttributeError:
        logging.info('OpenCV does not have the createCLAHE function: please upgrade')

    try:
        logging.info('Trying SciKit-Image CLAHE')
        return skclahe(image)
    except ImportError:
        logging.info('No SciKit-Image found: please install it for CLAHE support')

    logging.info('No supported CLAHE package found, image is unchanged')
    return image
