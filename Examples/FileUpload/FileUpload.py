#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Accounts
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 07-Aug-2006
# Last mod  : 24-Aug-2006
# -----------------------------------------------------------------------------

import time
from railways import *

__doc__ = """\
This example shows how to do a file upload with a progress bar. A source of
inspiration was lighttpd [mod_uploadprogress]
(http://blog.lighttpd.net/articles/2006/08/01/mod_uploadprogress-is-back) which
was a helpful to setup this example.
"""
# ------------------------------------------------------------------------------
#
# MAIN COMPONENT
#
# ------------------------------------------------------------------------------

class Main(Component):

	def init( self ):
		self._counter = 0
		self._uploads = {}

	@on(GET="lib/{path:any}")
	def lib( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		# This is really only useful when running standalone, as with normal
		# setups, this data should be served by a more poweful web server, with
		# caching and load balancing.
		localpath = self.app().localPath(path)
		libpath   = self.app().localPath("../../Library/" + path)
		if not os.path.exists(localpath): localpath = libpath
		return request.respondFile(localpath)

	@on( GET="/")
	@display("index")
	def main( self, request ):
		"""Serves the main template file"""
		pass

	@on(GET="/api/upload/progress", POST="/api/upload/progress")
	def uploadStatus( self, request ):
		"""Returns the upload status"""
		# We get the reference to the upload from the current session
		key = request.session("uploading") 
		if not key and self._uploads:
			key = self._uploads.keys()[0]
		if key:
			value = self._uploads[key].loaded()
			return request.returns(value)
		else:
			return request.returns(0)

	@on(POST="/api/upload")
	def upload( self, request ):
		"""Serves the main template file"""
		key = "UPLOAD:" + str(time.time())
		self._uploads[key] = request
		request.session("uploading", key)
		def iterate(request=request):
			while not request.loaded() == 100:
				# We load by steps of 100kbytes
				request.load(100 * 1024)
				# And wait 1 sec (because it may be too fast !)
				time.sleep(1)
				yield ""
			request.session("uploading", "")
			del self._uploads[key]
		return request.respond(iterate())

if __name__ == "__main__":
	app  = Application(components=Main())
	name = os.path.splitext(os.path.basename(__file__))[0]
	run( app=app, name=name, method=STANDALONE, port=8000,async=False)

# EOF
