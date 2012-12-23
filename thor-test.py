import thor, thor.http, urlparse, sys, tempfile
import ipdb
from retro.wsgi import RetroHandler
from retro import Application, Component, on


# Method	Stream	Notes
# read(size)	input	1
# readline()	input	1, 2
# readlines(hint)	input	1, 3
# __iter__()	input	 
# flush()	errors	4
# write(str)	errors	 
# writelines(seq)	errors	

class DataStream:
	"""The DataStream is a stream with read and write cursor and a file-like
	interface. It uses the SpooledTemporaryFile so that unless the data is
	greater than `SPOOL_SIZE` it will be stored in memory.

	This makes `DataStream` very suitable for managing input coming from the
	network, scaling from small to large (100Mb+) requests.
	
	Note that this class is NOT THREAD-SAFE"""

	SPOOL_SIZE = 64 * 1024

 	# NOTE: A better version of this would be that once a chunk is read from
	# the stream, it is removed from it, so that in case a of a very long running
	# request the size of the datastream does not go infinitely

	def __init__( self ):
		self._data      = tempfile.SpooledTemporaryFile(max_size=self.SPOOL_SIZE)
		self._read      = 0
		self._written   = 0
		self._pos       = 0
		self.isComplete = False

	def flush( self ):
		return self._data.flush()

	def seek( self, pos ):
		if self._pos != pos: self._data.seek(pos)
		return pos

	def write( self, data):
		if self._pos != self._written: self.seek(self._written)
		res = self._data.write(data)
		self._written += len(data)
		self._pos      = self._written
		return res

	def writelines( self, lines):
		raise NotImplementedError

	def read(self, size=-1):
		if self._pos != self._read: self.seek(self._read)
		res = self._data.read()
		self._read += len(res)
		self._pos   = self._read
		return res

	def readline(self):
		raise NotImplementedError

	def readlines(self, hint=None):
		raise NotImplementedError

	def __iter__(self):
		raise NotImplementedError

	def done( self ):
		self.isComplete = True
		self._data.flush()
	
	def close( self ):
		self._data.close()

class ThorHandler:

	AVAILABLE = []

	@classmethod
	def Get(cls, exchange=None, application=None):
		if cls.AVAILABLE: h = cls.AVAILABLE.pop()
		else:             h = ThorHandler()
		if exchange: h.set(exchange, application)
		return h

	def __init__( self ):
		self.reset()
		self.handler = RetroHandler.Get()

	def reset( self ):
		self.application = None
		self.exchange    = None
		self.method      = None
		self.uri         = None
		self.headers     = None
		self.trailers    = []
		self.inputStream = None
		self.isComplete  = False

	def set( self, exchange, application ):
		assert self.exchange is None
		self.method      = self.uri = self.headers = None
		self.application = application
		self.exchange    = exchange
		self.isComplete  = False
		self.trailers    = []
		exchange.on("request_start", self._onRequestStart)
		exchange.on("request_body",  self._onRequestBody)
		exchange.on("request_done",  self._onRequestDone)
		return self
	
	def _onRequestStart( self, method, uri, headers ):
		self.inputStream = DataStream()
		self.method      = method
		self.uri         = uri
		headers          = thor.http.header_dict(headers)
		self.iterator    = self.handler.process(
			self.application,
			method, uri, headers,
			self._onStart, self._onWrite
		) 
		self.step()

	def _onRequestBody( self, chunk ):
		self.inputStream.write(chunk)
		self.step()

	def _onRequestDone( self, trailers ):
		self.isComplete = True
		self.inputStream.done()
		self._stepUntilEnd()

	def step( self ):
		try:
			res = self.iterator.next()
			return True
		except StopIteration, e:
			self.exchange.response_done(self.trailers)
			self.inputStream.close()
			self.reset()
			self.AVAILABLE.append(self)
			return False

	def _stepUntilEnd( self ):
		# We call step and then loop through Thor's async loop so that
		# we don't steal CPU from other handlers
		#while self.step():
		#	pass
		if self.step():
			thor.loop.schedule(0.0, self._stepUntilEnd)


	# =========================================================================
	# RETRO HANDLER CALLBACKS
	# =========================================================================

	def _onStart( self, handler ):
		# TODO: Should add HTTP/HTTPS detection
		self.inputStream       = DataStream()
		env                    = handler.env
		#env["command"]         = self.command
		env["wsgi.input"]      = self.inputStream
		#env["REMOTE_ADDR"]     = self.client_address[0]
		#env["REMOTE_ADDR"]     = self.client_address[0]
		#env["SERVER_NAME"]     = self.server.server_address[0]
		#env["SERVER_PORT"]     = str(self.server.server_address[1])
		#env["SERVER_PROTOCOL"] = self.request_version

	def _onWrite( self, handler, chunk ):
		if not handler.headersSent:
			status, headers = handler.response
			code, phrase    = status.split(" ", 1)
			self.exchange.response_start(status, phrase, headers)
			handler.headersSent = True
		self.exchange.response_body(chunk)

# -----------------------------------------------------------------------------
#
# TEST
#
# -----------------------------------------------------------------------------

class Echo(Component):
	@on(GET_POST_UPDATE_DELETE="{path:any}")
	def echo( self, request, path ):
		#sys.stdout.write(request.body())
		#sys.stdout.write("\n\n")
		#sys.stdout.flush()
		return request.respond(path)

application = Application(Echo())

def test_handler(exchange):
	return ThorHandler.Get(exchange, application)

def test_data_stream():
	s = DataStream()
	t = "1234567890"
	a = "ABCDEDFGHIJ"
	s.write(t)
	assert t == s.read()
	s.write(a)
	assert a == s.read()
	assert not  s.read()
	s.write(t)
	assert t == s.read()

if __name__ == "__main__":
	test_data_stream()
	demo_server = thor.http.HttpServer('127.0.0.1', 8000)
	demo_server.on('exchange', test_handler)
	thor.run()
