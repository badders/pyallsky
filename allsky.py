import sys
import serial
import argparse
import time
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
            print 'Testing :', rate
            ser.baudrate = rate
            ser.write(checksum(COM_TEST))
            time.sleep(0.1)
            # Expect a 2 byte response for this command
            if ser.inWaiting():
                data = ser.read(ser.inWaiting())
                if data == ':0':
                    found = True
                    print 'Baud rate on camera set to', rate
                    break

        if not found:
            print 'Detection failed'
        self._ser = ser

    def set_baudrate(self, baud):
        try:
            com = BAUD_RATE[baud]
        except KeyError:
            print 'Baud rate unsupported'
            return

        # Actually request new baud rate
        print com
        cs = checksum(com)
        self._ser.write(com + cs)
        rs = self._ser.read(1)
        self._ser.baudrate = baud
        if rs != cs:
            print rs, cs
            print 'An unknown error occured rs!= cs'
            return

        if self._ser.read(1) != 'S':
            print 'An unknown error occured no S'
            return

        com = 'Test'
        self._ser.write(com + cs)
        print 'Sending Test'
        time.sleep(0.1)

        print self._ser.inWaiting()
        if self._ser.read(6) != 'TestOk':
            print 'An unknown error occured not TestOK'
            return
        else:
            print 'TestOk'

        self._ser.write('k')

        time.sleep(1)
        print self._ser.inWaiting()

    def _send_command(self, command):
        cs = checksum(command)
        self._ser.write(command + cs)
        response = self._ser.read(1)
        if response != cs:
            print 'Command error', command
        return response == cs

    def firmware_version(self):
        """
        Request version information from the camera
        returns - hex string of the version numbers
        """
        self._send_command(GET_FVERSION)
        v = self._ser.read(2)
        return hexify(v)

    def calibrate_guider(self):
        """
        Request the camera to automatically calibrate the guider.
        returns - Calibration data sent back from camera
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
        returns - Data sent back from camera
        """
        self._send_command(AUTO_GUIDE)
        response = ''
        a = ''
        while a != TERMINATOR:
            a = self._ser.read(1)
            response += a

        return response


    def _get_image_block(self, expected=4096, ignore_cs=False):
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
                print 'Checksum failed', cs_failed, 'times'
        print 'Processed', len(data), 'bytes'
        return data

    def get_image(self, exposure=40):
        """
        Fetch an image from the camera
        exposure - exposure time in 100us units
        returns an astropy PrimaryHDU object
        """
        exp = struct.pack('I', exposure)[:3]
        com = TAKE_IMAGE + exp[::-1] + chr(0x00) + chr(0x01)

        self._send_command(com)

        # Wait for exposure to finish
        while True:
            d = self._ser.read(1)
            if d == EXPOSURE_DONE:
                print 'Exposure Complete'
                break

        # Download Image
        blocks_expected = (640 * 480) / 4096
        self._send_command(XFER_IMAGE)

        data = ''
        for _ in range(blocks_expected):
            data += self._get_image_block()

        # Now make into a fits image
        data = np.fromstring(data, dtype=np.int16)
        print data.shape
        data = data.reshape((480, 640))
        print data.shape
        hdu = fits.PrimaryHDU(data)

        return hdu

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch images from SBIG AllSky Camera')
    parser.add_argument('device', metavar='D', nargs=1, help='Serial device')
    args = parser.parse_args()
    dev = args.device[0]

    camera = AllSkyCamera(dev)
    print camera.firmware_version()
    # print camera.calibrate_guider()
    # print camera.autonomous_guide()
    camera.get_image().writeto('/Users/tom/test.fits', clobber=True)
