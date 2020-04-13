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
# HELPERS
#
# -----------------------------------------------------------------------------

RESET = "\033[0m"
GRADIENT = (
	59,  66, 108, 151, 194,
	231, 230, 229, 228, 227, 226,
	220, 214, 208, 202, 160, 196
)

def lerp(a, b, k):
	return a + (b - a) * k

def normal(color):
	return "\033[38;5;%sm" % (color)

def bold  (color):
	return "\033[1;38;5;%sm" % (color)

# -----------------------------------------------------------------------------
#
# ASYNC REQUEST
#
# -----------------------------------------------------------------------------

class AsyncRequest(retro.core.Request):
	"""A specialized retro Request object that uses coroutines to
	load the data."""

	def createRequestBodyLoader( self, request, complete=False ):
		return AsyncRequestBodyLoader(request, complete)

	def init( self ):
		self._aioInput = self._environ['wsgi.input']
		# NOTE: It's OK to merge the HTTP context's headers with
		# the request as the context is not recycled.
		self._headers  = self._aioInput.headers

	# =========================================================================
	# LOADING
	# =========================================================================

	async def load( self, size=None, decode=True ):
		# We make sure that the body loader exists
		if self.isLoaded():
			return self
		else:
			self._load_prepare()
			await self._load_load(size)
			self._load_process(size, decode)
			# assert (self.isLoaded())
		return self

	async def _load_load( self, size):
		if not self._bodyLoader:
			self._bodyLoader = AsyncRequestBodyLoader(self)
		if not self._bodyLoader.isComplete():
			is_loaded = await self._bodyLoader.load(size)

	# =========================================================================
	# DATA LOADING & PROCESSING
	# =========================================================================

	async def data( self, data=retro.core.NOTHING, asFile=False, partial=False ):
		await self._data_load(data, partial)
		return self._data_process(data, asFile, partial)

	async def _data_load( self, data, partial ):
		if data is retro.core.NOTHING and not partial:
			while not self.isLoaded():
				await self.load()

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
		to_read    = self._load_prepare(size)
		read_data  = None
		iteration  = 0
		read_count = 0
		while read_count < to_read:
			d = await self._load_load(to_read - read_count)
			if d is None:
				break
				self._isComplete = True
			else:
				read_data    = d if iteration == 0 else read_data + d
				read_count  += len(d)
				iteration   += 1
				# NOTE: We stream the data here
				if writeData:
					self.request._data.write(d)
				# We break early if we did not read anything
				if read_count == 0:
					break
		# NOTE: We don't call self._load_post like in the sync version, because
		# we've been streaming theresult
		return read_data

	async def _load_load( self, to_read ):
		assert to_read != 0
		read_data = await self.request._environ['wsgi.input'].read(to_read)
		read_count = len(read_data)
		self.contentRead += read_count
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

	def __init__( self, address, port, stats ):
		self.address = address
		self.port     = port
		self.started  = time.time()
		self.stats    = stats
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
		self.started  = time.time()

	def input( self, stream ):
		self._stream = stream

	def feed( self, data ):
		"""Feeds data into the context."""
		if self.step >= 2:
			# If we're past reading the body (>=2), then we can't decode anything
			return False
		else:
			t = self.rest + data if self.rest else data
			# TODO: We're looking for the final \r\n\r\n that separates
			# the header from the body.
			i = t.find(b"\r\n\r\n")
			if i == -1:
				self.rest = t
			else:
				# We skip the 4 bytes of \r\n\r\n
				j = i + 4
				o = self._parseChunk(t,0,j)
				assert (o <= j)
				self.rest = t[j:] if j < len(t) else None
			return True

	def _parseChunk( self, data, start, end ):
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
			step = self._parseLine(step, data[o:i])
			# And we increase the offset
			o = i + 2
		# We update the state
		self.step = step
		return o

	def _parseLine( self, step, line ):
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
			h = line[:j].decode().strip()
			j += 1
			if j < len(line) and line[j] == " ":
				j += 1
			v = line[j:].decode().strip()
			self.headers[h] = v
		return step

	# TODO: We might want to move that to connection, but right
	# now the HTTP context is a better fix.
	# variant of that.
	async def read( self, size=None ):
		"""Reads `size` bytes from the context's input stream, using
		whatever data is left from the previous data feeding."""
		assert size != 0
		rest = self.rest
		# This method is a little bit contrived because e need to test
		# for all the cases. Also, this needs to be relatively fast as
		# it's going to be used often.
		if rest is None:
			if self._stream:
				if size is None:
					res =  await self._stream.read()
					return res
				else:
					# FIXME: Somewhow when returning directly there
					# is an issue when receiving large uploaded files, it
					# will block forever.
					res = await self._stream.read(size)
					return res
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

	def __init__( self ):
		# NOTE: We should probably have only one context
		self.context = None

	async def process( self, reader, writer, application, server ):
		# FIXME: It seems that sometimes the response status is not properly communicated
		# We extract meta-information abouth the connection
		addr    = writer.get_extra_info("peername")
		# We creates an HTTPContext that represents the incoming
		# request.
		context  = HTTPContext(server.address, server.port, server.stats)
		self.context = context
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
		# Here we don't write bodies of HEAD requests, as some browsers
		# simply won't read the body.
		write_body = not (context.method == "HEAD")
		written    = 0
		# NOTE: It's not clear why this returns different types
		if isinstance(res, types.GeneratorType):
			for _ in res:
				data = self._ensureBytes(_)
				written += len(data)
				if write_body:
					writer.write(data)
		else:
			if asyncio.iscoroutine(res):
				res = await res
			# NOTE: I'm not sure why we need to to asWSGI here
			r   = res.asWSGI(wrt)
			for _ in r:
				if isinstance(_, types.AsyncGeneratorType):
					async for v in _:
						data = self._ensureBytes(v)
						written += len(data)
						if writer._transport.is_closing():
							break
						if write_body:
							writer.write(data)
				else:
					data = self._ensureBytes(_)
					written += len(data)
					if writer._transport.is_closing():
						break
					if write_body:
						writer.write(data)
				if writer._transport.is_closing():
					break

		# We need to let some time for the schedule to do other stuff, this
		# should prevent the `socket.send() raised exception` errors.
		# SEE: https://github.com/aaugustin/websockets/issues/84
		await asyncio.sleep(0)
		# TODO: The tricky part here is how to interface with WSGI so that
		# we iterate over the different steps (using await so that we have
		# proper streaming if the response is an iterator). And also
		# how to interface with the writing.
		# NOTE: When the client has closed already
		#   File "/usr/lib64/python3.6/asyncio/selector_events.py", line 807, in write_eof
		# 	self._sock.shutdown(socket.SHUT_WR)
		# AttributeError: 'NoneType' object has no attribute 'shutdown'
		if writer._transport and not writer._transport.is_closing():
			try:
				writer.write_eof()
				await writer.drain()
			except OSError as e:
				pass
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
		self._logResponse(context)

	def _logResponse( self, context ):
		method = context.method or "?"
		uri    = context.uri or "?"
		status = context.status or 600
		elapsed = time.time() - context.started
		stats   = context.stats or {}
		stats["min.time"] = min(elapsed, stats["min.time"] or elapsed)
		stats["max.time"] = max(elapsed, stats["max.time"] or elapsed)
		tk = (1.0 * elapsed - stats["min.time"]) / (stats["max.time"] or 1)
		sk = min (1.0, (1.0 * status / 500.0))
		ti = round(tk * (len(GRADIENT) - 1))
		si = round(sk * (len(GRADIENT) - 1))
		uri_color = RESET
		if method == "HEAD":
			uri_color = normal(GRADIENT[0])
		elif status > 400:
			uri_color = normal(GRADIENT[-1])
		status_color = 255
		if status >= 500:
			status_color = 196 # Red
		elif status >= 400:
			status_color = 202 # Orange
		logging.info("{reset}{method_start}{method:7s}{method_end} {uri_start}{uri:70s}{reset} {status_start}[{status:3d}]{status_end} {elapsed_start}in {elapsed:2.3f}s{elapsed_end}{reset}".format(
			method        = method,
			method_start  = (bold if method in ("GET", "POST", "DELETE") else normal)(status_color),
			method_end    = RESET,
			status        = status,
			status_start  = normal(GRADIENT[si]),
			status_end    = RESET,
			uri           = uri[:69] + "…" if uri and len(uri) > 70 else uri,
			uri_start     = uri_color,
			elapsed       = elapsed,
			elapsed_start = normal(GRADIENT[ti]),
			elapsed_end   = RESET,
			reset         = RESET,
		))

	def _ensureBytes( self, value ):
		return value.encode("utf-8") if not isinstance(value,bytes) else value

# -----------------------------------------------------------------------------
#
# SERVER
#
# -----------------------------------------------------------------------------

class Server(object):
	"""Simple asynchronous server"""

	def __init__( self, application, address="127.0.0.1", port=8000 ):
		self.application = application
		self.application._dispatcher._requestClass = AsyncRequest
		self.address = address
		self.port = port
		self.stats = {
			"min.time" : 99999999,
			"max.time" : 0,
		}

	async def request( self, reader, writer ):
		conn = WSGIConnection()
		try:
			await conn.process(reader, writer, self.application, self)
		except ConnectionResetError:
			logging.info("{0:7s} {1} connection closed after {2:0.3f}s".format(conn.context.method or "?", conn.context.uri, time.time() - conn.context.started, color=reporter.COLOR_YELLOW))

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
	logging.info("Retro {font_server}asyncio{reset} server listening on {font_url}http://{host}:{port}{reset}".format(
		host=socket[0], port=socket[1],
		font_server=bold(255),
		font_url=normal(51),
		reset=RESET,
	))
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

# EOF - vim: ts=4 sw=4 noet
