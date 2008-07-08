#!/usr/bin/env python
# Encoding: iso-8859-1
# -----------------------------------------------------------------------------
# Project   : Railways - Comet Example
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 14-Jun-2006
# Last mod  : 14-Jun-2006
# -----------------------------------------------------------------------------

import os, time
from railways import *

__doc__ = """\
This example shows how to do implement a Comet service  with Railways. 
"""
# ------------------------------------------------------------------------------
#
# MAIN COMPONENT
#
# ------------------------------------------------------------------------------

class Main(Component):

	def init( self ):
		self.pipes = {}

	@on(GET="lib/{path:any}")
	def lib( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		# This is really only useful when running standalone, as with normal
		# setups, this data should be served by a more poweful web server, with
		# caching and load balancing.
		return request.localFile(self.app().localPath("../../Library/" + path))

	@on(GET="/")
	@display("index")
	def main( self, request ):
		pass

	@on(GET="/api/processes")
	def processes( self, request ):
		def push():
			last_status = -1
			value       = 0
			while True:
				yield "<pre>%s</pre>" % (os.popen("ps -el").read())
				time.sleep(5)
		return request.respondMultiple(push())

	def ensurePipe( self, n ) :
		k = str(n)
		return self.pipes.setdefault(k,[])

	@on(GET="/pipe/{n:number}/read")
	def onPipeRead( self, request ):
		def condition()
		def stream():
			while True:
				yield
				

	def onPipeWrite( self, request ):
	@on(GET="/api/date")

	def date( self, request ):
		def push():
			last_status = -1
			value       = 0
			while True:
				yield "<pre>%s</pre>" % (os.popen("date").read())
				time.sleep(1)
		return request.respondMultiple(push())

if __name__ == "__main__":
	app  = Application(Main())
	name = os.path.splitext(os.path.basename(__file__))[0]
	run( app=app, name=name, method=STANDALONE, port=8000 )

# EOF - vim: tw=80 ts=4 sw=4 noet
