import sys
import serial
import time
import logging
from datetime import datetime
import struct
import numpy as np
from astropy.io import fits

# Test Commands
COM_TEST = 'E'
OPEN_SHUTTER = 'O'
CLOSE_SHUTTER = 'C'
DE_ENERGIZE = 'K'

# Setup Commands
GET_FVERSION = 'V'
BAUD_RATE = {9600 : 'B0',
             19200 : 'B1',
             38400 : 'B2',
             57600 : 'B3',
             115200 : 'B4',
             230400 : 'B5',
             460800 : 'B6'}

# Imaging Commands
TAKE_IMAGE = 'T'
ABORT_IMAGE = 'A'
XFER_IMAGE = 'X'

CSUM_OK = 'K'
CSUM_ERROR = 'R'
STOP_XFER = 'S'

EXPOSURE_IN_PROGRESS = 'E'
READOUT_IN_PROGRESS = 'R'
EXPOSURE_DONE = 'D'
MAX_EXPOSURE = 0x63FFFF

# Guiding Commands
CALIBRATE_GUIDER = 'H'
AUTO_GUIDE = 'I'
TERMINATOR = chr(0x1A)

# Other Constants
PIXEL_SIZE = 2

def checksum(command):
    """
    Return the command with the checksum byte added
    command - Command string to be sent

    The checksum is simply calculated by complementing the byte, clearing the
    most significant bit and XOR with the current checksum, going through each byte
    in the command. For each individual command the checksum starts as 0
    """
    cs = 0
    for b in command:
        csb = ~ord(b) & 0x7F
        cs = cs ^ csb
    return chr(cs)

def hexify(s):
    """
    Print a string as hex values
    """
    return":".join(c.encode('hex') for c in s)

class AllSkyCamera():
    """
    Class to interact with the all sky camera, encapsulating the serial communication
    protocol, and providing a pythonic api to access the device
    """
    def __init__(self, device):
        ser = serial.Serial('/dev/tty.usbserial')

        # Camera baud rate is initially unknown, so find it
        found = False
        for rate in sorted(BAUD_RATE, key=BAUD_RATE.get)[:-2]:
            logging.debug('Testing : {}'.format(rate))
            ser.baudrate = rate
            ser.write(checksum(COM_TEST))
            time.sleep(0.1)
            # Expect a 2 byte response for this command
            if ser.inWaiting():
                data = ser.read(ser.inWaiting())
                if data == ':0':
                    found = True
                    logging.debug('Baud rate on camera set to {}'.format(rate))
                    break

        if not found:
            logging.debug('Detection failed')
        self._ser = ser

    def set_baudrate(self, baud):
        """
        Set the camera baud rate. Does not work yet.
        """
        try:
            com = BAUD_RATE[baud]
        except KeyError:
            logging.error('Baud rate unsupported')
            return

        # Actually request new baud rate
        logging.debug(com)
        cs = checksum(com)
        self._ser.write(com + cs)
        rs = self._ser.read(1)
        self._ser.baudrate = baud
        assert(rs == cs)
        assert(self._ser.read(1) == 'S')

        com = 'Test'
        self._ser.write(com + cs)
        time.sleep(0.1)

        assert(self._ser.read(6) == 'TestOk')
        self._ser.write('k')

        time.sleep(1)
        print self._ser.inWaiting()

    def _send_command(self, command):
        cs = checksum(command)
        self._ser.write(command + cs)
        response = self._ser.read(1)
        if response != cs:
            logging.error('Command error reponse to {}'.format(command))
        return response == cs

    def firmware_version(self):
        """
        Request version information from the camera
        returns a hex string of the version numbers
        """
        self._send_command(GET_FVERSION)
        v = self._ser.read(2)
        return hexify(v)

    def calibrate_guider(self):
        """
        Request the camera to automatically calibrate the guider.
        returns the string of calibration data sent back from camera
        """
        self._send_command(CALIBRATE_GUIDER)
        response = ''
        a = ''
        while a != TERMINATOR:
            a = self._ser.read(1)
            response += a

        return response

    def autonomous_guide(self):
        """
        Begin autonomous guiding process
        returns -- Data sent back from camera
        """
        self._send_command(AUTO_GUIDE)
        response = ''
        a = ''
        while a != TERMINATOR:
            a = self._ser.read(1)
            response += a

        return response


    def _get_image_block(self, expected=4096, ignore_cs=False):
        """
        Get one 'block' of image data. At full frame the camera returns image
        data in chunks of 4096 pixels. For different imaging modes this value
        will change, but the caller can simply change the value of expected.
        expected -- Number of pixels to retrieve
        ignore_cs -- always pass checksum without checking (for debug only)
        """
        valid = False
        cs_failed = 0
        while not valid:
            data = self._ser.read(expected * PIXEL_SIZE)
            cs_byte = ord(self._ser.read(1))

            cs = 0
            for c in data:
                cs = cs ^ ord(c)

            if cs == cs_byte:
                self._ser.write(CSUM_OK)
                valid = True
            else:
                cs_failed += 1
                self._ser.write(CSUM_ERROR)
            if ignore_cs:
                valid = True

            if cs_failed > 0:
                logging.error('Checksum failed {} times'.format(cs_level))
        logging.debug('Processed {} bytes'.format(len(data)))
        return data

    def get_image(self, exposure=1.0, progress_callback=None):
        """
        Fetch an image from the camera
        exposure -- exposure time in seconds
        progress_callback -- Function to be called after each block downloaded
        returns an astropy HDUList object
        """
        # Camera expsosure time works in 100us units
        exptime = exposure / 100e-6
        if exptime > MAX_EXPOSURE:
            exptime = MAX_EXPOSURE
            exposure = 653.3599
        exp = struct.pack('I', exptime)[:3]
        com = TAKE_IMAGE + exp[::-1] + chr(0x00) + chr(0x01)

        timestamp = datetime.now().isoformat()

        logging.debug('Beginning Exposure')
        self._send_command(com)
        # Wait for exposure to finish
        while True:
            d = self._ser.read(1)
            if d == EXPOSURE_DONE:
                logging.debug('Exposure Complete')
                break

        # Download Image
        blocks_expected = (640 * 480) / 4096
        self._send_command(XFER_IMAGE)

        data = ''
        blocks_complete = 0
        for _ in range(blocks_expected):
            data += self._get_image_block()
            blocks_complete += 1
            if progress_callback is not None:
                progress_callback(float(blocks_complete) / blocks_expected * 100)

        logging.debug('Image download complete')

        # Add information to fits head
        head = fits.Header()
        head['DATAMODE'] = '1X1 BIN'
        head['EXPOSURE'] = '{}'.format(exposure)
        head['DATE-OBS'] = timestamp

        # Now make into a fits image
        data = np.fromstring(data, dtype=np.int16)
        data = data.reshape((480, 640))
        hdu = fits.PrimaryHDU(data, header=head)

        return hdu
