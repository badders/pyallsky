from allsky import AllSkyCamera
import serial
import argparse, sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--device', help='Path to serial device', default='/dev/usbserial')
    parser.add_argument('-e', '--exposure', type=float, help='Exposure time in seconds', default=1.0)
    parser.add_argument('path', help='Filename to save image')
    args = parser.parse_args()

    try:
        cam = AllSkyCamera(args.device)
        cam.open_shutter()
        cam.de_energize_shutter()
        print('Downloading image ...')
        image = cam.get_image(exposure=args.exposure)
        image.writeto(args.path)
    except serial.serialutil.SerialException as err:
        print(str(err))
        sys.exit(2)

if __name__ == '__main__':
    main()
