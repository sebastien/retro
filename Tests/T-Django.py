#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Retro Test Suite
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# -----------------------------------------------------------------------------
# Creation  : 22-Mar-2007
# Last mod  : 22-Mar-2007
# -----------------------------------------------------------------------------

import os
from railways import *

PORT        = 8100
ROOT        = os.path.dirname(os.path.abspath(__file__))
TEMPLATES   = os.path.abspath(os.path.join(ROOT, "data"))

# ------------------------------------------------------------------------------
#
# TEST COMPONENT
#
# ------------------------------------------------------------------------------

class Main(Component):

	@on(GET="/")
	@display("index.dtmpl", DJANGO)
	def main( self, request ):
		pass

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------

if __name__ == "__main__":
	# We update the settings module
	os.environ["DJANGO_SETTINGS_MODULE"] = os.path.splitext(os.path.basename(__file__))[0]
	app = Application(components=[Main()]).configure(templates=TEMPLATES)
	run(app,name="Retro test",method=STANDALONE, port=PORT, root=ROOT)

# EOF
