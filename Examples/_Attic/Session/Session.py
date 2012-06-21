#!/usr/bin/env python
# Encoding  : iso-8859-1
# -----------------------------------------------------------------------------
# Project   : Sessions Example
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 08-Aug-2006
# Last mod  : 06-Mar-2008
# -----------------------------------------------------------------------------

from retro import *

__doc__ = """\
This example shows how to do manage sessions
"""

HTML_TEMPLATE = """\
<html xmlns:py="http://purl.org/kid/ns#">
<head>
    <script language="javascript" type="text/javascript" src="/lib/prototype.js"></script>
    <script language="javascript" type="text/javascript" src="/lib/retro.js"></script>
    <link rel="stylesheet" media="screen" type="text/css" href="/lib/screen.css" />
  </head>
  <body>
    <div id="title">
      <h1>Retro</h1>
      <h2>Session example</h2>
    </div>
     %s
  </body>
</html>"""

HTML_LOGIN = HTML_TEMPLATE % ("""
<p>Enter your login and password!</p>
<form action="user/login" method="POST">
<input type="text"     name="login"    value="login"/>
<input type="password" name="password" value="password"/>
<input type="submit"   value="login"/>
</form>
""")

HTML_LOGGED = HTML_TEMPLATE % ("""
<p>Hello, <b>%s</b>, you are logged in !</p>
<form action="user/logout" method="GET">
<input type="submit"   value="disconnect"/>
</form>
<p>You are now granted access to the <a href='restricted'>restricted area</a>.</p>
<p>Cookies:</p>
<pre>%s</pre>
""")

HTML_RESTRICTED = HTML_TEMPLATE % ("""
<p>You were granted to the restricted area.</p>
<form action="user/logout" method="GET">
<input type="submit"   value="disconnect"/>
</form>
""")

# ------------------------------------------------------------------------------
#
# USER COMPONENT
#
# ------------------------------------------------------------------------------

class Main(Component):

	@predicate
	def isAuthenticated( self, request ):
		return request.session("logged") == 1

	@on(GET="/")
	def main( self, request ):
		if self.isAuthenticated(request):
			return request.respond(HTML_LOGGED % ( request.session('login'), request.cookies() ))
		else:
			return request.respond(HTML_LOGIN)

	@when('isAuthenticated')
	@on(GET="/restricted")
	def restricted( self, request ):
		return request.respond(HTML_RESTRICTED)

	@on(POST="/user/login")
	def login( self, request ):
		request.session("logged", 1)
		request.session("login", request.get('login'))
		return request.bounce()

	@on(GET="/user/logout")
	def logout( self, request ):
		request.session("logged", 0)
		return request.bounce()

	# RESOURCES
	# ____________________________________________________________________________

	@on(GET="lib/{path:any}")
	def lib( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		return request.respondFile(self.app().localPath("../../Library/" + path))

def setupStack( stack ):
	"""Sets up the WSGI stack, by adding a session middleware"""
	from beaker.middleware import SessionMiddleware
	stack = SessionMiddleware(stack,type='dbm', data_dir=".")
	return stack

if __name__ == "__main__":
	print "python Session.py [beaker|flup]"
	print "       runs the example with 'beaker' or 'flup' session back-end\n"
	args = sys.argv
	if len(args) == 2 and args[1].lower() == "beaker":
		run(
			app          = Application(Main()).configure(session="BEAKER"),
			name         = os.path.splitext(os.path.basename(__file__))[1],
			method       = STANDALONE,
			processStack = setupStack
		)
	else:
		run(
			app          = Application(Main()).configure(session="FLUP"),
			name         = os.path.splitext(os.path.basename(__file__))[1],
			method       = STANDALONE,
		)

# EOF - vim: tw=80 ts=4 sw=4 noet
