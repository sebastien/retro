#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 27-Jul-2006
# Last mod  : 27-Jul-2008
# -----------------------------------------------------------------------------

import os, sys, time, webbrowser
from os.path import abspath, dirname, join
from retro import *
from retro.wsgi import SERVER_ERROR_CSS

__doc__ = """
The 'record' module provides the 'Record' component that simply prints (and
optionanly records) the incoming requests.
"""

# ------------------------------------------------------------------------------
#
# RECORD
#
# ------------------------------------------------------------------------------

class Record(Component):
	"""Records the requests made to the given URL."""

	def __init__( self, prefix="/record" ):
		Component.__init__(self, name="Record")
		self.PREFIX   = prefix
		self.out      = sys.stdout

	def log( self, data ):
		sys.stdout.write(data)

	@on(GET="")
	@on(GET="/{rest}")
	def catchAll( self, request, rest=None ):
		self.log ("----8<---- START REQUEST ----------\n")
		self.log (request.environ("extra.request"))
		self.log ("".join(request.environ("extra.headers")))
		if request.data(): self.log (request.data())
		self.log ("----8<----  END REQUEST  ----------\n")
		return request.respond("OK")

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------


def run( args ):
	if type(args) not in (type([]), type(())): args = [args]
	from optparse import OptionParser
	# We create the parse and register the options
	oparser = OptionParser(version="Retro[+record]")
	oparser.add_option("-p", "--port", action="store", dest="port",
		help=OPT_PORT, default="8000")
	oparser.add_option("-f", "--files", action="store_true", dest="files",
		help="Server local files", default=None)
	# We parse the options and arguments
	options, args = oparser.parse_args(args=args)
	app  = Application(components=[Record()])
	import retro
	return retro.run(app=app,sessions=False,port=int(options.port))

# -----------------------------------------------------------------------------
#
# Main
#
# -----------------------------------------------------------------------------

if __name__ == "__main__":
	run(sys.argv[1:])

# EOF
