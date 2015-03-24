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

    def save_other(self, filename, overlay=True):
        '''
        Write the image to a file in JPEG/PNG format

        overlay -- add an overlay with timestamp and exposure information
        '''
        # copy the image so we don't change the internal data
        image = self.color_image.copy()

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

def capture_image(device, exposure_time, debayer=False):
    '''
    High level method to capture an image from the SBIG AllSky 340/340C camera

    If a color camera is being used (AllSky 340C), then the debayer parameter
    should be used in order to interpret the color CCD information correctly.

    device -- the device node to use (for example, /dev/ttyUSB0)
    exposure_time -- the exposure time to use (in seconds)
    debayer -- use the de-Bayer function to interpret color CCD data

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

    # scale images to 8-bit
    image.monochrome_image /= 256
    image.color_image /= 256

    return image
