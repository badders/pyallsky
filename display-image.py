from allsky import AllSkyCamera
import matplotlib
matplotlib.use('Qt4Agg')
import matplotlib.pyplot as plt
import aplpy

cam = AllSkyCamera('/dev/tty.usbserial')

storage = '/home/allsky/images'

print cam.firmware_version()

image = cam.get_image(exposure=0.1)

gc = aplpy.FITSFigure(image)

gc.show_grayscale()

plt.show()
