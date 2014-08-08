#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 09-May-2013
# Last mod  : 09-May-2013
# -----------------------------------------------------------------------------

import time, string, hashlib
from retro import *
from retro.contrib.upload import Uploader

# ------------------------------------------------------------------------------
#
# COMPONENT
#
# ------------------------------------------------------------------------------

class Main(Component):

	def __init__( self ):
		Component.__init__(self)
		self.uploader = Uploader()

	@on(GET="")
	@on(GET="{path:any}")
	def get(self, request, path=None):
		if not path: path = "index.html"
		return request.respond(self.app().load(path))

	@on(POST="upload")
	def upload( self, request ):
		upload_id    = request.param("id")
		block_size   = request.param("blocksize") or (64 * 1024)
		upload       = self.uploader.upload(request, upload_id, block_size)
		upload.onCompleted(self.onUploadComplete)
		return request.respond((
			"%s bytes read (%f%%)<br>" % (_.lastBytesRead, _.progress) for _ in upload
		))

	@expose(GET="upload/progress?{params}")
	def uploadProgress(self, params):
		return self.uploader.get(params["id"])

	def onUploadComplete( self, upload ):
		for name in upload.request.files():
			file = upload.request.file(name)
			name = "uploaded-" + file.name
			print ("Saving uploaded file to: {0}".format(name))
			with open(name, "wb") as f:
				f.write(file.data)

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------

def generate_file(length):
	res = ""
	while len(res) < length:
		with file(__file__) as f:
			d = f.read()
			rest = length - len(res)
			if len(d) > rest:
				res += d[:rest]
			else:
				res += d
	data = res
	sig  = hashlib.sha256(data).hexdigest()
	name = "%s-%s.data.tmp" % (length, sig)
	print "Generating data file", name
	with file(name, "wb") as f:
		f.write(data)

if __name__ == "__main__":
	import glob
	# We generate a 5Mb file
	if not glob.glob("*.data.tmp"):generate_file(length=5000 * 1024)
	main = Main()
	run(
		app        = Application(main),
		name       = os.path.splitext(os.path.basename(__file__))[1],
		method     = STANDALONE,
		sessions   = False,
	)

# EOF
