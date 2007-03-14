#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Railways - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
#             Colin Stewart                           <http://www.owlfish.com/>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 15-Apr-2006
# Last mod  : 13-Mar-2006
# -----------------------------------------------------------------------------

__doc__ = """\
This module is based on Colin Stewart WSGIUtils WSGI server, only that it is
tailored to Railways specific needs. In this respect, you can only use it with
Railways applications, but it will give you many more features than any other
WSGI servers, which makes it the ideal target for development.
"""

import SimpleHTTPServer, SocketServer, BaseHTTPServer, urlparse
import sys, logging, socket, errno, time
import traceback, StringIO, threading, atexit
import core

# ------------------------------------------------------------------------------
#
# ERROR REPORTING
#
# ------------------------------------------------------------------------------

SERVER_ERROR = """\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
<title>Railways Error</title>
<style><!-- 
html, body {
		padding: 0;
		margin: 0;
		font: 10pt/12pt Helvetica, Arial, sans-serif;
		color: #555555;
}
body {
	padding: 30px;
	padding-top: 80px;
}
body b {
	color: #222222;
}
body a:link, body a:visited, body a:hover, body a:active, body a b {
	color: #c65252;
	text-decoration: none;
}
body a:hover {
	text-decoration: none;
}
body a img {
	border: 0px;
}
body code, body pre {
	font-size: 0.8em;
	background: #F5E5E5;
}
body pre {
	padding: 5px;
}
.traceback {
	font-size: 8pt;
	border-left: 1px solid #f11111;
	padding: 10px;
}
 --></style>
</head>
<body>
  <h1>Railways Application Error</h1>
   The following error has occurred in the current Railways Application
   <pre class='traceback'>%s</pre>
</body>
</html>
"""

# ------------------------------------------------------------------------------
#
# WSGI REACTOR
#
# ------------------------------------------------------------------------------

class WSGIReactorGuard:
	"""This class is a utility that allows to protect Railways reactor from
	being accessed by multiple threads at the same time, while also allowing
	lightweight threads to sleep without blocking the whole application."""

class WSGIReactor:
	"""The Reactor is a thread of execution that has a queue of actions
	that need to be executed. The actions are dispatched by the WSGI handlers
	which can be bound to a single threaded or multi-threaded web server.

	The reactor does not need to be created, and is only useful when dealing
	with a multi-threaded environment."""

	def __init__( self ):
		self._handlers      = []
		self._handlersCount = 0
		self._handlersLock  = threading.Lock()
		self._mainthread    = None
		self._isRunning     = False

	def register( self, handler, application ):
		self._handlersLock.acquire()
		self._handlers.append((handler, application))
		self._handlersCount += 1
		self._handlersLock.release()

	def start( self ):
		self._mainthread  = threading.Thread(target=self.run)
		self._isRunning   = True
		self._mainthread.start()
		return self

	def stop( self ):
		self._isRunning = False
		if self._mainthread:
			self._mainthread.join()
		self._mainthread = None

	def run( self ):
		i = 0
		while self._isRunning:
			if not self._handlers:
				continue
			self._handlersLock.acquire()
			handler, application = self._handlers[i]
			self._handlersLock.release()
			if not handler.next(application):
				self._handlersLock.acquire()
				del self._handlers[i]
				self._handlersCount -= 1
				self._handlersLock.release()
			else:
				i = (i + 1) % self._handlersCount

REACTOR = None
def hasReactor():
	"""Tells wether the reactor is enabled or not."""
	return not (REACTOR is None)

def getReactor(autocreate=True):
	"""Returns the shared reactor instance for this module, creating a new
	reactor if necessary."""
	global REACTOR
	if REACTOR is None and autocreate:
		#atexit.register(REACTOR.stop)
		# TODO: For some reason, the execution of some handlers completely freeze the
		# reactor
		REACTOR = WSGIReactor()
	return REACTOR

# ------------------------------------------------------------------------------
#
# WSGI REQUEST HANDLER
#
# ------------------------------------------------------------------------------

class WSGIHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
	"""A simple handler class that takes makes a WSGI interface to the
	default Python HTTP server."""

	class ResponseExpected(Exception):
		"""This exception occurs when a handler does not returns a Response,
		which can happen quite often in the beginning."""
		def __init__( self, handler ):
			Exception.__init__(self,"""\
Handler must return a response object: %s
Use request methods to create a response (request.respond, request.returns, ...)
"""% ( handler ))

	STARTED    = "Started"
	PROCESSING = "Processing"
	ENDED      = "Ended"
	ERROR      = "Error"

	def logMessage (self, *args):
		pass

	def logRequest (self, *args):
		pass

	def do_GET (self):
		self.run(self.server.application)

	def do_POST (self):
		self.run(self.server.application)

	def finish( self ):
		return
	
	def _finish( self ):
		SimpleHTTPServer.SimpleHTTPRequestHandler.finish(self)

	def run(self, application):
		"""This is the main function that runs a Railways application and
		produces the response."""
		self._state = self.STARTED
		# When using the reactor, we simply submit the application for
		# execution
		if hasReactor():
			getReactor().register(self, application)
		# Otherwise we iterate on the application (one shot execution)
		else:
			while self.next(application): continue

	def next( self, application ):
		"""This function should be called by the main thread, and allows to
		process the request step by step (as opposed to one-shot processing)."""
		res = False
		if self._state == self.STARTED:
			self._processStart(application)
			res = True
		elif self._state == self.PROCESSING:
			self._processIterate()
			res = True
		elif self._state != self.ENDED:
			self._processEnd()
			res = False
		return res

	def _processStart( self, application ):
		protocol, host, path, parameters, query, fragment = urlparse.urlparse ('http://localhost%s' % self.path)
		if not hasattr(application, "fromRailways"):
			raise Exception("Railways embedded Web server can only work with Railways applications.")
		script = application.app().config().root()
		logging.info ("Running application with script name %s path %s" % (script, path))
		env = {
			'wsgi.version': (1,0)
			,'wsgi.url_scheme': 'http'
			,'wsgi.input': self.rfile
			,'wsgi.errors': sys.stderr
			,'wsgi.multithread': 1
			,'wsgi.multiprocess': 0
			,'wsgi.run_once': 0
			,'REQUEST_METHOD': self.command
			,'SCRIPT_NAME': script
			,'PATH_INFO': path
			,'QUERY_STRING': query
			,'CONTENT_TYPE': self.headers.get ('Content-Type', '')
			,'CONTENT_LENGTH': self.headers.get ('Content-Length', '')
			,'REMOTE_ADDR': self.client_address[0]
			,'SERVER_NAME': self.server.server_address [0]
			,'SERVER_PORT': str (self.server.server_address [1])
			,'SERVER_PROTOCOL': self.request_version
		}
		for httpHeader, httpValue in self.headers.items():
			env ['HTTP_%s' % httpHeader.replace ('-', '_').upper()] = httpValue
		# Setup the state
		self._sentHeaders = 0
		self._headers = []
		try:
			self._result = application(env, self._startResponse)
			self._state  = self.PROCESSING
		except:
			self._result  = None
			self._showError()
			self._state = self.ERROR
		return self._state

	def _processIterate(self):
		"""This iterates through the result iterator returned by the WSGI
		application."""
		self._state = self.PROCESSING
		try:
			try:
				data = self._result.next()
				if data: self._writeData(data)
				return self._state
			except StopIteration:
				if hasattr(self._result, 'close'):
					self._result.close()
				return self._processEnd()
		except socket.error, socketErr:
			# Catch common network errors and suppress them
			if (socketErr.args[0] in (errno.ECONNABORTED, errno.EPIPE)):
				logging.debug ("Network error caught: (%s) %s" % (str (socketErr.args[0]), socketErr.args[1]))
				# For common network errors we just return
				return
		except socket.timeout, socketTimeout:
			# Socket time-out
			logging.debug ("Socket timeout")
			return

	def _processEnd( self ):
		self._state = self.ENDED
		if (not self._sentHeaders):
			# We must write out something!
			self._writeData (" ")
		self._finish()
		return self._state

	def _startResponse (self, response_status, response_headers, exc_info=None):
		if (self._sentHeaders):
			raise Exception ("Headers already sent and start_response called again!")
		# Should really take a copy to avoid changes in the application....
		self._headers = (response_status, response_headers)
		return self._writeData

	def _writeData (self, data):
		if (not self._sentHeaders):
			status, headers = self._headers
			# Need to send header prior to data
			statusCode = status [:status.find (' ')]
			statusMsg = status [status.find (' ') + 1:]
			self.send_response (int (statusCode), statusMsg)
			for header, value in headers:
				self.send_header (header, value)
			self.end_headers()
			self._sentHeaders = 1
		# Send the data
		self.wfile.write (data)

	def _showError( self ):
		"""Generates a response that contains a formatted error message."""
		error_msg = StringIO.StringIO()
		traceback.print_exc(file=error_msg)
		error_msg = error_msg.getvalue()
		logging.error (error_msg)
		if not self._sentHeaders:
			self._startResponse('500 Server Error', [('Content-type', 'text/html')])
		# TODO: Format the response if in debug mode
		self._state = self.ENDED
		self._writeData(SERVER_ERROR % (error_msg))
		self._processEnd()

# ------------------------------------------------------------------------------
#
# WSGI SERVER
#
# ------------------------------------------------------------------------------

# TODO: Easy restart/reload
# TODO: Easy refresh/refresh of the templates
# TODO: Easy access of the configuration
# TODO: Easy debugging of the WSGI application (step by step, with a debugging
#       component)
class WSGIServer (SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
#class WSGIServer (BaseHTTPServer.HTTPServer):
	"""A simple extension of the base HTTPServer that forwards the handling to
	the @WSGIHandler defined in this module.
	
	This server is multi-threaded, meaning the the application and its
	components can be used at the same time by different thread. This allows
	interleaving of handling of long processes, """

	def __init__ (self, address, application, serveFiles=1):
		BaseHTTPServer.HTTPServer.__init__ (self, address, WSGIHandler)
		self.application        = application
		self.serveFiles         = 0
		self.serverShuttingDown = 0

	def handle(self):
		"""Handle multiple requests if necessary."""
		# FIXME: Don't know if this is necessary
		self.close_connection = 1
		self.handle_one_request()
		while not self.close_connection:
			self.handle_one_request()
# EOF
