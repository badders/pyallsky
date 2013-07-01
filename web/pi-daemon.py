import web
import allsky
import glob
import datetime
import os

"""
Provide simple access to the AllSky camera throught a web interface.
n.b. create a director /static/images/ that links to the DOWNLOAD_DIR
"""

MAX_FILES = 150
DOWNLOAD_DIR = '/Users/tom/fits/'
DEVICE = '/dev/tty.usbserial'
DEFAULT_EXPOSURE = 0.1

urls = ('/', 'SBIG',
        '/view/(.*)', 'Viewer')

render = web.template.render('templates', base='base')

class Viewer:
    def GET(self, name):
        img_url = '/static/images/' + name
        return render.fitsview(img_url)

class SBIG:
    form = web.form.Form(
        web.form.Textbox('exposure', web.form.notnull,
                         description='Exposure Time (s):', value=DEFAULT_EXPOSURE),
        web.form.Button('Take Image'),
    )

    def getImageList(self):
        return map(os.path.basename, glob.glob(DOWNLOAD_DIR + '*.fits'))

    def __init__(self):
        self._camLock = False

    def GET(self):
        form = self.form()
        return render.SBIG(form, self.getImageList())

    def POST(self):
        form = self.form()
        if not form.validates() or self._camLock:
            return render.SBIG(form, self.getImageList())

        exposure = float(form.d.exposure)
        assert(exposure > 0 and exposure < 653.3599)
        self._camLock = True
        cam = allsky.AllSkyCamera(DEVICE)
        image = cam.get_image(exposure)
        image.writeto(DOWNLOAD_DIR + str(datetime.datetime.now()) + '.fits')
        self._camLock = False
        return render.SBIG(form, self.getImageList())

app = web.application(urls, globals(), autoreload=False)
app.run()
