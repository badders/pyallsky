#!/usr/bin/env python

'''
Control for the SBIG AllSky 340/340C
'''

import serial
import time
import logging
import datetime
import struct
import array

# Test Commands
COM_TEST = 'E'

# Shutter Commands
OPEN_SHUTTER = 'O'
CLOSE_SHUTTER = 'C'
DE_ENERGIZE = 'K'

# Heater Commands
HEATER_ON = 'g\x01'
HEATER_OFF = 'g\x00'

# Setup Commands
GET_FVERSION = 'V'
GET_SERIAL = 'r'
BAUD_RATE = {9600: 'B0',
             19200: 'B1',
             38400: 'B2',
             57600: 'B3',
             115200: 'B4',
             230400: 'B5',
             460800: 'B6'}

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
    '''
    Return the checksum of an arbitrary command

    command -- command string to checksum

    The checksum is simply calculated by complementing the byte, clearing the
    most significant bit and XOR with the current checksum, going through each byte
    in the command. For each individual command the checksum starts as 0
    '''
    cs = 0
    for b in command:
        csb = ~ord(b) & 0x7F
        cs = cs ^ csb
    return chr(cs)


def hexify(s, join_char=':'):
    '''
    Print a string as hex values
    '''
    return join_char.join(c.encode('hex') for c in s)

def bufdump(buf):
    '''
    Print a byte buffer in the convenient format of a hex-ified string and
    the total length
    '''
    return '"%s" (%d bytes)' % (hexify(buf), len(buf))

def serial_rx(ser, nbytes, timeout=0.5):
    '''
    Receive data from a serial port with a timeout

    ser -- the serial.Serial() to receive from
    nbytes -- the maximum number of bytes to receive
    timeout -- the maximum number of seconds to wait for data
    '''
    tstart = time.time()
    data = ''

    while True:
        # timeout has passed, break out of the loop
        tcurrent = time.time()
        tdiff = tcurrent - tstart
        if tdiff > timeout:
            break

        # we have all the bytes, break out of the loop
        remain = nbytes - len(data)
        if remain == 0:
            break

        # append more bytes as they come in
        data += ser.read(remain)

    return data

def serial_tx(ser, data, timeout=0.5):
    '''
    Write data to a serial port with a timeout

    ser -- the serial.Serial() to receive from
    data -- the data to send
    timeout -- the maximum number of seconds to try to send data
    '''
    ser.write(data)

def serial_rx_until(ser, terminator, timeout=5.0):
    '''
    Receive data from a serial port until a certain terminator character is received

    ser -- the serial.Serial() to receive from
    terminator -- the single character which terminates the receive operation
    timeout -- the maximum amount of time to wait

    Returns all of the data read up to (but not including) the terminator
    '''
    tstart = time.time()
    data = ''

    while True:
        # timeout has passed, break out of the loop
        tcurrent = time.time()
        tdiff = tcurrent - tstart
        if tdiff > timeout:
            break

        c = ser.read(1)
        if c == terminator:
            break

        # terminator was not found, append the current byte
        data += c

    return data

def serial_expect(ser, txcmd, rxcmd, timeout=0.5):
    '''
    Send a command and receive an expected reply

    ser -- the serial.Serial() to receive from
    txcmd -- the command to transmit (checksum will be added automatically)
    rxcmd -- the expected response
    timeout -- the maximum number of seconds to wait for the response

    return -- True on success, False otherwise
    '''
    csum = checksum(txcmd)
    txdata = txcmd + csum
    rxdata = csum + rxcmd

    logging.debug('serial_expect: tx %s', bufdump(txdata))
    serial_tx(ser, txdata, timeout)

    logging.debug('serial_expect: begin rx')
    data = serial_rx(ser, len(rxdata) * 10, timeout)

    logging.debug('serial_expect: rx %s', bufdump(data))
    logging.debug('serial_expect: ex %s', bufdump(rxdata))

    if data.endswith(rxdata):
        logging.debug('serial_expect: success, rx and ex match')
        return True
    else:
        logging.debug('serial_expect: failure, rx and ex mismatch')
        return False

def check_communications(ser, count=3, required_successes=2):
    '''
    Use the 'Communictions Test' command to verify that communications with
    the camera are working as expected. Both the number of trials and the
    required number of successes can be specified.

    ser -- the serial.Serial() to receive from
    count -- the maximum number of times to attempt to communicate
    required_successes -- the number of successful attempts required

    return -- True on success, False otherwise
    '''
    successes = 0

    for i in xrange(count):
        logging.debug('Checking current communication settings, try %d', i)

        if serial_expect(ser, 'E', 'O', 0.1):
            logging.debug('Successful communication attempt')
            successes += 1
        else:
            logging.debug('Unsuccessful communication attempt')

        # possible early exit
        if successes >= required_successes:
            break

    if successes >= required_successes:
        logging.debug('Required number of successes reached')
        return True
    else:
        logging.debug('Communications test failed: successes=%d', successes)
        return False

def autobaud(ser, count=3):
    '''
    Automatic Baud Rate Detection

    The manual specifies an algorithm where each possible baud rate is
    attempted once, and the successful one is the winner. This is insufficient,
    since the previous attempts may leave some junk in the serial port buffer
    on the receiving side.

    To work around the problem, we set the attempted baud rate, then
    check the communications several times to clear out any leftover junk.
    This method has been found to be extremely reliable.

    ser -- the serial.Serial() to receive from
    count -- the maximum number of attempts to communicate at each baud rate

    return -- True on success, False otherwise
    '''
    found = False
    for rate in sorted(BAUD_RATE, key=BAUD_RATE.get)[:-2]:
        logging.debug('Testing baud rate %s', rate)
        ser.setBaudrate(rate)
        found = check_communications(ser, count)
        if found:
            logging.info('Autodetect baud rate successful %d', rate)
            break

    return found

def serial_timeout_calc(ser, nbytes):
    '''
    Calculate the required timeout to transmit a certain number of bytes
    based on the current baud rate of the serial port

    ser -- the serial.Serial() to receive from
    nbytes -- the number of bytes that will be transmitted

    return -- the time required to transmit in seconds
    '''
    # (bits_per_second / number_of_bits) * overhead_fudge_factor
    return (ser.getBaudrate() / (nbytes * 8)) * 1.5

class AllSkyException(Exception):
    '''Specific exception class for errors from this code'''
    pass

class AllSkyCamera(object):
    '''
    Class to interact with the SBIG AllSky 340/340C camera, encapsulating the
    serial communication protocol, and providing a pythonic api to access the
    device.

    Automatically determines the baud rate necessary for communication.
    '''
    def __init__(self, device):
        ser = serial.Serial(device)

        # defaults taken from the manual
        ser.setBaudrate(9600)
        ser.bytesize = serial.EIGHTBITS
        ser.parity = serial.PARITY_NONE
        ser.stopbits = serial.STOPBITS_ONE

        # set a short timeout for reads during baud rate detection
        ser.timeout = 0.1

        # Camera baud rate is initially unknown, so find it
        if not autobaud(ser, count=3):
            logging.debug('Autodetect baud rate failed')
            raise AllSkyException('Autodetect baud rate failed')

        self.__ser = ser

    def get_baudrate(self):
        '''
        Get the current serial port baudrate
        '''
        return self.__ser.getBaudrate()

    def set_baudrate(self, baudrate):
        '''
        Set the camera baud rate. This is stored in non-volatile memory,
        so the setting will be kept across power cycles.
        '''
        # check for supported baud rate
        try:
            BAUD_RATE[baudrate]
        except KeyError:
            logging.error('Baud rate %d unsupported', baudrate)
            raise AllSkyException('Baud rate %d unsupported' % baudrate)

        ser = self.__ser

        # check communications first
        if not check_communications(ser):
            logging.error('Initial communications test failed')
            raise AllSkyException('Initial communications test failed')

        # send baud rate change command
        data = BAUD_RATE[baudrate] + checksum(BAUD_RATE[baudrate])
        self.serial_tx(data)

        # read back anything it sends us
        data = self.serial_rx(100)
        logging.debug('RX: %s', bufdump(data))

        # switch baudrate
        ser.setBaudrate(baudrate)

        # clear out any stale data in the serial port buffers
        data = self.serial_rx(100)
        logging.debug('RX: %s', bufdump(data))

        # send the next part of the sequence
        # NOTE: no checksum!
        self.serial_tx('Test')

        # clear out any stale data in the serial port buffers
        data = self.serial_rx(100)
        logging.debug('RX: %s', bufdump(data))

        # send the next part of the sequence
        # NOTE: no checksum!
        self.serial_tx('k')

        # clear out any stale data in the serial port buffers
        data = self.serial_rx(100)
        logging.debug('RX: %s', bufdump(data))

        # check communications again, being more liberal this time
        if not check_communications(ser, count=10, required_successes=3):
            logging.debug('Final communications test failed')
            raise AllSkyException('Final communications test failed')

    def send_command(self, command):
        '''
        Send a command to the camera and read back and check the checksum

        command -- the command to send

        return -- True on success, False otherwise
        '''
        ser = self.__ser

        csum = checksum(command)
        data = command + csum

        serial_tx(ser, data)
        data = serial_rx(ser, 1)

        if data != csum:
            logging.error('command %s csum %s rxcsum %s', bufdump(command), bufdump(csum), bufdump(data))

        return data == csum

    def serial_rx(self, nbytes, timeout=0.5):
        '''Low level method to receive some bytes from the camera'''
        return serial_rx(self.__ser, nbytes, timeout)

    def serial_tx(self, data, timeout=0.5):
        '''Low level method to transmit some bytes to the camera'''
        return serial_tx(self.__ser, data, timeout)

    def serial_rx_until(self, terminator, timeout=5.0):
        '''Low level method to receive some bytes from the camera until a terminating byte is received'''
        return serial_rx_until(self.__ser, terminator, timeout)

    def firmware_version(self):
        '''
        Request firmware version information from the camera and
        return it in the string format described in the manual.

        Example: R1.30 - "Release v1.30"
        Example: T1.16 - "Test v1.16"
        '''
        self.send_command(GET_FVERSION)
        data = self.serial_rx(2)

        # convert to integers
        data = array.array('B', data)

        version_type = (data[0] & 0x80) and 'T' or 'R'
        version_major = (data[0] & 0x7f)
        version_minor = (data[1])

        return '%s%d.%d' % (version_type, version_major, version_minor)

    def serial_number(self):
        '''
        Returns the camera's serial number (9 byte string)
        '''
        self.send_command(GET_SERIAL)
        data = self.serial_rx(9)
        return data

    def open_shutter(self):
        '''
        Open the camera shutter, then de-energize the shutter motor.
        '''
        self.send_command(OPEN_SHUTTER)
        time.sleep(0.2)
        self.send_command(DE_ENERGIZE)

    def close_shutter(self):
        '''
        Close the camera shutter, then de-energize the shutter motor.
        '''
        self.send_command(CLOSE_SHUTTER)
        time.sleep(0.2)
        self.send_command(DE_ENERGIZE)

    def activate_heater(self):
        '''
        Activate the built in heater
        '''
        self.send_command(HEATER_ON)

    def deactivate_heater(self):
        '''
        Deactivate the built in heater
        '''
        self.send_command(HEATER_OFF)

    def calibrate_guider(self):
        '''
        Request the camera to automatically calibrate the guider.
        return -- the string of calibration data sent back from camera
        '''
        self.send_command(CALIBRATE_GUIDER)
        return self.serial_rx_until(TERMINATOR, 240.0)

    def autonomous_guide(self):
        '''
        Begin autonomous guiding process
        return -- Data sent back from camera
        '''
        self.send_command(AUTO_GUIDE)
        return self.serial_rx_until(TERMINATOR, 240.0)

    def take_image(self, exposure=1.0):
        '''
        Run an exposure of the CCD.
        exposure -- exposure time in seconds
        return -- the timestamp that the exposure was taken in ISO format
        '''
        # Camera exposure time works in 100us units, with a maximum value
        exptime = min(exposure / 100e-6, MAX_EXPOSURE)

        exp = struct.pack('I', exptime)[:3]
        com = TAKE_IMAGE + exp[::-1] + chr(0x00) + chr(0x01)

        timestamp = datetime.datetime.utcnow()

        logging.debug('Exposure begin: command %s', hexify(com))
        self.send_command(com)

        # wait until the exposure is finished, with plenty of timing slack to
        # handle hardware latency on very short exposures (measurements show
        # that the camera has ~1 second of hardware latency)
        timeout = exposure + 5.0
        self.serial_rx_until(EXPOSURE_DONE, timeout)
        logging.debug('Exposure complete')

        return timestamp

    def __xfer_image_block(self, expected=4096, ignore_csum=False, tries=10):
        '''
        Get one 'block' of image data. At full frame the camera returns image
        data in chunks of 4096 pixels. For different imaging modes this value
        will change, but the caller can simply change the value of expected.

        This routine will automatically retry if a communication error occurs,
        up to the maximum number of retries specified.

        expected -- Number of pixels to retrieve
        ignore_csum -- Always pass checksum without checking (for debug only)
        tries -- The maximum number of tries before aborting transfer

        return -- the raw pixel data from the camera as a Python array of unsigned bytes
        '''
        for i in xrange(tries):
            logging.debug('Get Image Block: try %d', i)

            # not the first try, transmit checksum error so the camera will try again
            if i > 0:
                self.serial_tx(CSUM_ERROR)

            # calculate number of bytes and expected transfer time
            nbytes = expected * PIXEL_SIZE
            timeout = serial_timeout_calc(self.__ser, nbytes)

            # read the data and checksum
            logging.debug('Get Image Block: attempt to read %d bytes in %s seconds', nbytes, timeout)
            data = self.serial_rx(nbytes, timeout)
            csum_byte = self.serial_rx(1)
            logging.debug('Get Image Block: finished reading data')

            # not enough bytes, therefore transfer failed
            if len(data) != nbytes:
                logging.debug('Not enough data returned before timeout')
                continue

            # calculate XOR-based checksum, convert data to ints, then xor
            # Python has some weird sign extension thing, hence the extra bitwise ands
            data = array.array('B', data)
            csum = 0
            for byte in data:
                csum ^= (byte & 0xff)
                csum &= 0xff

            # convert csum_byte to an integer
            csum_byte = ord(csum_byte)

            logging.debug('Checksum from camera: %.2x', csum_byte)
            logging.debug('Checksum calculated: %.2x', csum)

            # enough bytes and csum valid, exit the loop
            if ignore_csum or csum == csum_byte:
                logging.debug('Checksum OK, successfully received block')
                self.serial_tx(CSUM_OK)
                return data

            # enough bytes and csum invalid, try again
            logging.debug('Checksum ERROR')

        # too many retries passed, abort
        logging.debug('Get Image Block: retries exhausted, abort transfer')
        self.serial_tx(STOP_XFER)
        raise AllSkyException('Too many errors during image sub-block transfer')

    def xfer_image(self, progress_callback=None):
        '''
        Fetch an image from the camera

        progress_callback -- Function to be called after each block downloaded

        return -- the raw pixel data from the camera as a Python array of unsigned bytes
        '''
        # Calculate number of sub-blocks expected
        blocks_expected = (640 * 480) / 4096

        # Download Image
        self.send_command(XFER_IMAGE)

        data = array.array('B')
        blocks_complete = 0
        for _ in range(blocks_expected):
            data += self.__xfer_image_block()
            blocks_complete += 1
            logging.debug('Received block %d', blocks_complete)
            if progress_callback is not None:
                progress_callback(float(blocks_complete) / blocks_expected * 100)

        logging.debug('Image download complete')
        return data
