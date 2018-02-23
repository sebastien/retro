#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 15-Feb-2018
# Last mod  : 16-Feb-2018
# -----------------------------------------------------------------------------

import asyncio, collections, sys, types, time
import retro.core
from   retro.contrib.localfiles import LocalFiles
try:
	import reporter
	logging = reporter.bind("retro-aio")
except ImportError as e:
	import logging

"""
A simple AsyncIO-based HTTP Web Server with an WSGI interface that
specializes Retro's request object to support asynchronous loading.

It's not meant to be used in production but is perfect for local development
servers. The implementation only supports HTTP/1.1 and is designed to be
relatively simple.
"""

# -----------------------------------------------------------------------------
#
# ASYNC REQUEST
#
# -----------------------------------------------------------------------------

class AsyncRequest(retro.core.Request):
	"""A specialized retro Request object that uses coroutines to
	load the data."""

	async def data( self, data=retro.core.NOTHING, asFile=False, partial=False ):
		await self._data_load(data, partial)
		return self._data_process(data, asFile, partial)

	async def _data_load( self, data, partial ):
		if data == retro.core.NOTHING and not partial:
			while not self.isLoaded():
				await self.load()

	async def load( self, size=None, decode=True ):
		# We make sure that the body loader exists
		self._load_prepare()
		await self._load_load(size)
		self._load_process(size, decode)

	async def _load_load( self, size):
		if not self._bodyLoader:
			self._bodyLoader = RequestBodyLoader(self)
		if not self._bodyLoader.isComplete():
			is_loaded = await self._bodyLoader.load(size)

	def createRequestBodyLoader( self, request, complete=False ):
		return AsyncRequestBodyLoader(request, complete)

# -----------------------------------------------------------------------------
#
# REQUEST BODY LOADER
#
# -----------------------------------------------------------------------------

class AsyncRequestBodyLoader(retro.core.RequestBodyLoader):
	"""A specialized request body loader to asynchronously load the
	requests's body."""

	async def load( self, size=None, writeData=True ):
		# If the load is complete, we don't have anything to do
		to_read = self._load_prepare(size)
		read_data = await self._load_load(to_read)
		return self._load_post(to_read, read_data, writeData)

	async def _load_load( self, to_read ):
		read_data = await self.request._environ['wsgi.input'].read(to_read)
		self.contentRead += to_read
		return read_data

# -----------------------------------------------------------------------------
#
# HTTP CONTEXT
#
# -----------------------------------------------------------------------------
# TEST:  curl --data "param1=value1&param2=value2" http://localhost:8001/poeut

class HTTPContext(object):
	"""Parses an HTTP request and headers from a stream through the `feed()`
	method."""

	def __init__( self, address, port ):
		self.address = address
		self.port     = port
		self.reset()

	def reset( self ):
		self.method   = None
		self.uri      = None
		self.protocol = None
		self.headers  = collections.OrderedDict()
		self.step     = 0
		self.rest     = None
		self.status   = None
		self._stream  = None

	def input( self, stream ):
		self._stream = stream

	def feed( self, data ):
		"""Feeds data into the context."""
		if self.step >= 2:
			return False
		else:
			t = self.rest + data if self.rest else data
			i = t.rfind(b"\r\n")
			if i == -1:
				self.rest = t
			else:
				j = i + 2
				o = self.parseChunk(t,0,j)
				assert (o <= j)
				self.rest = t[j:] if j < len(t) else None
			return True

	def parseChunk( self, data, start, end ):
		"""Parses a chunk of the data, which MUST have at least one
		/r/n in there and end with /r/n."""
		# NOTE: In essence, this is pretty close to data[stat:end].split("\r\n")
		# 0 = REQUEST
		# 1 = HEADERS
		# 2 = BODY
		# 3 = DONE
		step = self.step
		o    = start
		l    = end
		# We'll stop once we reach the end passed above.
		while step < 2 and o < l:
			# We find the closest line separators. We're guaranteed to
			# find at least one.
			i = data.find(b"\r\n", o)
			# The chunk must have \r\n at the end
			assert (i >= 0)
			# Now we have a line, so we parse it
			step = self.parseLine(step, data[o:i])
			# And we increase the offset
			o = i + 2
		color = reporter.COLOR_BLUE_BOLD
		if self.method == "HEAD":
			color = reporter.COLOR_BLUE
		elif self.method == "POST":
			color = reporter.COLOR_GREEN_BOLD
		elif self.method == "UPDATE":
			color = reporter.COLOR_GREEN
		elif self.method == "DELETE":
			color = reporter.COLOR_YELLOW
		logging.info("[{0}] {1}".format(self.method, self.uri), color=color)
		# We update the state
		self.step = step
		return o

	def parseLine( self, step, line ):
		"""Parses a line (without the ending `\r\n`), updating the
		context's {method,uri,protocol,headers,step} accordingly. This
		will stop once two empty lines have been encountered."""
		if step == 0:
			# That's the REQUEST line
			j = line.index(b" ")
			k = line.index(b" ", j + 1)
			self.method   = line[:j].decode()
			self.uri      = line[j+1:k].decode()
			self.protocol = line[k+1:].decode()
			step = 1
		elif not line:
			# That's an EMPTY line, probably the one separating the body
			# from the headers
			step += 1
		elif step >= 1:
			# That's a HEADER line
			step = 1
			j = line.index(b":")
			h = line[:j].decode()
			j += 1
			if j < len(line) and line[j] == " ":
				j += 1
			v = line[j:].decode()
			self.headers[h] = v
		return step

	# TODO: We might want to move that to connection, but right
	# now the HTTP context is a better fix.
	# variant of that.
	async def read( self, size=None ):
		"""Reads `size` bytes from the context's input stream, using
		whatever data is left from the previous data feeding."""
		rest = self.rest
		# This method is a little bit contrived because e need to test
		# for all the cases. Also, this needs to be relatively fast as
		# it's going to be used often.
		if rest is None:
			if self._stream:
				if size is None:
					return await self._stream.read()
				else:
					return await self._stream.read(size)
			else:
				return b""
		else:
			self.rest = None
			if size is None:
				if self._stream:
					return rest + (await self._stream.read())
				else:
					return rest
			elif len(rest) > size:
				self.rest = rest[size:]
				return rest[:size]
			else:
				return rest + (await self._stream.read(size - len(rest)))

	def export( self ):
		"""Exports a JSONable representation of the context."""
		return {
			"method": self.method,
			"uri": self.uri,
			"protocol": self.protocol,
			"headers": [(k,v) for k,v in self.headers.items()],
		}

	def toWSGI( self ):
		"""Exports a WSGI data structure usable for this context."""
		# SEE: https://www.python.org/dev/peps/pep-0333/
		path = self.uri or ""
		# FIXME: path sometimes is None, we should investigte
		i    = path.find("?")
		if i == -1:
			query = ""
		else:
			query = path[i+1:]
			path  = path[:i]
		res = {
			"wsgi.version"    : (1,0),
			"wsgi.url_scheme" : "http",
			"wsgi.input"      : self,
			"wsgi.errors"     : sys.stderr,
			"wsgi.multithread": 0,
			"wsgi.multiprocess": 0,
			"wsgi.run_once": 0,
			"retro.app": None,
			# "extra.request" : None
			# "extra.header"  : None
			"REQUEST_URI"     : self.uri,
			"REQUEST_METHOD"  : self.method,
			"SCRIPT_NAME"     : "",
			"PATH_INFO"       : path,
			"QUERY_STRING"    : query,
			"CONTENT_TYPE"    : None,
			"CONTENT_LENGTH"  : None,
			"HTTP_COOKIE"     : None,
			"HTTP_USER_AGENT" : None,
			"SCRIPT_ROOT"     : None,
			"HTTP_HOST"       : None,
			"SERVER_NAME"     : self.address,
			"SERVER_PORT"     : self.port,
			# SEE: https://www.python.org/dev/peps/pep-0333/#url-reconstruction
		}
		# We set the additional headers
		for k,v in self.headers.items():
			res[k.upper().replace("-", "_")] = v
		return res

# -----------------------------------------------------------------------------
#
# WSGI CONNECTION
#
# -----------------------------------------------------------------------------

class WSGIConnection(object):
	"""Represents an asynchronous HTTP connection. The connection
	creates an HTTP context and pass it in WSGI format to the application,
	writing the output to the writer socket."""

	BUFFER_SIZE = 1024 * 128

	async def process( self, reader, writer, application, server ):
		# We extract meta-information abouth the connection
		addr    = writer.get_extra_info("peername")
		# We creates an HTTPContext that represents the incoming
		# request.
		context  = HTTPContext(server.address, server.port)
		# This parsers the input stream in chunks
		n        = self.BUFFER_SIZE
		ends     = False
		started  = time.time()
		# We only parse the REQUEST line and the HEADERS. We'll stop
		# once we reach the body. This means that we won't be reading
		# huge requests large away, but let the client decide how to
		# process them.
		while not ends and context.step < 2:
			data    = await reader.read(n)
			ends    = len(data) < n
			context.feed(data)
		# Now that we've parsed the REQUEST and HEADERS, we set the input
		# and let the application do the processing
		context.input(reader)

		# We create a WSGI environment
		env = context.toWSGI()
		# We get a WSGI-enabled requet handler
		wrt = lambda s, h: self._startResponse(writer, context, s, h)
		res = application(env, wrt)
		# NOTE: It's not clear why this returns different types
		if isinstance(res, types.GeneratorType):
			for _ in res:
				writer.write(self._ensureBytes(_))
				await writer.drain()
		else:
			if asyncio.iscoroutine(res):
				res = await res
			# NOTE: I'm not sure why we need to to asWSGI here
			r   = res.asWSGI(wrt)
			for _ in r:
				writer.write(self._ensureBytes(_))
				await writer.drain()
			await writer.drain()
		color = reporter.COLOR_DARK_GRAY
		if context.status >= 100 and context.status < 200:
			color = reporter.COLOR_LIGHT_GRAY
		elif context.status >= 200 and context.status < 300:
			color = reporter.COLOR_GREEN
		elif context.status >= 300 and context.status < 400:
			color = reporter.COLOR_CYAN
		elif context.status >= 400 and context.status < 500:
			color = reporter.COLOR_YELLOW
		elif context.status >= 500:
			color = reporter.COLOR_RED
		logging.trace(" {0}  {1:60s} [{2:0.3f}ms]".format(" " * len(context.method), context.uri, time.time() - started), color=color)
		# TODO: The tricky part here is how to interface with WSGI so that
		# we iterate over the different steps (using await so that we have
		# proper streaming if the response is an iterator). And also
		# how to interface with the writing.
		writer.close()

	def _startResponse( self, writer, context, response_status, response_headers, exc_info=None ):
		writer.write(b"HTTP/1.1 ")
		writer.write(self._ensureBytes(response_status))
		writer.write(b"\r\n")
		try:
			context.status = int(response_status.split(" ", 1)[0])
		except:
			context.status = 0
		for h,v in response_headers:
			writer.write(self._ensureBytes(h))
			writer.write(b": ")
			writer.write(self._ensureBytes(v))
			writer.write(b"\r\n")
		writer.write(b"\r\n")

	def _ensureBytes( self, value ):
		return value.encode("utf-8") if not isinstance(value,bytes) else value

# -----------------------------------------------------------------------------
#
# SERVER
#
# -----------------------------------------------------------------------------

class Server(object):
	"""Smiple asynchronous server"""

	def __init__( self, application, address="127.0.0.1", port=8000 ):
		self.application = application
		self.application._dispatcher._requestClass = AsyncRequest
		self.address = address
		self.port = port

	async def request( self, reader, writer ):
		conn = WSGIConnection()
		try:
			await conn.process(reader, writer, self.application, self)
		except ConnectionResetError:
			print ("Client closed connection")

# -----------------------------------------------------------------------------
#
# API
#
# -----------------------------------------------------------------------------

def run( application, address, port ):
	loop    = asyncio.get_event_loop()
	server  = Server(application, address, port)
	coro    = asyncio.start_server(server.request, address, port, loop=loop)
	server  = loop.run_until_complete(coro)
	socket = server.sockets[0].getsockname()
	logging.info("Retro asyncio server listening on %s:%s" % ( socket[0], socket[1] ))
	try:
		loop.run_forever()
	except KeyboardInterrupt:
		pass
	# Close the server
	server.close()
	loop.run_until_complete(server.wait_closed())
	loop.close()
	logging.trace("done")

# -----------------------------------------------------------------------------
#
# MAIN
#
# -----------------------------------------------------------------------------

if __name__ == "__main__":
	run()

# EOF
