#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Accounts
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 18-Sep-2006
# Last mod  : 18-Sep-2006
# -----------------------------------------------------------------------------

import time
from railways import *
from prevail import *
from prevail.web import expose

__doc__ = """\
This example shows how to do use the burst channel to group many small requests
into one big request"""

class Rectangle(PersistentObject):

	def init(self):
		self.setSize(100, 100)
		self.setPosition(0,0)

	@attribute(Integer)
	def x( self, x): pass

	@attribute(Integer)
	def y( self, y): pass

	@attribute(Integer)
	def w( self, w): pass

	@attribute(Integer)
	def h( self, h): pass

	def setSize( self, w, h ):
		self.w(w)
		self.h(h)

	def setPosition( self, x, y ):
		self.x(x)
		self.y(y)

# ------------------------------------------------------------------------------
#
# MAIN COMPONENT
#
# ------------------------------------------------------------------------------

class Main(Component):

	def init( self ):
		self._counter = 0
		self._uploads = {}
		self._elements = {}
		self._values   = {}

	@on(GET="lib/{path:any}")
	def lib( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		# This is really only useful when running standalone, as with normal
		# setups, this data should be served by a more poweful web server, with
		# caching and load balancing.
		localpath = self.app().localPath("lib/" + path)
		libpath   = self.app().localPath("../../Library/" + path)
		if not os.path.exists(localpath): localpath = libpath
		return request.localFile(localpath)

	@on( GET="/")
	@display("index")
	def main( self, request ):
		"""Serves the main template file"""
		pass

	# This method as well as the following are simply for testing the burst
	# channel, so that we ensure that setting and getting a value will work, and
	# that POST and GET request will work as well.
	@on( POST="/values")
	def setvalue( self, request ):
		"""Sets a value"""
		self._values[request.get("name")]=request.get("value")
		return request.bounce()

	@ajax( GET="/values" )
	def getvalues( self ):
		return self._values

if __name__ == "__main__":
	STORAGE = Storage(classes=[Rectangle])
	run(
			app        = Application(components=(Main(), expose(STORAGE))),
			name       = os.path.splitext(os.path.basename(__file__))[0],
			method     = STANDALONE
	)

# EOF
