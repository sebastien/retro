#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Retro - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 15-Oct-2009
# -----------------------------------------------------------------------------

import sys, os, thread
import wsgi
from wsgi import REACTOR, onShutdown, onError
from core import asJSON
from web  import on, ajax, expose, display, predicate, when, cache, \
Component, Application, \
Dispatcher, Configuration, ValidationError, Event, RendezVous, \
KID, CHEETAH, DJANGO

# FIXME: Add support for stackable applications

__version__ = "0.9.5"
__doc__     = """\
This is the main Retro module. You can generally do the following:

>	from retro import *
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

__pychecker__ = "unusednames=executionInfo,status"

# ------------------------------------------------------------------------------
#
# DEPENDENCIES
#
# ------------------------------------------------------------------------------

DEFAULT_PORT    = 8000
DEFAULT_ADDRESS = "0.0.0.0"
FLUP = FCGI = WSGIREF = SCGI = STANDALONE = None
CGI  = True
STANDALONE = "STANDALONE"

try:
	FLUP_FCGIServer = None
	FLUP_SCGIServer = None
	from flup.server.fcgi import WSGIServer as FLUP_FCGIServer
	from flup.server.scgi import WSGIServer as FLUP_SCGIServer
	FLUP = "FLUP"
	FCGI = "FLUP_FCGI"
	SCGI = "FLUP_SCGI"
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

OPT_PORT     = "Specifies the port on which the server should be run"
OPT_PREFIX   = "Prefix to prepend to the URLs"

def command( args, **extra ):
	if type(args) not in (type([]), type(())): args = [args]
	from optparse import OptionParser
	# We create the parse and register the options
	oparser = OptionParser(version="Retro " + __version__)
	oparser.add_option("-p", "--port", action="store", dest="port",
		help=OPT_PORT, default=DEFAULT_PORT)
	oparser.add_option("-P", "--prefix", action="store", dest="prefix",
		help=OPT_PREFIX, default=None)
	# We parse the options and arguments
	options, args = oparser.parse_args(args=args)
	extra["prefix"]   = options.prefix
	extra["port"]     = int(extra.get("port") or options.port)
	run(**extra)

def run( app=None, components=(), method=STANDALONE, name="retro",
root = ".", resetlog=False, address="", port=None, prefix='', async=False,
sessions=False, withReactor=None, processStack=lambda x:x, runCondition=lambda:True,
onError=None ):
	"""Runs this web application with the given method (easiest one is STANDALONE),
	with the given root (directory from where the web app-related resource
	will be resolved).

	This function is the 'main' for your web application, so this is basically
	the last call you should have in your web application main."""
	if async:
		async = False
		return thread.start_new_thread(run,(),locals())
	if not (withReactor is None):
		wsgi.USE_REACTOR = withReactor
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
	config.setdefault("root",    root)
	config.setdefault("name",    name)
	config.setdefault("logfile", name + ".log")
	if resetlog: os.path.unlink(config.logfile())
	# We set the configuration
	app.config(config)
	# And start the application
	app.start()
	# NOTE: Maybe we should always print it
	#print app.config()
	# We start the WSGI stack
	stack = app._dispatcher
	stack = processStack(stack)
	# == FCGI (Flup-provided)
	#
	if method == FCGI:
		if not has(FLUP):
			raise ImportError("Flup is required to run FCGI")
		fcgi_address = address or config.get("address")
		fcgi_port    = port or config.get("port")
		if fcgi_port and fcgi_address:
			server = FLUP_FCGIServer(stack, bindAddress=(fcgi_address, fcgi_port))
		elif fcgi_address:
			server = FLUP_FCGIServer(stack, bindAddress=fcgi_address)
		else:
			server = FLUP_FCGIServer(stack)
		server.run()
	#
	# == SCGI (Flup-provided)
	#
	elif method == SCGI:
		if not has(FLUP):
			raise ImportError("Flup is required to run SCGI")
		fcgi_address = address or config.get("address")
		fcgi_port    = port or config.get("port")
		if fcgi_port and fcgi_address:
			server = FLUP_SCGIServer(stack, bindAddress=(fcgi_address, fcgi_port))
		elif fcgi_address:
			server = FLUP_SCGIServer(stack, bindAddress=fcgi_address)
		else:
			server = FLUP_SCGIServer(stack)
		server.run()
	#
	# == CGI
	#
	elif method == CGI:
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
			environ["com.saddi.service.session"] = sessions
		def start_response( status, headers, executionInfo=None ):
			for key, value in headers:
				print "%s: %s" % (key, value)
			print
		# FIXME: This is broken
		res = "".join(tuple(self.dispatcher(environ, start_response)))
		print res
		if sessions:
			sessions.close()
	#
	# == STANDALONE (WSGIREF)
	#
	# elif method == STANDALONE_WSGIREF:
	# 	server_address     = (
	# 		address or app.config("address") or DEFAULT_ADDRESS,
	# 		port or app.config("port") or DEFAULT_PORT
	# 	)
	# 	server = WSGIServer(server_address, WSGIRequestHandler)
	# 	server.set_app(stack)
	# 	socket = server.socket.getsockname()
	# 	print "WSGIREF server listening on %s:%s" % ( socket[0], socket[1])
	# 	try:
	# 		while runCondition: server.handle_request() 
	# 	except KeyboardInterrupt:
	# 		print "done"
	#
	# == STANDALONE (Retro WSGI server)
	#
	else:
		server_address     = (
			address or app.config("address") or DEFAULT_ADDRESS,
			port or app.config("port") or DEFAULT_PORT
		)
		stack.fromRetro = True
		stack.app          = lambda: app
		server = wsgi.WSGIServer(server_address, stack)
		wsgi.onError(onError)
		socket = server.socket.getsockname()
		print "Retro embedded server listening on %s:%s" % ( socket[0], socket[1])
		try:
			while runCondition():
				server.handle_request()
		except KeyboardInterrupt:
			print "done"
# EOF
