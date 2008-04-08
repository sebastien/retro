#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Hello World
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 08-Aug-2008
# Last mod  : 08-Aug-2008
# ----------------------------------------------------------------------------

from railways import *

class Main(Component):
	"""To use this, go to <http://localhost:8080/say/hello>"""

	@on(GET="/say/{something:rest}")
	def saySomething( self, request, something ):
		return request.respond(
			"<html><body>You said: <b>%s</b></body></html>" % (something)
		)

run( components=[Main()] )

# EOF
