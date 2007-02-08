#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Railways - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 05-Jan-2007
# -----------------------------------------------------------------------------

__doc__ = """
This script starts a Railways/Py web server that acts as a local proxy to the
current filesystem or given directory ."""

import os, sys, StringIO
from railways import *
from sugar import sugar

PORT               = 8080

# ------------------------------------------------------------------------------
#
# PROXY CLASS
#
# ------------------------------------------------------------------------------

class Main(Component):

	def start( self, root=None ):
		if not root: root = os.path.abspath(".")
		else: root = os.path.abspath(root)
		self._localroot = root
		
	@on(GET_POST="/{path:any}")
	def local( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		lpath = self.app().localPath(os.path.join(self._localroot, path))
		#try:
		if True:
			if os.path.isdir(path):
				return request.respond(self.listdir(lpath,path))
			elif path.endswith(".scjs") or path.endswith(".sjs"):
				output = StringIO.StringIO()
				sugar.run(["-m", lpath], output)
				res = "" + output.getvalue()
				return request.respond(content=res)
			else:
				try:
					return request.localfile(lpath)
				except:
					return request.respond(status=404)
		#except:
		#	return request.respond(status=404)

	def listdir( self, lpath, path ):
		res = "<html><body><h1>Listing of %s</h1><ul>" % (path)
		for file in os.listdir(lpath):
			res += "<li><a href='%s/%s'>%s</a></li>" % (os.path.basename(path), file, file)
		res += "</ul></body></html>"
		return res

if __name__ == "__main__":
	main = Main()
	main.start(*sys.argv[1:])
	run(
		app        = Application(main),
		name       = os.path.splitext(os.path.basename(__file__))[1],
		method     = STANDALONE,
		sessions   = False,
		port       = PORT
	)

# EOF
