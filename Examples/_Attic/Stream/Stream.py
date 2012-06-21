#!/usr/bin/env python
# Encoding: iso-8859-1
# -----------------------------------------------------------------------------
# Project   : Retro - Stream Example
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 14-Jul-2008
# Last mod  : 14-Jul-2006
# -----------------------------------------------------------------------------

import os, time, threading
from retro import *

__doc__ = """\
This example shows how to do implement a Comet service  with Retro. 
"""

PAGE = """
<html>
	<head>
		<title>Retro | Comet Example</title>
	</head>
	<body>
		<h3>Stream Reading</h3>
		<iframe src="/api/stream/read" style="width:100%;height:450px" />
		<br />
	</body>
</html>
"""

# ------------------------------------------------------------------------------
#
# MAIN COMPONENT
#
# ------------------------------------------------------------------------------

class Counter:

	def __init__( self ):
		self.data         = time.time()
		self.dataWritten  = Event()
		self._mainthread  = threading.Thread(target=self.run)
		self._mainthread.start()

	def run( self ):
		while True:
			#print "ITERATE"
			self.data = time.time()
			self.dataWritten()
			time.sleep(1)
			self.data = None

	def hasData( self ):
		return self.data != None

COUNTER = Counter()

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
	def main( self, request ):
		return request.respond(PAGE,contentType="text/html")

	def ensurePipe( self, n ):
		k = str(n)
		if self.pipes.has_key(k):
			return self.pipes[k]
		else:
			p = Pipe()
			self.pipes[k] = p
			return p

	@on(GET="/api/stream/read")
	def onStreamRead( self, request ):
		def stream():
			while True:
				value = str(COUNTER.data) + "<br />"
				yield value
				yield RendezVous(expect=1).joinEvent(COUNTER.dataWritten)
		# Continuous production/polling mode:
		# return request.respond(stream()).produceOn(pipe.dataWritten)
		# Burst/event-based production mode:
		return request.respond(stream())

if __name__ == "__main__":
	app  = Application(Main())
	name = os.path.splitext(os.path.basename(__file__))[0]
	run( app=app, name=name, method=STANDALONE, port=8000, withReactor=True )
	REACTOR.debugMode = True

# EOF - vim: tw=80 ts=4 sw=4 noet
