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
# Last mod  : 22-Mar-2007
# -----------------------------------------------------------------------------

import sys, os, thread
from wsgi import WSGIServer
from core import asJSON
from web  import on, ajax, display, predicate, when, Component, Application, \
Dispatcher, Configuration, ValidationError, KID, CHEETAH, DJANGO

__version__ = "0.3.11"
__doc__     = """\
This is the main Railways module. You can generally do the following:

>	from railways import *
>	class MyCompoment(Component):
>	
>		@on("/index.html")
>		def main( self, request ):
>			return request.respond("Hello World!")
>	
>	if __name__ == "__main__":
>		run(Application(MyCompoment()), STANDALONE)

All important classes, functions and decorators are made available through this
module, so you should not have to bother with anything else."""

# ------------------------------------------------------------------------------
#
# DEPENDENCIES
#
# ------------------------------------------------------------------------------

FLUP = FCGI = WSGIREF = SCGI = STANDALONE = SESSIONS = None
CGI  = True
STANDALONE = "STANDALONE"

try:
	from flup.middleware.session import DiskSessionStore, SessionService, SessionMiddleware
	from flup.server.fcgi import WSGIServer as FLUP_FCGIServer
	from flup.server.scgi import WSGIServer as FLUP_SCGIServer
	FLUP = "FLUP"
	FCGI = "FLUP_FCGI"
	SCGI = "FLUP_SCGI"
	SESSIONS = True
except ImportError:
	FLUP = None

try:
	import wsgiref.simple_server
	WSGIREF    = "WSGIREF"
	STANDALONE_WSGIREF = "STANDALONE_WSGIREF"
except ImportError:
	WSGIREF = None
	STANDALONE_WSGIREF = None

FEATURES = filter(lambda x:x, (FLUP, FCGI, STANDALONE, WSGIREF, KID,))
def has( feature ):
	"""Tells if your Python installation has any of the following features:

	- FLUP for FCGI, SCGI servers
	- WSGIREF for standalone WSGI server
	- KID for template processing

	"""
	return feature in FEATURES

CONFIG = Configuration()

# ------------------------------------------------------------------------------
#
# RUNNING
#
# ------------------------------------------------------------------------------

def run( app=None, components=(), method=STANDALONE, name="railways", root = ".",
resetlog=False, address="", port=8000, prefix='', async=False, sessions=True ):
	"""Runs this web application with the given method (easiest one is STANDALONE),
	with the given root (directory from where the web app-related resource
	will be resolved).

	This function is the 'main' for your web application, so this is basically
	the last call you should have in your web application main."""
	if async:
		async = False
		return thread.start_new_thread(run,(),locals())
	if app == None: app = Application(prefix=prefix,components=components)
	else: map(app.register, components)
	# We set up the configuration if necessary
	config = app.config()
	if not config: config = Configuration(CONFIG)
	# Adjusts the working directory to basepath
	root = os.path.abspath(root)
	if os.path.isfile(root): root = os.path.dirname(root)
	# We set the application root to the given root, and do a chdir
	os.chdir(root)
	config.root(root)
	config.name(name)
	config.port(port)
	config.address(address)
	config.logfile(name + ".log")
	if resetlog: os.path.unlink(config.logfile())
	app.config(config)
	# We start the WSGI stack
	stack = app._dispatcher
	# And run the application in a specific server
	if sessions:
		if not has(FLUP):
			raise ImportError("Flup is required to enable session management.\nSet 'session' to False to avoid this.")
		session_store = DiskSessionStore()
	#
	# == FCGI (Flup-provided)
	#
	if method == FCGI:
		if not has(FLUP):
			raise ImportError("Flup is required to run FCGI")
		if sessions:
			stack  = SessionMiddleware(session_store,stack)
		server = FLUP_FCGIServer(stack, bindAddress=(config.address(), config.port()))
		server.run()
	#
	# == SCGI (Flup-provided)
	#
	elif method == SCGI:
		if not has(FLUP):
			raise ImportError("Flup is required to run SCGI")
		if sessions:
			stack  = SessionMiddleware(session_store,stack)
		server = FLUP_SCGIServer(stack, bindAddress=(config.address(), config.port()))
		server.run()
	#
	# == CGI
	#
	elif method == CGI:
		if sessions:
			session_service = SessionService(session_store, os.environ)
		environ         = {} ; environ.update(os.environ)
		# From <http://www.python.org/dev/peps/pep-0333/#the-server-gateway-side>
		environ['wsgi.input']        = sys.stdin
		environ['wsgi.errors']       = sys.stderr
		environ['wsgi.version']      = (1,0)
		environ['wsgi.multithread']  = False
		environ['wsgi.multiprocess'] = True
		environ['wsgi.run_once']     = True
		if environ.get('HTTPS','off') in ('on','1'):
			environ['wsgi.url_scheme'] = 'https'
		else:
			environ['wsgi.url_scheme'] = 'http'
		# FIXME: Don't know if it's the proper solution
		req_uri = environ["REQUEST_URI"]
		script_name = environ["SCRIPT_NAME"]
		if req_uri.startswith(script_name):
			environ["PATH_INFO"]  = req_uri[len(script_name):]
		else:
			environ["PATH_INFO"]  = "/"
		if sessions:
			environ["com.saddi.service.session"] = session_service
		def start_response( status, headers, executionInfo=None ):
			for key, value in headers:
				print "%s: %s" % (key, value)
			print
		res = "".join(tuple(self.dispatcher(environ, start_response)))
		print res
		if sessions:
			session_service.close()
	#
	# == STANDALONE (WSGIREF)
	#
	elif method == STANDALONE_WSGIREF:
		server_address = (address, port)
		server = WSGIServer(server_address, WSGIRequestHandler)
		if sessions:
			stack  = SessionMiddleware(session_store,stack)
		server.set_app(stack)
		socket = server.socket.getsockname()
		print "WSGIREF server listening on %s:%s" % ( socket[0], socket[1])
		try:
			while True: server.handle_request() 
		except KeyboardInterrupt:
			print "done"
	#
	# == STANDALONE (Railways WSGI server)
	#
	else:
		server_address = (address, port)
		if sessions:
			stack  = SessionMiddleware(session_store,stack)
		stack.fromRailways = True
		stack.app          = lambda: app
		server = WSGIServer(server_address, stack)
		socket = server.socket.getsockname()
		print "Railways embedded server listening on %s:%s" % ( socket[0], socket[1])
		try:
			while True: server.handle_request() 
		except KeyboardInterrupt:
			print "done"
# EOF
