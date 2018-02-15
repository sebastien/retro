import asyncio, collections
import retro
from   retro.contrib.localfiles import LocalFiles
from   retro.core import Request

"""
A simple AsyncIO-based HTTP Web Server with an WSGI interface. It's not meant
to be used in production but is perfect for local development servers. The
implementation only supports HTTP/1.1 and is designed to be relatively simple.
"""

# -----------------------------------------------------------------------------
#
# HTTP CONTEXT
#
# -----------------------------------------------------------------------------
# TEST:  curl --data "param1=value1&param2=value2" http://localhost:8001/poeut

class HTTPContext(object):
	"""Parses an HTTP request and headers from a stream through the `feed()`
	method."""

	def __init__( self ):
		self.reset()

	def reset( self ):
		self.method   = None
		self.url      = None
		self.protocol = None
		self.headers  = collections.OrderedDict()
		self.step     = 0
		self.rest     = None
		self._stream  = None

	def input( self, stream ):
		self._stream = stream

	# TODO: We might want to make that async, or at least provide an async
	# variant of that.
	def read( self, size=None ):
		"""Reads `size` bytes from the context's input stream, using
		whatever data is left from the previous data feeding."""
		rest = self.rest
		# This method is a little bit contrived because e need to test
		# for all the cases. Also, this needs to be relatively fast as
		# it's going to be used often.
		if rest is None:
			if self._stream:
				if size is None:
					return self._stream.read()
				else:
					return self._stream.read(size)
			else:
				return b""
		else:
			self._rest = None
			if size is None:
				if self._stream:
					return rest + self._stream.read()
				else:
					return rest
			elif len(rest) > size:
				self._rest = rest[size:]
				return rest[:size]
			else:
				return rest + self._stream.read(size - len(rest))

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
		# We update the state
		self.step = step
		return o

	def parseLine( self, step, line ):
		"""Parses a line (without the ending `\r\n`), updating the
		context's {method,url,protocol,headers,step} accordingly. This
		will stop once two empty lines have been encountered."""
		if step == 0:
			# That's the REQUEST line
			j = line.index(b" ")
			k = line.index(b" ", j + 1)
			self.method   = line[:j].decode()
			self.url      = line[j+1:k].decode()
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
			v = line[j:].strip().decode()
			self.headers[h] = v
		return step

	def export( self ):
		"""Exports a JSONable representation of the context."""
		return {
			"method": self.method,
			"url": self.url,
			"protocol": self.protocol,
			"headers": [(k,v) for k,v in self.headers.items()],
		}

	def toWSGI( self ):
		"""Exports a WSGI data structure usable for this context."""
		# SEE: https://www.python.org/dev/peps/pep-0333/
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
			"REQUEST_URI"     : self.url,
			"REQUEST_METHOD"  : self.method,
			"QUERY_STRING"    : None,
			"PATH_INFO"       : None,
			"CONTENT_TYPE"    : None,
			"CONTENT_LENGTH"  : None,
			"HTTP_COOKIE"     : None,
			"HTTP_HOST"       : None,
			"HTTP_USER_AGENT" : None,
			"SCRIPT_NAME"     : None,
			"SCRIPT_ROOT"     : None,
		}
		# We set the additional headers
		for k,v in self.headers:
			res[k.upper().replace("-", "_")] = v
		return res

# -----------------------------------------------------------------------------
#
# CONNECTION
#
# -----------------------------------------------------------------------------

class Connection(object):
	BUFFER_SIZE = 10

	async def process( self, reader, writer ):
		# We extract meta-information abouth the connection
		addr    = writer.get_extra_info("peername")
		# We creates an HTTPContext that represents the incoming
		# request.
		context  = HTTPContext(reader)
		# This parsers the input stream in chunks
		n        = self.BUFFER_SIZE
		ends     = False
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
		req = Request(env)
		res = req(env, self._startResponse)
		# TODO: The tricky part here is how to interface with WSGI so that
		# we iterate over the different steps (using await so that we have
		# proper streaming if the response is an iterator). And also
		# how to interface with the writing.

		writer.write(b"404 Not Found\r\n")

		await writer.drain()
		writer.close()

	def _processResponse( self, response_status, response_headers, exc_info=None ):

	def _writeData( self, data ):


# -----------------------------------------------------------------------------
#
# SERVER
#
# -----------------------------------------------------------------------------

class Server(object):

	async def request( self, reader, writer ):
		conn = Connection()
		await conn.process(reader, writer)

# -----------------------------------------------------------------------------
#
# API
#
# -----------------------------------------------------------------------------

def run( arguments=None, options={} ):
	# import argparse
	# p = argparse.ArgumentParser(description="Starts a web server that translates PAML files")
	# p.add_argument("values",  type=str, nargs="*")
	# p.add_argument("-d", "--def", dest="var",   type=str, action="append")
	# components = [LocalFiles()]
	# app        = retro.Application(components=components)

	address = "127.0.0.1"
	port    = 8001
	loop    = asyncio.get_event_loop()
	server  = Server()
	coro    = asyncio.start_server(server.request, address, port, loop=loop)
	server  = loop.run_until_complete(coro)
	print('Serving on {}'.format(server.sockets[0].getsockname()))
	try:
		loop.run_forever()
	except KeyboardInterrupt:
		pass

	# Close the server
	server.close()
	loop.run_until_complete(server.wait_closed())
	loop.close()

# -----------------------------------------------------------------------------
#
# MAIN
#
# -----------------------------------------------------------------------------

if __name__ == "__main__":
	run()

# EOF
