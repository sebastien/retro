#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Railways Test Suite
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# -----------------------------------------------------------------------------
# Creation  : 18-Mar-2007
# Last mod  : 18-Mar-2007
# -----------------------------------------------------------------------------

import os
from railways import *

PORT        = 8100
ROOT        = os.path.dirname(os.path.abspath(__file__))
TEMPLATES   = os.path.abspath(os.path.join(ROOT, "data"))

INDEX = """
<html>
	<body onload="updateImages()">
	Here is an image
	<img id="img1" alt="no image" />
	<img id="img2" alt="no image" />
	<img id="img3" alt="no image" />
	<script>
	function updateImages(){
		document.img1.setAttribute("src", "images/image1.jpg")
		document.img2.setAttribute("src", "images/image2.jpg")
		document.img3.setAttribute("src", "images/image2.jpg")
	}
	</script>
	</body>
</html>
"""

# ------------------------------------------------------------------------------
#
# TEST COMPONENT
#
# ------------------------------------------------------------------------------

class Main(Component):

	@on(GET="/images/{f:file}")
	def getimage( self, request, f ):
		return request.localFile( "data/" + f)

	@on(GET="/")
	def main( self, request ):
		return request.respond(INDEX)

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------

if __name__ == "__main__":
	# We update the settings module
	app = Application(components=[Main()]).configure(templates=TEMPLATES)
	run(app,name="Railways test",method=STANDALONE, port=PORT, root=ROOT)

# EOF
