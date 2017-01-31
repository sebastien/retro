#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Hello World
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 08-Aug-2008
# Last mod  : 08-Aug-2008
# ----------------------------------------------------------------------------

from retro import *

class Main(Component):
	"""To use this, go to <http://localhost:8080/say/hello>"""

	@on(GET="{any:rest}")
	def saySomething( self, request, any ):
		return request.respond("Hello, World!")

run( components=[Main()] )

# EOF
