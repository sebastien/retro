#!/usr/bin/env python
# Encoding: utf8
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
# Last mod  : 22-Jul-2015
# -----------------------------------------------------------------------------

# FIXME: Reactor is broken (and probably unnecessary)

__doc__ = """\
This module is based on Colin Stewart WSGIUtils WSGI server, only that it is
tailored to Retro specific needs. In this respect, you can only use it with
Retro applications, but it will give you many more features than any other
WSGI servers, which makes it the ideal target for development.
"""

try:
	import http.server  as SimpleHTTPServer
	import socketserver as SocketServer
	import urllib.parse as urlparse
	BaseHTTPServer = SimpleHTTPServer
except ImportError:
	import SimpleHTTPServer, SocketServer, BaseHTTPServer, urlparse

from .core import ensureUnicode

import sys, socket, errno, time, traceback, io, threading, re
try:
	import reporter
	logging = reporter.bind("retro")
except ImportError:
	import logging
	reporter = None

from . import core, web

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

RE_EXCEPTION_TRACEBACK = re.compile("^Traceback \([^)]+\):$")
RE_EXCEPTION_FILE      = re.compile('^  File "([^"]+)", line (\d+), in ([^\s]+)$')
RE_EXCEPTION_ERROR     = re.compile("^([\w_]+(\.[\w_]+)*):\s*$")
SERVER_ERROR_CSS = u"""\
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
	background: #F5E5E5;
	font-family: monospace;
	font-size: 80%;
	line-height: 1.25em;
}

body pre {
	padding: 5px;
}


.traceback {
}

.prelude {
	border-left: 1px solid #f11111;
	background: #555555;
	color: white;
	padding: 1.25em;
	margin-top: 1.25em;
}

.exception {
	border-left: 1px solid #f11111;
	padding: 1.25em;
	color: white;
	background: #FF6B48;
	font-weight: bold;
}
.exception code {
	padding: 0em;
	background: transparent;
}

.traceback .output {
	border-left: 1px solid #f11111;
	padding: 1.25em;
	background: #F5E5E5;
}

.traceback .stack ol {
	padding: 0em;
}

.traceback .stack li {
	list-style-type: none;
	margin-top:    0.75em;
	margin-bottom: 0.75em;
	background: #F0F0F0;
}

.traceback .stack li .number {
	display: inline-block;
	background: #555555;
	color: white;
	padding: 0.5em;
	padding-right: 0.75em;
	width: 2.5em;
	text-align: right;
}

.traceback .stack li.N0 .number {
	background: #FF6B48;
}

.traceback .stack li .origin {
	color: #808080;
}

.traceback .stack li .description {
	padding: 0.5em;
	padding-left: 1.25em;
}
.traceback .stack li .source {
	padding: 1.25em;
	margin: 0em;
	color: #555555;
}

.traceback .stack .line {
	font-weight: bold;
}

.traceback .stack .function {
	padding: 0em;
	font-weight: bold;
	background: transparent;
}

.traceback .stack a,
.traceback .stack a:hover
{
	color: #808080;
	text-decoration: none;
}

.traceback .stack a:hover {
	background-color: #F0F0F0;
}

"""


SERVER_ERROR = u"""\
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
   <div class="prelude"><code>%s</code></div>
   <div class="exception"><code>%s</code></div>
   <div class='traceback'>%s</pre>
</body>
</html>
"""

# ------------------------------------------------------------------------------
#
# WSGI REACTOR
#
# ------------------------------------------------------------------------------

class WSGIReactorGuard:
	"""This class is a utility that allows to protect Retro reactor from
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
		self._mainthread    = None
		self._isRunning     = False
		self.debugMode      = False

	def register( self, handler, application ):
		self._handlersLock.acquire()
		self._handlers.append((handler, application))
		self._hasHandlersEvent.set()
		self._handlersLock.release()

	def start( self ):
		if not self._isRunning:
			assert self._mainthread is None
			self._handlersLock     = threading.Lock()
			self._hasHandlersEvent = threading.Event()
			self._hasHandlersEvent.clear()
			self._isRunning   = True
			self._mainthread  = threading.Thread(target=self.run)
			self._mainthread.start()
		return self

	def stop( self ):
		if self._isRunning:
			self._hasHandlersEvent.set()
			self._isRunning = False
			self._mainthread = None

	def shutdown( self, *args ):
		self.stop()

	def run( self ):
		"""The Reactor runs by iterating on each handler, one at a time.
		Basically, each handler is a response generator and each handler is
		allowed to produce only one item per round. In other words, handlers are
		interleaved."""
		while self._isRunning:
			self._hasHandlersEvent.wait()
			# This situation may happen when we shutdown on empty handlers list
			if not self._handlers:
				continue
			self._handlersLock.acquire()
			handler, application = self._handlers[0]
			del self._handlers[0]
			if not self._handlers:
				self._hasHandlersEvent.clear()
			self._handlersLock.release()
			#if self.debugMode:
				#time.sleep(0.5)
			# If the handler is done, we simply remove it from the handlers list
			# If the handler continues, we re-schedule it
			if handler.next(application) is True:
				self._handlersLock.acquire()
				self._handlers.append((handler,application))
				self._hasHandlersEvent.set()
				self._handlersLock.release()


USE_REACTOR = False
REACTOR     = None
ON_SHUTDOWN = []
ON_ERROR    = []

def shutdown(*args):
	if REACTOR:
		REACTOR.shutdown()
	for callback in ON_SHUTDOWN:
		try:
			callback()
		except Exception as e:
			logging.error("Error while shutting down", e)
	sys.exit()

def onShutdown( callback ):
	global ON_SHUTDOWN
	if callback:
		ON_SHUTDOWN.append(callback)

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

def createReactor():
	global REACTOR
	REACTOR = WSGIReactor()

if HAS_SIGNAL:
	# Jython does not support all signals, so we only use
	# the available ones
	signals = ['SIGINT',  'SIGHUP', 'SIGABRT', 'SIGQUIT', 'SIGTERM']
	for sig in signals:
		try:
			signal.signal(getattr(signal,sig),shutdown)
		except Exception as e:
			sys.stderr.write("[!] retro.wsgi.createReactor:%s %s\n" %(sig, e))

createReactor()

def usesReactor():
	"""Tells wether the reactor is enabled or not."""
	return USE_REACTOR

def getReactor(autocreate=True):
	"""Returns the shared reactor instance for this module, creating a new
	reactor if necessary."""
	REACTOR.start()
	return REACTOR

# ------------------------------------------------------------------------------
#
# WSGI REQUEST HANDLER
#
# ------------------------------------------------------------------------------

class WSGIHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
	"""A simple handler class that takes makes a WSGI interface to the
	default Python HTTP server.

	This handler is made to handle HTTP response generation in multiple times,
	allowing easy implementation of streaming/comet/push(whatever you call it).
	It will also automatically delegate the processing of the requests to the
	module REACTOR if it exists(see 'getReactor()')

	NOTE: It seems like some browsers(including FireFox) won't allow more than
	one open POST connection per session... so be sure to test streaming with
	two different instances.
	"""

	class ResponseExpected(Exception):
		"""This exception occurs when a handler does not returns a Response,
		which can happen quite often in the beginning."""
		def __init__( self, handler ):
			Exception.__init__(self,"""\
Handler must return a response object: %s
Use request methods to create a response(request.respond, request.returns, ...)
"""%( handler ))

	STARTED    = "Started"
	PROCESSING = "Processing"
	WAITING    = "Waiting"
	ENDED      = "Ended"
	ERROR      = "Error"

	def log_request(self, code="-", size=""):
		if hasattr(self, "_startTime"):
			line = "{0:60s} [{1}] {2:0.3f}s".format(self.requestline, code, (time.time() - self._startTime))
		else:
			line = "{0:60s} [{1}]".format(self.requestline, code)
		if code >= 400:
			logging.error(line)
		elif code >= 300 and code < 400:
			if reporter:
				logging.info(line, code=code, color=reporter.COLOR_DARK_GRAY)
			else:
				logging.info(line)
		else:
			logging.info(line)

	def log_error( self, format, *args ):
		logging.error("{0} - - [{1}] {2}".format(
			self.client_address[0],
			self.log_date_time_string(),
			format % args,
		))

	def log_message( self, format, *args ):
		pass

	def do_GET(self):
		self.run(self.server.application)

	def do_HEAD(self):
		self.run(self.server.application)

	def do_OPTIONS(self):
		self.run(self.server.application)

	def do_POST(self):
		self.run(self.server.application)

	def do_PUT(self):
		self.run(self.server.application)

	def do_DELETE(self):
		self.run(self.server.application)

	def finish( self ):
		return

	def _finish( self ):
		# NOTE: I am not sure this is necessary anymore, at least it causes
		# problems with Python3
		if False:
			try:
				SimpleHTTPServer.SimpleHTTPRequestHandler.finish(self)
			except Exception as e:
				# This sometimes throws an 'error: [Errno 32] Broken pipe'
				pass

	def run(self, application, useReactor=True):
		"""This is the main function that runs a Retro application and
		produces the response. This does not return anything, and the execution
		will be asynchronous is a reactor is available and that the useReactor
		parameter is True(this is the case by default)."""
		self._state = self.STARTED
		self._rendezvous = None
		# When using the reactor, we simply submit the application for
		# execution(we delegate the execution to the reactor)
		if usesReactor():
			getReactor().register(self, application)
		# Otherwise we iterate on the application(one shot execution)
		else:
			while self.next(application):
				# We do a time.sleep in the hope that this would yield to
				# other threads
				time.sleep(0)
				continue

	def nextWithReactor( self, application ):
		if self.next(application):
			getReactor().register(self.nextWithReactor, application)

	def next( self, application ):
		"""This function should be called by the main thread, and allows to
		process the request step by step(as opposed to one-shot processing).
		This makes it easier to do streaming."""
		res = False
		if self._state == self.STARTED:
			self._startTime = time.time()
			self._processStart(application)
			res = True
		elif self._state == self.PROCESSING:
			self._processIterate()
			res = True
		elif self._state == self.WAITING:
			# If a reactor is used, we re-schedule the continuation of this
			# process when the condition/rendez-vous is met
			# FIXME: Should not be global
			if usesReactor():
				handler = self
				def resume_on_rdv(*args,**kwargs):
					handler._state = handler.PROCESSING
					getReactor().register(handler, application)
				# When the timeout is reached, we just end the request
				def resume_on_timeout(*args,**kwargs):
					handler._state = handler.ENDED
					self._processEnd()
					return False
				self._rendezvous.onMeet(resume_on_rdv)
				self._rendezvous.onTimeout(resume_on_timeout)
			# If we are in a process/threaded mode, we create an Event object
			# that will be set to true when the event is met
			else:
				# FIXME: Implement this
				raise NotImplementedError
			res = False
		elif self._state != self.ENDED:
			self._processEnd()
			res = False
		return res

	def _processStart( self, application ):
		"""First step called in the processing of a request. It creates the
		WSGI-compatible environment and passes the environment(which
		describes the request) and the function to output the response the
		application request handler.

		The state of the server is set to PROCESSING or ERROR if the request
		handler fails."""
		protocol, host, path, parameters, query, fragment = urlparse.urlparse('http://localhost%s' % self.path)
		if not hasattr(application, "fromRetro"):
			raise Exception("Retro embedded Web server can only work with Retro applications.")
		script = application.app.config("root")
		env = {
			'wsgi.version':(1,0)
			,'wsgi.url_scheme': 'http'
			,'wsgi.input': self.rfile
			,'wsgi.errors': sys.stderr
			,'wsgi.multithread': 1
			,'wsgi.multiprocess': 0
			,'wsgi.run_once': 0
			,'retro.app':application.app
			,'extra.request': self.raw_requestline
			,'extra.headers': self.headers.headers if hasattr(self.headers, "headers") else self.headers
			,'REQUEST_METHOD': self.command
			,'SCRIPT_NAME': script
			,'PATH_INFO': path
			,'QUERY_STRING': query
			,'CONTENT_TYPE': self.headers.get('Content-Type', '')
			,'CONTENT_LENGTH': self.headers.get('Content-Length', '')
			,'REMOTE_ADDR': self.client_address[0]
			,'SERVER_NAME': self.server.server_address [0]
			,'SERVER_PORT': str(self.server.server_address [1])
			,'SERVER_PROTOCOL': self.request_version
		}
		for httpHeader, httpValue in list(self.headers.items()):
			# FIXME: Slow!
			env ['HTTP_%s' % httpHeader.replace('-', '_').upper()] = httpValue
		# Setup the state
		self._sentHeaders = 0
		self._headers = []
		try:
			self._result = application(env, self._startResponse)
			self._state  = self.PROCESSING
		except Exception as e:
			self._result  = None
			self._showError(e, env, application)
			self._state = self.ERROR
		return self._state

	def _processIterate(self):
		"""This iterates through the result iterator returned by the WSGI
		application."""
		self._state = self.PROCESSING
		try:
			data = next(self._result)
			if data:
				self._writeData(core.ensureBytes(data))
			return self._state
		except StopIteration:
			if hasattr(self._result, 'close'):
				self._result.close()
			return self._processEnd()
		except socket.error as socketErr:
			# Catch common network errors and suppress them
			if(socketErr.args[0] in (errno.ECONNABORTED, errno.EPIPE)):
				logging.debug("Network error caught: (%s) %s" % (str (socketErr.args[0]), socketErr.args[1]))
				# For common network errors we just return
				self._state = self.ERROR
				return False
		except socket.timeout as socketTimeout:
			# Socket time-out
			logging.debug("Socket timeout")
			self._state = self.ERROR
			return False
		except Exception as e:
			self._result = None
			# FIXME: We're not capturing the traceback from the generator,
			# alhought the problem actually happened within it
			logging.error("[!] Exception in stream: {0}".format(e))
			logging.error(traceback.format_exc())
			self._state = self.ERROR

	def _processEnd( self ):
		# TODO: Should close the request
		self._state = self.ENDED
		if(not self._sentHeaders):
			# If we have an exception here in the socket, we can safely ignore
			# it, because the client stopped the connection anyway
			try:
				# We must write out something!
				self._writeData(core.ensureBytes(" "))
			except:
				pass
		self._finish()
		return self._state

	def _startResponse(self, response_status, response_headers, exc_info=None):
		if(self._sentHeaders):
			raise Exception("Headers already sent and start_response called again!")
		# Should really take a copy to avoid changes in the application....
		self._headers =(response_status, response_headers)
		return self._writeData

	def _writeData(self, data):
		if(not self._sentHeaders):
			status, headers = self._headers
			# Need to send header prior to data
			# FIXME: Slow?
			statusCode = status [:status.find(' ')]
			statusMsg = status [status.find(' ') + 1:]
			success   = False
			try:
				self.send_response(int (statusCode), statusMsg)
				success = True
			except socket.error as socketErr:
				logging.debug("Cannot send response caught: (%s) %s" % (str (socketErr.args[0]), socketErr.args[1]))
			if success:
				try:
					for header, value in headers:
						self.send_header(header, value)
				except socket.error as socketErr:
					logging.debug("Cannot send headers: (%s) %s" % (str (socketErr.args[0]), socketErr.args[1]))
			try:
				self.end_headers()
				self._sentHeaders = 1
			except socket.error as socketErr:
				logging.debug("Cannot end headers: (%s) %s" % (str (socketErr.args[0]), socketErr.args[1]))
		# Send the data
		try:
			if core.IS_PYTHON3:
				if not isinstance(data,bytes):
					data = bytes(data, encoding="utf8")
			self.wfile.write(data)
		except socket.error as socketErr:
			logging.debug("Cannot send data: (%s) %s" % (str (socketErr.args[0]), socketErr.args[1]))

	def _showError( self, exception=None, env=None, callback=None ):
		"""Generates a response that contains a formatted error message."""
		prelude   = u""
		error_msg = u""
		error_txt = u""
		if env:
			prelude += u"<div class='request'>{0} {1}</div>\n".format(
				env.get("REQUEST_METHOD"),
				env.get("PATH_INFO"),
			)
		# FIXME: We use repr do work around encoding problems in the output
		if isinstance(exception, web.HandlerException):
			error_txt = traceback.format_exc()
			exception_name = exception
			# FIXME: This should be improved
			_, trace_msg = self._formatException(exception.trace)
			_, error_msg = self._formatException(error_txt)
			error_msg = trace_msg + error_msg
		else:
			error_txt = traceback.format_exc()
			exception_name = exception
			exception_name, error_msg = self._formatException(error_txt)
		if not self._sentHeaders:
			self._startResponse("500 Server Error", [("Content-type", "text/html")])
		# TODO: Format the response if in debug mode
		self._state = self.ENDED
		error_message = core.ensureUnicode(SERVER_ERROR %( SERVER_ERROR_CSS, prelude, exception_name, error_msg))
		self._writeData(core.ensureBytes(error_message))
		error_txt = core.ensureUnicode(error_txt)
		logging.error(error_txt)
		error(error_txt)
		self._processEnd()

	def _formatException( self, exception ):
		result = []
		lines  = core.ensureUnicode(exception).split("\n")
		i      = 0
		escape = lambda _:_.replace("<", "&lt;").replace(">", "&gt;")
		output  = []
		stack   = []
		error   = None
		name    = None
		for i,line in enumerate(lines):
			line = lines[i]
			m = RE_EXCEPTION_TRACEBACK.match(line)
			if m:
				# We skip the traceback header
				i += 1
				continue
			m = RE_EXCEPTION_FILE.match(line)
			if m:
				stack.append(dict(
					path=m.group(1),
					line=m.group(2),
					function=m.group(3),
					code=lines[i+1],
					number=len(stack)
				))
				i += 2
				continue
			m = RE_EXCEPTION_ERROR.match(line)
			if m:
				error = line
				name = m.group(1)
				i += 1
			else:
				output.append(line)
				i += 1
		# We strip the output
		while output and not output[0].strip():  output = output[1:]
		while output and not output[-1].strip(): output = output[:-1]
		# FIXME: This still does not work properly for errors with weird UTF8
		output = (core.ensureUnicode(_) for _ in output)
		result = [
			u"<div class='output'><pre>{0}</pre></div>".format("\n".join(output)),
			u"<div class='stack'><ol>",
		]
		stack.reverse()
		for i, _ in enumerate(stack):
			result.append(
				("<li class=N{5}><div class=origin>"
				"<span class=number>{4}</span>"
				"<span class=description>"
				"<span class=function>{2}(...)</span> in "
				"<span class=file><a href='file://{0}'>{0}</a></span>"
				", line <span class=line>{1}</span>"
				"</span>"
				"</div>"
				"<pre class=source>{3}</pre>"
				).format(
					_["path"], _["line"], _["function"], escape(_["code"]),
					_["number"], i
				)
			)
		return name, u"\n".join(ensureUnicode(_) for _ in result)

# ------------------------------------------------------------------------------
#
# WSGI SERVER
#
# ------------------------------------------------------------------------------

# TODO: Easy restart/reload
# TODO: Easy refresh/refresh of the templates
# TODO: Easy access of the configuration
# TODO: Easy debugging of the WSGI application(step by step, with a debugging
#       component)
class WSGIServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
#class WSGIServer(BaseHTTPServer.HTTPServer):
	"""A simple extension of the base HTTPServer that forwards the handling to
	the @WSGIHandler defined in this module.

	This server is multi-threaded, meaning the the application and its
	components can be used at the same time by different thread. This allows
	interleaving of handling of long processes, """

	def __init__(self, address, application, serveFiles=0):
		BaseHTTPServer.HTTPServer.__init__(self, address, WSGIHandler)
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
			logging.error(u"[-] Connection closed by client %s:%s" % (client_address[0], client_address[1]))
		elif last_error.startswith("error: [Errno 32]"):
			logging.error(u"[-] Connection interrupted by client %s:%s" % (client_address[0], client_address[1]))
		else:
			logging.error(u"[-] Unsupported exception:{0}".format(exception))

# EOF - vim: tw=80 ts=4 sw=4 noet
