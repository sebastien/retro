#!/usr/bin/env python
# Encoding: iso-8859-1
# -----------------------------------------------------------------------------
# Project   : Retro - Comet Example
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 14-Jun-2006
# Last mod  : 08-Jul-2006
# -----------------------------------------------------------------------------

import os, time, threading
from retro import *

__doc__ = """\
This example shows how to do implement a Comet service  with Retro. 
"""

READ = """
<html>
	<head>
		<title>Retro | Comet Example</title>
	</head>
	<body>
		<h3>Output</h3>
		<iframe src="/api/pipe/0/read" style="width:100%;height:450px" />
		<br />
	</body>
</html>
"""

WRITE = """
<html>
	<head>
		<title>Retro | Comet Example</title>
	</head>
	<body>
		<h3>Input</h3>
		<form action="/api/pipe/0/write" method="POST">
			<input name=message type=text value="Type something here" />
			<input type=submit value="Send" />
			<small><a href="/read">read here</a></small>
		<form>
	</body>
</html>
"""

# ------------------------------------------------------------------------------
#
# MAIN COMPONENT
#
# ------------------------------------------------------------------------------

class Pipe:

	def __init__( self ):
		self.data    = []
		self.dataWritten = Event()

	def hasData( self ):
		return len(self.data) > 0

	def write( self, data ):
		self.data.append(data)
		self.dataWritten.trigger()

	def read( self ):
		v = self.data[0]
		if len(v) > 1:
			self.data = self.data[1:]
		else:
			self.data = []
			self.hasDataEvent.clear()
		return v

class Main(Component):

	def init( self ):
		self.pipes = {}

	@on(GET="lib/{path:any}")
	def lib( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		# This is really only useful when running standalone, as with normal
		# setups, this data should be served by a more poweful web server, with
		# caching and load balancing.
		return request.respondFile(self.app().localPath("../../Library/" + path))

	@on(GET="/")
	def main( self, request ):
		return request.respond(WRITE,contentType="text/html")

	@on(GET="/read")
	def read( self, request ):
		return request.respond(READ,contentType="text/html")

	@on(GET="/api/processes")
	def processes( self, request ):
		def push():
			last_status = -1
			value       = 0
			while True:
				yield "<pre>%s</pre>" % (os.popen("ps -el").read())
				time.sleep(5)
		return request.respondMultiple(push())

	def ensurePipe( self, n ):
		k = str(n)
		if self.pipes.has_key(k):
			return self.pipes[k]
		else:
			p = Pipe()
			self.pipes[k] = p
			return p

	@on(GET="/api/pipe/{n:number}/read")
	def onPipeRead( self, request, n ):
		pipe = self.ensurePipe(n)
		def stream():
			while True:
				if pipe.hasData():
					value = str(pipe.read()) + "<br />"
					print ">>>", value
					yield value
				else:
					# FIXME: This takes considerable time when there is no
					# reactor bound
					yield RendezVous(expect=1).joinEvent(pipe.dataWritten)
		# Continuous production/polling mode:
		# return request.respond(stream()).produceOn(pipe.dataWritten)
		# Burst/event-based production mode:
		return request.respond(stream())

	@on(POST="/api/pipe/{n:number}/write")
	def onPipeWrite( self, request, n ):
		pipe = self.ensurePipe(n)
		pipe.write(request.param("message"))
		return request.bounce()

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
	run( app=app, name=name, method=STANDALONE, port=8000, withReactor=True )
	REACTOR.debugMode = True

# EOF - vim: tw=80 ts=4 sw=4 noet
