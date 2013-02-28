#!/usr/bin/env python
# Encoding: iso-8859-1
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
#             Colin Stewart                           <http://www.owlfish.com/>
#             Fabien Moritz                           <fabien.moritz@gmail.com>
# -----------------------------------------------------------------------------
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 15-Apr-2006
# Last mod  : 08-Feb-2013
# -----------------------------------------------------------------------------

import traceback

__doc__ = """\
This module is based on Colin Stewart WSGIUtils WSGI server, only that it is
tailored to Retro specific needs. In this respect, you can only use it with
Retro applications, but it will give you many more features than any other
WSGI servers, which makes it the ideal target for development.
"""

import SimpleHTTPServer, SocketServer, BaseHTTPServer, urlparse
import sys, logging, socket, errno, time
import traceback, StringIO
import core

# FIXME: ERRORS seen with  ab -n 9000 -c 500 http://localhost:8080/
# [!] Exception in stream: Headers already sent and start_response called again!
# Traceback (most recent call last):
#   File "/home/sebastien/Projects/Private/FFctn-2.0/Webapp/Distribution/Library/py/retro/wsgi.py", line 299, in _processIterate
#     data = self._iterator.next()
#   File "/home/sebastien/Projects/Private/FFctn-2.0/Webapp/Distribution/Library/py/retro/core.py", line 1080, in asWSGI
#     startResponse(status, self.headers)
#   File "/home/sebastien/Projects/Private/FFctn-2.0/Webapp/Distribution/Library/py/retro/wsgi.py", line 344, in _startResponse
#     raise Exception ("Headers already sent and start_response called again!")
# ---
# [!] Exception in stream: 'NoneType' object has no attribute 'sendall'
# Traceback (most recent call last):
#   File "/home/sebastien/Projects/Private/FFctn-2.0/Webapp/Distribution/Library/py/retro/wsgi.py", line 304, in _processIterate
#     self._writeData(data)
#   File "/home/sebastien/Projects/Private/FFctn-2.0/Webapp/Distribution/Library/py/retro/wsgi.py", line 350, in _writeData
#     if self._onWrite: self._onWrite(self, data)
#   File "/home/sebastien/Projects/Private/FFctn-2.0/Webapp/Distribution/Library/py/retro/wsgi.py", line 468, in _onWrite
#     self.end_headers()
#   File "/usr/lib/python2.7/BaseHTTPServer.py", line 412, in end_headers
#     self.wfile.write("\r\n")
#   File "/usr/lib/python2.7/socket.py", line 324, in write
#     self.flush()
#   File "/usr/lib/python2.7/socket.py", line 303, in flush
#     self._sock.sendall(view[write_offset:write_offset+buffer_size])
# AttributeError: 'NoneType' object has no attribute 'sendall'
# Exception: Headers already sent and start_response called again!

# 
# Jython has no signal module
try:
	import signal
	HAS_SIGNAL = True
except:
	HAS_SIGNAL = False

# ------------------------------------------------------------------------------
#
# ERROR REPORTING
#
# ------------------------------------------------------------------------------

ON_ERROR = []

def error(message):
	for callback in ON_ERROR:
		try:
			callback(message)
		except:
			pass

def onError( callback ):
	global ON_ERROR
	if callback:
		ON_ERROR.append(callback)

SERVER_ERROR_CSS = """\
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
"""

SERVER_ERROR = """\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
<title>Retro Error</title>
<style><!-- 
%s
 --></style>
</head>
<body>
  <h1>Retro Application Error</h1>
   The following error has occurred in the current Retro Application
   <pre class='traceback'>%s</pre>
</body>
</html>
"""

# ------------------------------------------------------------------------------
#
# RETRO HANDLER
#
# ------------------------------------------------------------------------------

class RetroHandler:
	"""The handler takes a retro.Application instance, a method, URI and
	headers and runs it with a WSGI-like environment.
	
	Retro applications are WSGI application that support asynchronous execution
	by using `Events` and `RendezVous` classes.

	The following features are supported:

	- If the application yields/returns a value that has a `close` method,
	  it will be invoked on the last result.
	
	Handlers are automatically pooled in the `AVAILABLE` pool so that to avoid
	creating to many of them."""

	STARTED        = "STARTED"
	PROCESSING     = "PROCESSING"
	WAITING        = "WAITING"
	ENDED          = "ENDED"
	ERROR          = "ERROR"

	AVAILABLE      = []
	CLEANUP_LAST   = 0
	CLEANUP_PERIOD = 3600

	@classmethod
	def Get(cls):
		"""Gets an available handler"""
		t = time.time()
		if t - cls.CLEANUP_LAST > cls.CLEANUP_PERIOD:
			cls.AVAILABLE = filter(lambda _:(t - _[1]) < cls.CLEANUP_PERIOD, cls.AVAILABLE)
		if cls.AVAILABLE:
			h = cls.AVAILABLE.pop()[0]
		else:
			h = RetroHandler()
		return h

	def __init__( self ):
		self.reset()
	
	def reset( self ):
		self.application  = None
		self.method       = None
		self.uri          = None
		self.headers      = None
		self.headersSent  = False
		self.env          = None
		self.response     = None
		self._state       = None
		self._rendezvous  = None
		self._iterator    = None
		self._onStart     = None
		self._onWrite     = None

	def process(self, application, method, uri, headers, onStart=None, onWrite=None):
		"""This is the main function that runs a Retro application and
		produces the response. This does not return anything, and the execution
		will be asynchronous if a reactor is available and that the useReactor
		parameter is True (this is the case by default).
		
		Note that the same handler can only be used"""
		self.reset()
		self._onStart     = onStart
		self._onWrite     = onWrite
		self._state       = self.STARTED
		self.application  = application
		self.method       = method
		self.uri          = uri
		self.headers      = headers
		# FIXME: Should provide to options:
		# setup() -> run()     that does a single-shot run
		# setup() -> stream()  that iterates
		try:
			can_continue = True
			iteration    = 0
			# NOTE: The idea here is that the handler should yield the following:
			# - the number of the iteration
			# - the time elapsed since the request (lifetime)
			# - the data chunk returned by the application
			# - an optional event to register a callback called when the next 'step' can be called
			# - an optional event to register a callback called if the delay has timed out
			while can_continue:
				can_continue = self.next()
				if can_continue: yield (iteration, 0)
				iteration += 1
		except StopIteration, e:
			pass

	def next( self ):
		"""Iterates through the application, updating the handler's state."""
		res = False
		if self._state == self.STARTED:
			self._processStart()
			res = True
		elif self._state == self.PROCESSING:
			self._processIterate()
			res = True
		elif self._state == self.WAITING:
			raise NotImplementedError
			# SEE: http://wsgi.readthedocs.org/en/latest/specifications/fdevent.html
			# Here, we should wait for a rendez-vous to be met or timedout
			# to continue...
			# --
			# if usesReactor():
			# 	handler = self
			# 	def resume_on_rdv(*args,**kwargs):
			# 		handler._state = handler.PROCESSING
			# 		self.getReactor().register(handler, application)
			# 	# When the timeout is reached, we just end the request
			# 	def resume_on_timeout(*args,**kwargs):
			# 		handler._state = handler.ENDED
			# 		self._processEnd()
			# 		return False
			# 	self._rendezvous.onMeet(resume_on_rdv)
			# 	self._rendezvous.onTimeout(resume_on_timeout)
			# If we are in a process/threaded mode, we create an Event object
			# that will be set to true when the event is met
			res = False
		elif self._state != self.ENDED:
			self._processEnd()
			res = False
		return res

	def _processStart( self ):
		"""First step called in the processing of a request. It creates the
		WSGI-compatible environment and passes the environment (which
		describes the request) and the function to output the response the
		application request handler.
		
		The state of the server is set to PROCESSING or ERROR if the request
		handler fails."""
		protocol, host, path, parameters, query, fragment = urlparse.urlparse ('http://localhost%s' % self.uri)
		script = None
		if hasattr(self.application, "fromRetro"):
			script = self.application.app().config("root")
		# SEE: http://www.python.org/dev/peps/pep-0333/
		# SEE: http://wsgi.readthedocs.org/en/latest/amendments-1.0.html
		# SEE: http://wsgi.readthedocs.org/en/latest/proposals-2.0.html
		self.env = env = {
			"wsgi.version"       : (1,0)
			,"wsgi.charset"      : "utf-8"
			,"wsgi.url_scheme"   : "http"
			,"wsgi.input"        : None
			,"wsgi.errors"       : sys.stderr
			,"wsgi.multithread"  : False
			,"wsgi.multiprocess" : False
			,"wsgi.run_once"     : False
			,"REQUEST_METHOD"    : self.method
			,"SCRIPT_NAME"       : script
			,"PATH_INFO"         : path
			,"QUERY_STRING"      : query
			,"CONTENT_TYPE"      : self.headers.get("Content-Type",   "")
			,"CONTENT_LENGTH"    : self.headers.get("Content-Length", "")
			,"REMOTE_ADDR"       : None
			,"SERVER_NAME"       : None
			,"SERVER_PORT"       : None
			,"SERVER_PROTOCOL"   : None
		}
		# We copy the headers in the WSGI
		# FIXME: This should be optimized
		for name, value in self.headers.items(): env["HTTP_%s" % name.replace ("-", "_").upper()] = value
		if self._onStart: self._onStart(self)
		# Setup the state
		self.headersSent   = False
		self.response      = []
		try:
			self._iterator = self.application(env, self._startResponse)
			self._state    = self.PROCESSING
		except Exception, e:
			self._iterator  = None
			self._showError(e)
			self._state     = self.ERROR
		return self._state

	def _processIterate(self):
		"""This iterates through the result iterator returned by the WSGI
		application."""
		self._state = self.PROCESSING
		try:
			data = self._iterator.next()
			if isinstance(data, core.RendezVous):
				self._rendezvous = data
				self._state      = self.WAITING
			elif data:
				self._writeData(data)
			return self._state
		except StopIteration:
			return self._processEnd()
		except socket.error, socket_err:
			# Catch common network errors and suppress them
			if (socket_err.args[0] in (errno.ECONNABORTED, errno.EPIPE)):
				logging.debug ("Network error caught: (%s) %s" % (str (socket_err.args[0]), socket_err.args[1]))
				# For common network errors we just return
				self._state = self.ERROR
				return False
		except socket.timeout, socketTimeout:
			# Socket time-out
			logging.debug ("Socket timeout")
			self._state = self.ERROR
			return False
		except Exception, e:
			self._iterator = None
			# FIXME: We're not capturing the traceback from the generator,
			# alhought the problem actually happened within it
			# FIXME: Should use logging, no?
			logging.error("[!] Exception in stream: {0}\n{1}".format(e,traceback.format_exc()))
			self._state = self.ERROR

	def _processEnd( self ):
		self._state = self.ENDED
		if not self.headersSent:
			# If we have an exception here in the socket, we can safely ignore
			# it, because the client stopped the connection anyway
			try:
				# We must write out something!
				self._writeData(" ")
			except:
				pass
		self._finish()
		return self._state

	def _startResponse (self, response_status, response_headers, exc_info=None):
		if self.headersSent:
			raise Exception ("Headers already sent and start_response called again!")
		# Should really take a copy to avoid changes in the application....
		self.response = (response_status, response_headers)
		return self._writeData

	def _writeData (self, data):
		if self._onWrite: self._onWrite(self, data)

	def _showError( self, exception=None ):
		"""Generates a response that contains a formatted error message."""
		error_msg = StringIO.StringIO()
		traceback.print_exc(file=error_msg)
		error_msg = error_msg.getvalue()
		logging.error (error_msg)
		if not self.headersSent:
			self._startResponse('500 Server Error', [('Content-type', 'text/html')])
		# TODO: Format the response if in debug mode
		self._state = self.ENDED
		# This might fail, so we just ignore if it does
		error_msg = error_msg.replace("<", "&lt;").replace(">", "&gt;")
		self._writeData(SERVER_ERROR % (SERVER_ERROR_CSS, error_msg))
		error(error_msg)
		self._processEnd()

	def _finish( self ):
		"""Called when the processing of the request is finished"""
		# We append the handler to the list of AVAILABLE handlers
		if hasattr(self._iterator, "close"):
			self._iterator.close()
		# We apply reset so as to clear any reference
		self.reset()
	
	def release( self ):
		self.AVAILABLE.append((self, time.time()))

# ------------------------------------------------------------------------------
#
# WSGI REQUEST HANDLER
#
# ------------------------------------------------------------------------------

class WSGIHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
	"""A simple handler class that takes makes a WSGI interface to the
	default Python HTTP server. 
	
	This handler is made to handle HTTP response generation in multiple times,
	allowing easy implementation of streaming/comet/push (whatever you call it).
	It will also automatically delegate the processing of the requests to the
	module REACTOR if it exists (see 'getReactor()')
	
	NOTE: It seems like some browsers (including FireFox) won't allow more than
	one open POST connection per session... so be sure to test streaming with
	two different instances.
	"""

	# TODO: We should update this to use the reactor

	def __init__( self, request, client, server ):
		# NOTE: We need to instanciate the header here first
		self.handler = None
		SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(self, request, client, server)

	# NOTE: These are specializations of SimpleHTTPServer
	def do_GET    (self): self.run("GET")
	def do_HEAD   (self): self.run("HEAD")
	def do_POST   (self): self.run("POST")
	def do_PUT    (self): self.run("PUT")
	def do_DELETE (self): self.run("DELETE")

	def run( self, method ):
		"""Runs Retro's handler in one shot"""
		if not self.handler: self.handler = RetroHandler.Get()
		iterator = self.handler.process(
			self.server.application,
			method, self.path, self.headers,
			self._onStart, self._onWrite
		) 
		# We run the iterator in a one-shot
		for _ in iterator:
			pass
		try:
			SimpleHTTPServer.SimpleHTTPRequestHandler.finish(self)
		except Exception, e:
			# This sometimes throws an 'error: [Errno 32] Broken pipe'
			raise e
			pass

	def finish( self ):
		# NOTE: Finish is part of the SimpleHTTPRequestHandler. We
		# don't implement it as the logic is implemented already
		# in onWrite
		self.handler.release()
		pass

	def _onStart( self, handler ):
		"""Updates the WSGI environment of the handler"""
		# TODO: Should add HTTP/HTTPS detection
		env                    = handler.env
		env["command"]         = self.command
		env["wsgi.input"]      = self.rfile
		env["REMOTE_ADDR"]     = self.client_address[0]
		env["REMOTE_ADDR"]     = self.client_address[0]
		env["SERVER_NAME"]     = self.server.server_address[0]
		env["SERVER_PORT"]     = str(self.server.server_address[1])
		env["SERVER_PROTOCOL"] = self.request_version

	def _onWrite (self, handler, data):
		if not handler.headersSent:
			status, headers = handler.response
			# Need to send header prior to data
			code, reason = status.split(" ", 1)
			success      = False
			try:
				self.send_response(int(code), reason)
				success = True
			except socket.error, socket_err:
				logging.debug ("Cannot send response caught: (%s) %s" % (str (socket_err.args[0]), socket_err.args[1]))
			if success:
				try:
					for header, value in headers:
						self.send_header (header, value)
				except socket.error, socket_err:
					logging.debug ("Cannot send headers: (%s) %s" % (str (socket_err.args[0]), socket_err.args[1]))
			try:
				self.end_headers()
				handler.headersSent = True
			except socket.error, socket_err:
				logging.debug ("Cannot end headers: (%s) %s" % (str (socket_err.args[0]), socket_err.args[1]))
		# Send the data
		try:
			self.wfile.write (data)
		except socket.error, socket_err:
			logging.debug ("Cannot send data: (%s) %s" % (str (socket_err.args[0]), socket_err.args[1]))

	def log_message(self, format, *args):
		# SEE: BaseHTTPServer.BaseHTTPRequestHandler.log_message
		msg = format % args
		logging.info("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), msg))

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

	def __init__ (self, address, application, serveFiles=0):
		BaseHTTPServer.HTTPServer.__init__ (self, address, WSGIHandler)
		self.application        = application
		self.serveFiles         = serveFiles
		self.serverShuttingDown = 0

	def serve( self ):
		while True:
			self.handle_request()

	def handle_error(self, request, client_address):
		exception = traceback.format_exc()
		last_error = exception.rsplit("\n", 2)[-2]
		if   last_error == "AttributeError: 'NoneType' object has no attribute 'recv'":
			logging.error("Connection closed by client %s:%s" % (client_address[0], client_address[1]))
		elif last_error.startswith("error: [Errno 32]"):
			logging.error("Connection interrupted by client %s:%s" % (client_address[0], client_address[1]))
		else:
			logging.error("Unsupported exception: {0}".format(exception))

# EOF - vim: tw=80 ts=4 sw=4 noet
