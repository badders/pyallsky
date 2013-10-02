from allsky import AllSkyCamera
import serial
import argparse, sys


def capture_image(device, exposure_time, savefile):
    try:
        cam = AllSkyCamera(device)
        cam.open_shutter()
        print('Downloading image ...')
        image = cam.get_image(exposure=exposure_time)
        image.writeto(savefile)
    except serial.serialutil.SerialException as err:
        print(str(err))
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--device', help='Path to serial device', default='/dev/usbserial')
    parser.add_argument('-e', '--exposure', type=float, help='Exposure time in seconds', default=1.0)
    parser.add_argument('path', help='Filename to save image')
    args = parser.parse_args()
    capture_image(args.device, args.exposure, args.path)


if __name__ == '__main__':
    main()
