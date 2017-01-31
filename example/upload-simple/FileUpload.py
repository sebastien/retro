#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 08-Aug-2012
# Last mod  : 08-Aug-2012
# -----------------------------------------------------------------------------

import time, string, hashlib
from retro import *

# ------------------------------------------------------------------------------
#
# COMPONENT
#
# ------------------------------------------------------------------------------

class Main(Component):

	def __init__( self ):
		Component.__init__(self)
		# We'll store uploads by id here
		self.uploads = dict()

	@on(GET="")
	@on(GET="{path:any}")
	def get(self, request, path=None):
		if not path: path = "index.html"
		return request.respond(self.app().load(path))

	@on(POST="upload")
	def upload( self, request ):
		upload_id    = request.param("id")
		block_size   = request.param("blocksize") or (64 * 1024)
		result       = dict(progress=0,data=None)
		print request.param("id")
		self.uploads[upload_id] = result
		# FIXME: Should make sure that the data is saved to disk
		# to avoid bloating the memory with large uploads
		def stream():
			yield "<html><body><ul>"
			while not request.isLoaded():
				data               = request.load(block_size)
				progress           = request.loadProgress()
				result["progress"] = progress
				self.uploads[upload_id] = result
				print "Upload progress", progress
				yield "<li>%s%%</li>" % (progress)
				#time.sleep(1)
			uploaded_file = request.file("data")
			print "Uploaded SHA-1", hashlib.sha256(uploaded_file.data).hexdigest()
			yield "</ul></body></html>"
		return request.respond(stream())

	@on(GET="upload/progress")
	def uploadProgress(self, request):
		upload_id  = request.param("id")
		if self.uploads.has(upload_id):
			return request.returns(self.uploads.get(upload_id))
		else:
			return request.notFound()

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


