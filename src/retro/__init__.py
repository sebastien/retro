#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 02-Mar-2020
# -----------------------------------------------------------------------------

import sys, os, socket
from retro.core import asJSON, asPrimitive, cut, escapeHTML, NOTHING, \
	ensureBytes, ensureUnicode, ensureString, IS_PYTHON3, quote, unquote, Request, Response
from retro.web  import on, expose, predicate, when, restrict, cache, \
	Component, Application, \
	Dispatcher, Configuration, ValidationError, WebRuntimeError

# FIXME: Add support for stackable applications

__version__ = "2.9.0"
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
FLUP            = FCGI         = WSGIREF = SCGI = STANDALONE = None
CGI             = True
WSGI            = "WSGI"
STANDALONE      = "standalone"
AIO             = "aio"

# FIXME: We might want ot clean this
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

BJOERN = "bjoern"
ROCKET = "rocket"
GEVENT = "gevent"

FEATURES = [x for x in (FLUP, FCGI, STANDALONE, WSGIREF,) if x]
def has( feature ):
	"""Tells if your Python installation has any of the following features:

	- FLUP for FCGI, SCGI servers
	- WSGIREF for standalone WSGI server

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
		root = ".", resetlog=False, address="", port=None, prefix='', asynchronous=False,
		sessions=False, withReactor=None, processStack=lambda x:x, runCondition=lambda:True,
		onError=None ):
	"""Runs this web application with the given method (easiest one is STANDALONE),
	with the given root (directory from where the web app-related resource
	will be resolved).

	This function is the 'main' for your web application, so this is basically
	the last call you should have in your web application main."""
	if app == None:
		app = Application(prefix=prefix,components=components)
	else:
		for _ in components: app.register(_)
	# We set up the configuration if necessary
	config = app.config()
	if not config:
		config = Configuration(CONFIG)
	# Adjusts the working directory to basepath
	root = os.path.abspath(root)
	if os.path.isfile(root):
		root = os.path.dirname(root)
	# We set the application root to the given root, and do a chdir
	os.chdir(root)
	config.setdefault("root",    root)
	config.setdefault("name",    name)
	config.setdefault("logfile", name + ".log")
	if resetlog and os.path.exists(config.logfile()):
		os.unlink(config.logfile())
	# We set the configuration
	app.config(config)
	# And start the application
	app.start()
	# NOTE: Maybe we should always print it
	#print app.config
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
				print ("%s: %s" % (key, value))
			print ()
		# FIXME: This is broken
		res = "".join(tuple(self.dispatcher(environ, start_response)))
		print (res)
		if sessions:
			sessions.close()
	#
	# == GEVENT, BJOERN, ROCKET & WSGI
	#
	elif method in (GEVENT, BJOERN, ROCKET, WSGI):

		host   = config.get("host")
		port   = config.get("port")
		try:
			import reporter as logging
		except:
			import logging
		def application(environ, startResponse):
			# Gevent needs a wrapper
			if "retro.app" not in environ: environ["retro.app"] = stack.app
			return environ["retro.app"](environ, startResponse)
		def logged_application(environ, startResponse):
			logging.info("{0} {1}".format(environ["REQUEST_METHOD"], environ["PATH_INFO"]))
			if "retro.app" not in environ: environ["retro.app"] = stack.app
			return environ["retro.app"](environ, startResponse)
		if method == "GEVENT":
			try:
				from gevent import wsgi
			except ImportError:
				raise ImportError("gevent is required to run `gevent` method")
			# NOTE: This starts using gevent's WSGI server (faster!)
			wsgi.WSGIServer((host,port), application, spawn=None).serve_forever()
		elif method == BJOERN:
			try:
				import bjoern
			except ImportError:
				raise ImportError("bjoern is required to run `bjoern` method")
			bjoern.run(logged_application, host, port)
		elif method == ROCKET:
			try:
				import rocket
			except ImportError:
				raise ImportError("rocket is required to run `rocket` method")
			rocket.Rocket((host, int(port)), "wsgi", {"wsgi_app":application}).start()
		elif method == WSGI:
			# When using standalone WSGI, we make sure to wrap RendezVous objects
			# that might be returned by the handlers, and make sure we wait for
			# them -- we could use a callback version instead for specific web
			# servers.
			def retro_rendezvous_wrapper( environ, start_response, request=None):
				results = stack(environ, start_response, request)
				for result in results:
					if isinstance(result, RendezVous):
						result.wait()
						continue
					yield result
			retro_rendezvous_wrapper.stack = stack
			return retro_rendezvous_wrapper
	# == STANDALONE (WSGIREF)
	#
	# elif method == STANDALONE_WSGIREF:
	#	server_address     = (
	#		address or app.config("address") or DEFAULT_ADDRESS,
	#		port or app.config("port") or DEFAULT_PORT
	#	)
	#	server = WSGIServer(server_address, WSGIRequestHandler)
	#	server.set_app(stack)
	#	socket = server.socket.getsockname()
	#	print "WSGIREF server listening on %s:%s" % ( socket[0], socket[1])
	#	try:
	#		while runCondition: server.handle_request()
	#	except KeyboardInterrupt:
	#		print "done"
	#
	# == STANDALONE (Retro WSGI server)
	#
	elif method in (STANDALONE, AIO):
		try:
			import reporter as logging
		except:
			import logging
		server_address     = (
			address or app.config("address") or DEFAULT_ADDRESS,
			int(port or app.config("port") or DEFAULT_PORT)
		)
		stack.fromRetro = True
		# NOTE: That's an acceptable tight coupling
		stack._app      = app
		if method == STANDALONE and not asynchronous:
			import retro.wsgi
			try:
				server   = retro.wsgi.WSGIServer(server_address, stack)
				retro.wsgi.onError(onError)
				socket = server.socket.getsockname()
				print ("Retro embedded server listening on %s:%s" % ( socket[0], socket[1]))
			except Exception as e:
				logging.error("Retro: Cannot bind to {0}:{1}, error: {2}".format(server_address[0], server_address[1], e))
				return -1
			# TODO: Support runCondition
			try:
				while runCondition():
					server.handle_request()
			except KeyboardInterrupt:
				print ("done")
		else:
			import retro.aio
			import asyncio
			retro.aio.run(app, server_address[0], server_address[1])
			# TODO: Support runCondition
	else:
		raise Exception("Unknown retro setup method:" + method)

# EOF - vim: tw=80 ts=4 sw=4 noet
