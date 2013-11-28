#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 12-Sep-2013
# -----------------------------------------------------------------------------

# TODO: Decouple WSGI-specific code and allow binding to Thor
# TODO: Automatic suport for HEAD and cache requests

import os, sys, cgi, re, email, time, types, mimetypes, hashlib, tempfile, string
import gzip, io, threading, locale, collections
try:
	import urllib.request
	import urllib.parse    as urllib_parse
	from   http.server     import BaseHTTPRequestHandler
	from   http.cookies    import SimpleCookie
except ImportError:
	import urllib as urllib_parse
	from   BaseHTTPServer import BaseHTTPRequestHandler
	from   Cookie         import SimpleCookie

NOTHING    = re
MIME_TYPES = dict(
	bz2 = "application/x-bzip",
	gz  = "application/x-gzip",
)

# FIXME: Date in cache support should be locale

try:
	import json as simplejson
	HAS_JSON = True
except:
	HAS_JSON = False

__doc__ = """\
The Retro _core_ module defines classes that are at the basis of writing a
server-side web application. In this respect, this module defines classes:

 - For `Request` and `Response` management
 - For easy headers and cookies management
 - For `Session` management
 - For JSON/JavaScript serialization

This module could be easily re-used in another application, as it is (almost)
completely standalone and separated from Retro Web applications.
"""

# -----------------------------------------------------------------------------
#
# JSON PERSISTANCE
#
# -----------------------------------------------------------------------------

def json( value, *args, **kwargs ):
	assert HAS_JSON
	return simplejson.dumps(value, *args, **kwargs)

def unjson( value ):
	assert HAS_JSON
	return simplejson.loads(value)

def asJSON( value, **options ):
	"""Converts the given value to a JSON representation. This function is an
	enhanced version of `simplejson`, because it supports more datatypes
	(datetime, struct_time) and provides more flexibilty in how values can be
	serialized.

	Specifically, the given 'value' contains a 'asJS' or 'asJSON' method,
	this method will be invoked with this function as first argument and
	the options as keyword-arguments ('**options')
	"""
	# FIXME: It might be better to use json(asPrimitive(value,options)) if it
	# does not have a performance penalty
	if "currentDepth" in options:
		options["currentDepth"] = options["currentDepth"] + 1
	else:
		options["currentDepth"] = 0
	# NOTE: There might be a better way to test if it's a primitive type
	if value in (True, False, None) or type(value) in (bool, float, int, long, bytes, str, unicode):
		res = json(value)
	elif isinstance(value, str) or isinstance(value, unicode):
		return json(value)
	elif type(value) in (list, tuple, set):
		res = "[%s]" % (",".join([asJSON(x,**options) for x in value]))
	elif type(value) == dict:
		r = []
		for k in list(value.keys()):
			r.append('%s:%s' % (json(str(k)), asJSON(value[k], **options)))
		res = "{%s}" % (",".join(r))
	elif hasattr(value, "__class__") and value.__class__.__name__ == "datetime":
		res = asJSON(tuple(value.timetuple()), **options)
	elif hasattr(value, "__class__") and value.__class__.__name__ == "date":
		res = asJSON(tuple(value.timetuple()), **options)
	elif hasattr(value, "__class__") and value.__class__.__name__ == "struct_time":
		res = asJSON(tuple(value), **options)
	elif hasattr(value, "asJSON")  and isinstance(value.asJSON, collections.Callable):
		res = value.asJSON(asJSON, **options)
	elif hasattr(value, "export") and isinstance(value.export, collections.Callable):
		try:
			value = value.export(**options)
		except:
			value = value.export()
		res = asJSON(value)
	# The asJS is not JSON, but rather only JavaScript objects, so this implies
	# that there is a library implemented on the client side
	elif hasattr(value, "asJS") and isinstance(value.asJS, collections.Callable):
		res = value.asJS(asJSON, **options)
	# There may be a "serializer" function that knows better about the different
	# types of object. We use it if it is provided.
	elif options.get("serializer"):
		serializer = options.get("serializer")
		res = serializer(asJSON, value, **options)
		if res is None: res = asJSON(value.__dict__, **options)
	else:
		res = asJSON(value.__dict__, **options)
	return res

def asPrimitive( value, **options ):
	"""Converts the given value to a primitive value that can be converted
	to JSON"""
	if "currentDepth" in options:
		options["currentDepth"] = options["currentDepth"] + 1
	else:
		options["currentDepth"] = 0
	if value in (True, False, None) or type(value) in (float, int, int, str, str):
		res = value
	elif type(value) in (list, tuple, set):
		res = [asPrimitive(v, **options) for v in value]
	elif type(value) == dict:
		res = {}
		for k in value: res[k] = asPrimitive(value[k], **options)
	elif hasattr(value, "__class__") and (value.__class__.__name__ == "datetime" or value.__class__.__name__ == "date"):
		res = tuple(value.timetuple())
	elif hasattr(value, "__class__") and value.__class__.__name__ == "struct_time":
		res = tuple(value)
	elif hasattr(value, "asPrimitive")  and isinstance(value.asPrimitive, collections.Callable):
		res = value.asPrimitive(processor=asPrimitive, **options)
	elif hasattr(value, "export") and isinstance(value.export, collections.Callable):
		try:
			res = value.export(**options)
		except:
			res = value.export()
	# There may be a "serializer" function that knows better about the different
	# types of object. We use it it is provided.
	elif options.get("serializer"):
		serializer = options.get("serializer")
		res        = serializer(asJSON, value, **options)
	else:
		res = asPrimitive(value.__dict__, **options)
	return res

# -----------------------------------------------------------------------------
#
# CACHE TIMESTAMP
#
# -----------------------------------------------------------------------------

DAYS   = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "July", "Aug", "Sep", "Oct", "Nov", "Dec")
def cache_timestamp( t ):
	# NOTE: We  have to do it here as we don't want to force the locale
	# FORMAT: If-Modified-Since: Sat, 29 Oct 1994 19:43:31 GMT
	return "%s, %02d %s %d %d:%d:%d GMT" % (DAYS[t.tm_wday], t.tm_mday, MONTHS[t.tm_mon - 1], t.tm_year, t.tm_hour, t.tm_min, t.tm_sec)

# -----------------------------------------------------------------------------
#
# COMPRESSION
#
# -----------------------------------------------------------------------------

def compress_gzip(data):
	out = io.BytesIO()
	f   = gzip.GzipFile(fileobj=out, mode='w')
	f.write(data)
	f.close()
	return out.getvalue()

# -----------------------------------------------------------------------------
#
# AUTHENTICATION
#
# -----------------------------------------------------------------------------

RE_CUT = re.compile("^[\s\t]|")
def cut(text, separator="|"):
	res   = []
	for line in text.split("\n"):
		if not line: continue
		m = RE_CUT.match(line)
		if m:
			res.append(line[m.end() + 1:])
		else:
			res.append(line)
	return res

# -----------------------------------------------------------------------------
#
# MISC
#
# -----------------------------------------------------------------------------

def escapeHTML(text, quote=True):
	return cgi.escape(text or "", quote)

# -----------------------------------------------------------------------------
#
# EVENT
#
# -----------------------------------------------------------------------------

class Event:

	def __init__( self, name=None, description=None ):
		self.name          = name
		self.description   = description
		self.observers     =[]
		self.observersLock = threading.Lock()

	def observe( self, observer ):
		res = False
		self.observersLock.acquire()
		res = False
		if  not (observer in self.observers):
			self.observers.append(observer)
			res = True
		self.observersLock.release()
		return res

	def unobserve( self, observer ):
		res = False
		self.observersLock.acquire()
		if (observer in self.observers):
			del self.observers[self.observers.index(observer)]
			res = True
		self.observersLock.release()
		return res

	def pipe( self, event ):
		assert isinstance(event, Event)
		self.observe(event.trigger)

	def unpipe( self, event ):
		assert isinstance(event, Event)
		self.unobserve(event.trigger)

	def trigger( self, *args, **kwargs ):
		i = 0
		# We have to clone the observers, as the observer callbacks may remove themselve
		obs = tuple(self.observers)
		for o in obs:
			o(self, o, *args,**kwargs)
			i += 1

	def __getstate__( self ):
		s = self.__dict__.copy()
		del s["observersLock"]
		return s

	def __setstate__( self, s ):
		self.__dict__.update(s)
		if self.__dict__.get("observersLock") == None:
			self.observersLock = threading.Lock()

	def __call__( self,  *args, **kwargs ):
		self.trigger(*args,**kwargs)

class Stream:

	def length( self ):
		raise NotImplementedError

	def open( self, offset ):
		raise NotImplementedError

	def read( self, count ):
		raise NotImplementedError

def IteratorStream( stream ):

	def __init__( self, iterator, length ):
		self.iterator = iterator
		self.length   = length

# -----------------------------------------------------------------------------
#
# RENDEZ-VOUS
#
# -----------------------------------------------------------------------------

class RendezVous:

	def __init__( self, expect=1, timeout=-1 ):
		self.count      = 0
		self.goal       = expect
		self._events    = None
		self._onMeet    = None
		self._onTimeout = None
		self._timeout   = timeout
		self._created   = time.time()
		self._meetSemaphore = threading.Event(expect == 0)
		# FIXME: The best would be to use a schedule/reactor instead of that
		# like 'call me back in XXXms'
		if timeout > 0:
			def run():
				time.sleep(timeout)
				self.timeout()
			threading.Thread(target=run).start()

	def joinEvent( self, event ):
		if self._events is None: self._events = []
		self._meetSemaphore.clear()
		self._events.append(event)
		event.observe(self._eventMet)
		return self

	def _eventMet( self, event, observer, *args, **kwargs ):
		event.unobserve(observer)
		self.meet()

	def onMeet( self, callback ):
		if self._onMeet is None: self._onMeet = []
		self._onMeet.append(callback)

	def onTimeout( self, callback ):
		if self._onTimeout is None: self._onTimeout = []
		self._onTimeout.append(callback)

	def meet( self ):
		self.count += 1
		if self.count == self.goal:
			# When the goal is reached, we call the callbacks
			self._meetSemaphore.set()
			if self._onMeet:
				for c in self._onMeet:
					c(self,c,self.count)
				self._onMeet = None
		return self

	def wait( self ):
		self._meetSemaphore.wait()

	def timeout( self ):
		# When the goal is reached, we call the callbacks
		self._onMeet = None
		if self._onTimeout:
			for c in self._onTimeout:
				c(self,c,self.count)
				self._onTimeout = None
		return self

# ------------------------------------------------------------------------------
#
# REQUEST OBJECT
#
# ------------------------------------------------------------------------------

class Request:
	"""A request object is initialized from data given by the containing
	webserver, it is not directly built by the developer. As web server receive
	requests, they have to build responses to fullfill the requests."""

	DATA_SPOOL_SIZE          = 64 * 1024
	REQUEST_URI              = "REQUEST_URI"
	REQUEST_METHOD           = "REQUEST_METHOD"
	CONTENT_TYPE             = "CONTENT_TYPE"
	CONTENT_LENGTH           = "CONTENT_LENGTH"
	QUERY_STRING             = "QUERY_STRING"
	HTTP_COOKIE              = "HTTP_COOKIE"
	HTTP_HOST                = "HTTP_HOST"
	HTTP_USER_AGENT          = "HTTP_USER_AGENT"
	SCRIPT_NAME              = "SCRIPT_NAME"
	SCRIPT_ROOT              = "SCRIPT_ROOT"
	PATH_INFO                = "PATH_INFO"
	POST                     = "POST"
	GET                      = "GET"
	HEADER_SET_COOKIE        = "Set-Cookie"
	HEADER_CACHE_CONTROL     = "Cache-Control"
	HEADER_EXPIRES           = "Expires"
	HEADER_CONTENT_TYPE      = "Content-Type"
	HEADER_IF_NONE_MATCH     = "If-None-Match"
	HEADER_IF_MODIFIED_SINCE = "If-Modified-Since"

	def __init__( self, environ, charset ):
		"""This creates a new request."""
		self._environ          = environ
		self._headers          = None
		self._charset          = charset
		self._data             = tempfile.SpooledTemporaryFile(max_size=self.DATA_SPOOL_SIZE)
		self._component        = None
		self._cookies          = None
		self._files            = None
		self._params           = None
		self._responseHeaders  = []
		self._bodyLoader       = None
		self.protocol          = "http"

	def headers( self ):
		if self._headers is None:
			e = self._environ
			headers = {}
			# This parses headers from the WSGI environment
			for key in e:
				if not key.startswith("HTTP_"): continue
				header = "-".join(map(string.capitalize, key[len("HTTP_"):].split("_")))
				headers[header] = e[key]
			i = 0
			c = True
			while c:
				k = "HTTP_" + str(i)
				if k in e:
					name,value = e[k].split(",",1)
					headers[name] = value
				else:
					c = False
				i += 1
			self._headers = headers
			return self._headers
		else:
			return self._headers

	def header( self, name ):
		name = "-".join(map(string.capitalize, name.split("-")))
		return self.headers().get(name)

	def method( self ):
		"""Returns the method (GET, POST, etc) for this request."""
		return self._environ.get(self.REQUEST_METHOD)

	def path( self ):
		"""Alias for `self.uri`"""
		return self.uri()

	def url( self ):
		return self.protocol + "://" + self.host() + self.uri()

	def userAgent( self ):
		return self._environ.get(self.HTTP_USER_AGENT)

	def isFromCrawler( self ):
		return self.userAgent().split("/")[0].lower() in CRAWLERS

	def host( self ):
		"""Returns the hostname for this request"""
		return self._environ.get(self.HTTP_HOST)

	def uri( self ):
		"""Returns the URI for this method."""
		uri = self._environ.get(self.REQUEST_URI) or self._environ.get(self.PATH_INFO)
		if self._environ.get(self.QUERY_STRING): uri += "?" + self._environ.get(self.QUERY_STRING)
		return uri

	def contentType( self ):
		"""Returns the request content type"""
		return self._environ.get(self.CONTENT_TYPE)

	def contentLength( self ):
		"""Returns the request content length (if any)"""
		return int(self._environ.get(self.CONTENT_LENGTH) or 0)

	def get( self, name, load=False ):
		"""Gets the parameter with the given name. It is an alias for param"""
		params = self.params(load=load)
		return params.get(name)

	def param( self, name, load=False ):
		"""Gets the parameter with the given name. It is an alias for get"""
		return self.get(name, load=load)

	def params( self, load=False ):
		"""Returns a dictionary with the request parameters. Unless you specify
		load as True, this will only return the parameters containes in the
		request URI, not the parameters contained in the form data, in the
		case of a POST."""
		# Otherwise, if the parameters are empty
		if not self._params:
			query = self._environ.get(self.QUERY_STRING)
			if query:
				# We try to parse the query string
				query_params = cgi.parse_qs(query)
				# FIXME: What about unquote?
				# for key, value in params.items():
				# 	if name == key:
				# 		if len(value) == 1: return urllib.unquote(value[0])
				# 		return urllib.unquote(value)
				# TODO: Decode support
				# if not self._charset is None:
					# for key, value in d.iteritems():
						# d[key] = [i.decode(self._charset, 'ignore') for i in value]
				# In some cases we may only have a string as query, so we consider
				# it as a key
				if  not query_params:
					query        = urllib_parse.unquote(query)
					query_params = {query:'', '':query}
				for k,v in list(query_params.items()): self._addParam(k,v)
			else:
				self._params = {}
			# We load if we haven't loaded yet and load is True
			if load and not self.isLoaded(): self.load()
		return self._params

	def hashParams( self, path=None ):
		"""Parses the parameters that might be defined in the URL's hash, and
		returns a dictionary. Here is how this function works:

		>	hashParams("page")
		>	>> {'__path__': 'page'}

		>	hashParams("page=1")
		>	>> {'page': '1'}

		>	hashParams("page/1&category=2")
		>	>> {'category': '2', '__path__': 'page/1'}

		>	hashParams("page/1&category=2&category=3")
		>	>> {'category': ['2', '3'], '__path__': 'page/1'}

		"""
		if path is None:
			path = self.path().split("#", 1)
			if len(path) == 2: path=path[1]
			else: path = ""
		result = {}
		for element in path.split("&"):
			name_value = element.split("=",1)
			if len(name_value) == 1:
				name  = "__path__"
				value = name_value[0]
			else:
				name, value = name_value
			if name in result:
				if type(result[name]) not in (tuple, list):
					result[name] = [result[name]]
				result[name].append(value)
			else:
				result[name] = value
		return result

	def cookies( self ):
		"""Returns the cookies (as a 'Cookie.SimpleCookie' instance)
		attached to this request."""
		if self._cookies != None: return self._cookies
		cookies = SimpleCookie()
		cookies.load(self.environ(self.HTTP_COOKIE) or '')
		self._cookies = cookies
		return self._cookies

	def cookie( self, name, value=NOTHING, path="/" ):
		"""Returns the value of the given cookie or 'None', if a value is set,
		will make sure that any generated response will set the given cookie."""
		if value is NOTHING:
			c = self.cookies().get(name)
			if c: return c.value
			else: return None
		else:
			# NOTE: See also Response.setCookie
			found = False
			i     = 0
			for header in self._responseHeaders:
				if header[0] == self.HEADER_SET_COOKIE:
					self._responseHeaders[i] = (header[0], "%s=%s; path=%s" % (name, value, path))
					found = True
				i += 1
				break
			if not found:
				self._responseHeaders.append((self.HEADER_SET_COOKIE, "%s=%s; path=%s" % (name, value, path)))

	def has(self, name, load=False):
		"""Tells if the request has the given parameter."""
		params = self.params(load=load)
		return name in params

	def files( self ):
		return [_[0] for _ in self._files]

	def file( self, name ):
		"""Returns the file (as a 'cgi.FieldStorage') which was submitted
		as parameter with the given name. You will have more information
		accessible than with 'get' or 'param', retured as a dict with
		'param', 'filename', 'contentType' and 'data' fields."""
		if not self._files: return None
		for n, s in self._files:
			if n == name:
				return s
		return None

	def environ( self, name=NOTHING, value=NOTHING ):
		"""Gets or sets the environment attached to this request"""
		if name == NOTHING:
			return self._environ
		elif value == NOTHING:
			return self._environ.get(name)
		else:
			self._environ[name] = value

	def session( self, name=NOTHING, value=NOTHING ):
		"""Invokes this request component `session` method, and returns a couple
		(session, sessionState)"""
		session = self._component.session(self)
		if session is None:
			return None
		if name == NOTHING:
			return session
		elif value == NOTHING:
			return session.value(name)
		else:
			return session.value(name, value)

	def data( self, data=NOTHING, asFile=False, partial=False ):
		"""Gets/sets the request data as a file object. Note that when using
		the `asFile` parameter, you should be sure to not do any concurrent access
		to the data as a file, as you'll use the same file descriptor.
		"""
		if data == NOTHING:
			if not partial:
				while not self.isLoaded(): self.load()
			if asFile:
				return self._data
			else:
				position = self._data.tell()
				self._data.seek(0)
				res = self._data.read()
				self._data.seek(position)
				return res
		else:
			# We reset the parameters and files
			self._params     = {}
			self._files      = []
			# We simulate a load if the data was set
			self._environ[self.CONTENT_LENGTH] = len(data)
			if self._data: self._data.close()
			self._data       = tempfile.SpooledTemporaryFile(max_size=self.DATA_SPOOL_SIZE)
			self._data.write(data)
			self._bodyLoader = RequestBodyLoader(self, complete=True)
			return self._bodyLoader

	def body( self, body=re ):
		"""Gets/sets the request body (it is an alias for data)"""
		return self.data(body)

	def isLoaded( self ):
		"""Tells wether the request's body is loaded or not"""
		if self._bodyLoader: return self._bodyLoader.isComplete()
		else: return False

	def loadProgress( self, inBytes=False ):
		"""Returns an integer (0-100) that shows the load progress."""
		if self._bodyLoader: return self._bodyLoader.progress(inBytes)
		else: return 0

	def load( self, size=None, decode=True ):
		"""Loads `size` more bytes (all by default) from the request
		body.

		This will basically read a chunk of data from the incoming
		request, and write it to the `_data` spooled file. Once the
		request in completely read, the body decoder will decode
		the data
		"""
		# We make sure that the body loader exists
		if not self._bodyLoader: self._bodyLoader = RequestBodyLoader(self)
		if not self._bodyLoader.isComplete():
			self._bodyLoader.load(size)
		# We make sure the body is decoded if we have decode and the request is loaded
		if self._bodyLoader.isComplete() and decode:
			# If the the body loader is complete, we'll now proceed
			# with the decoding of the request, which will convert the data
			# into params and fields.
			self._bodyLoader.decode()
		return self

	def range( self ):
		"""Returns the range header information as a couple (start, end) or None if
		there is no range."""
		content_range  = self.header("range")
		if content_range:
			content_range = content_range.split("=")
			if len(content_range) > 1:
				content_range = content_range[1].split("-")
				range_start = int(content_range[0] or 0)
				if content_range[1]:
					range_end = int(content_range[1])
				else:
					range_end = None
			return (range_start, range_end)
		return None

	def referer( self ):
		"""Rerturns the HTTP referer for this request."""
		return self.environ("HTTP_REFERER")

	def clientIP( self ):
		"""Returns the HTTP client IP for this request. This method will get the
		HTTP_X_FORWARDED_FOR variable instead of the REMOTE_ADDR if it is set."""
		return self.environ("HTTP_X_FORWARDED_FOR") or self.environ("REMOTE_ADDR")

	def clientPort( self ):
		"""Returns the HTTP client port for this request."""
		return self.environ("REMOTE_PORT")

	def compression( self ):
		"""Returns the best accepted compression format for this request"""
		encodings = self._environ.get("HTTP_ACCEPT_ENCODING") or ""
		if encodings.find("gzip") != -1:
			return "gzip"
		else:
			return None

	def respond( self, content="", contentType=None, headers=None, status=200):
		"""Responds to this request."""
		if headers == None: headers = []
		if contentType: headers.append(["Content-Type",str(contentType)])
		return Response(content, self._mergeHeaders(headers), status, compression=self.compression())

	def respondMultiple( self, bodies='', contentType="text/html", headers=None, status=200):
		"""Response with multiple bodies returned by the given sequence or
		iterator. This allows to implement 'server push' very easily."""
		BOUNDARY  = "RETRO-Multiple-content-response"
		bodies    = iter(bodies)
		if not headers: headers = []
		headers.append(("Content-Type", "multipart/x-mixed-replace; "
		+ 'boundary=' + BOUNDARY + ''))
		def bodygenerator():
			for body in bodies:
				if body:
					res  = "\r\n" + "--" + BOUNDARY + "\r\n"
					res += "Content-Type: " + contentType + "\r\n"
					res += "\r\n"
					res += body
					res += "\r\n"
					res += "\r\n"
					yield res
				else:
					yield ""
		return Response(bodygenerator(), self._mergeHeaders(headers), 200, compression=self.compression())

	def redirect( self, url, **kwargs ):
		"""Responds to this request by a redirection to the following URL, with
		the given keyword arguments as parameter."""
		if kwargs: url += "?" + urllib_parse.urlencode(kwargs)
		return Response("", self._mergeHeaders([("Location", url)]), 302, compression=self.compression())

	def bounce( self, **kwargs ):
		url = self._environ.get("HTTP_REFERER")
		if url:
			if kwargs: url += "?" + urllib_parse.urlencode(kwargs)
			return Response("", self._mergeHeaders([("Location", url)]), 302, compression=self.compression())
		else:
			assert not kwargs
			return Response("", [], 200, compression=self.compression())

	def returns( self, value=None, raw=False, contentType=None, status=200, headers=None, options=None ):
		if not raw: value = asJSON(value, **(options or {}))
		h = [("Content-Type", contentType or "application/json")]
		if headers: h.extend(headers)
		return Response(value, headers=self._mergeHeaders(h), status=status, compression=self.compression())

	# FIXME: This should be split in respondData or respondStream that would allow to have ranged request
	# support for not only files but arbitrary data

	def respondStream( self, stream, contentType="application/x-binary", status=200, contentLength=True, etag=True, lastModified=None, buffer=1024 * 256 ):
		# FIXME: Attempt at abstracting that
		content_range          = self.header("range")
		range_start, range_end = self.range() or (None, None)
		has_range              = range_start != None and range_end != None
		# We start by looking at the file, if hasn't changed, we won't bother
		# reading it from the filesystem
		has_changed = True
		headers     = []
		# FIXME: Not sure why this would be necessary with etag
		if has_range or (lastModified is not None): #or etag:
			headers.append(("Last-Modified", cache_timestamp(lastModified)))
			modified_since = self.header(self.HEADER_IF_MODIFIED_SINCE)
			try:
				modified_since = time.strptime(modified_since, "%a, %d %b %Y %H:%M:%S GMT")
				if modified_since > lastModified:
					has_changed = False
			except Exception as e:
				pass
		# If the file has changed or if we request ranges or stream
		# then we'll load it and do the whole she bang
		data           = None
		content_length = None
		full_length    = None
		content        = None
		etag_sig       = None
		# We now add the content-type
		headers.append(("Content-Type", contentType))
		if has_changed or has_range:
			# We open the file to get its size and adjust the read length and range end
			# accordingly
			full_length = stream.length()
			if not has_range:
				content_length = full_length
			else:
				if range_end is None:
					range_end      = full_length - 1
					content_length = full_length - range_start
				else:
					content_length = min(range_end - range_start, full_length - range_start)
			if has_range or etag:
				# We don't use the content-type for ETag as we don't want to
				# have to read the whole file, that would be too slow.
				# NOTE: ETag is indepdent on the range and affect the file as a whole
				etag_sig = '"' + stream.etag() + '"'
				headers.append(("ETag",          etag_sig))
			if contentLength is True:
				headers.append(("Content-Length", str(content_length)))
			if has_range:
				headers.append(("Accept-Ranges", "bytes"))
				#headers.append(("Connection",    "Keep-Alive"))
				#headers.append(("Keep-Alive",    "timeout=5, max=100"))
				headers.append(("Content-Range", "bytes %d-%d/%d" % (range_start, range_end, full_length)))
			# This is the generator that will stream the file's content
			def pipe_content(path=path, start=range_start, remaining=content_length):
				stream.open(start or 0)
				while remaining:
					# FIXME: For some reason, we have to read the whole thing in Firefox
					chunk      = stream.read(min(buffer, remaining))
					read       = len(chunk)
					remaining -= read
					if read:
						yield chunk
					else:
						break
			content = pipe_content()
		# File system modification date takes precendence (but for stream we'll test ETag instead)
		if lastModified and not has_changed and not has_range:
			return self.notModified(contentType=contentType)
		# Otherwise we test ETag
		elif etag is True and etag_sig and self.header(self.HEADER_IF_NONE_MATCH) == etag_sig:
			return self.notModified(contentType=contentType)
		# and if nothing works, we'll return the response
		else:
			if has_range: status = 206
			return Response(content=content, headers=self._mergeHeaders(headers), status=status, compression=self.compression())

	def guessContentType( self, path ):
		ext    = path.rsplit(".",1)[-1]
		if ext in MIME_TYPES:
			return MIME_TYPES[ext]
		else:
			res, _ = mimetypes.guess_type(path)
			return res

	def respondFile( self, path, contentType=None, status=200, contentLength=True, etag=True, lastModified=True, buffer=1024 * 256 ):
		"""Responds with a local file. The content type is guessed using
		the 'mimetypes' module. If the file is not found in the local
		filesystem, and exception is raised.

		By default, this method supports caching and will serve both ETags
		and Last-Modified headers, and will also return a 304 not changed
		if necessary.
		"""
		# FIXME: Re-architecture that one, maybe using a FileStream object
		# https://developer.mozilla.org/en-US/docs/Configuring_servers_for_Ogg_media
		# NOTE: This is a fairly complex method that should be broken down
		if not path: return self.notFound()
		path = os.path.abspath(path)
		if not contentType:
			# FIXME: For some reason, sometimes the following call stalls the
			# request (only in production mode!)
			contentType = self.guessContentType(path)
		if not os.path.exists(path):
			return self.notFound("File not found: %s" % (path))
		# We start by guetting range information in case we want/need to do streaming
		# http://benramsey.com/blog/2008/05/206-partial-content-and-range-requests/
		# http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html
		# http://tools.ietf.org/html/rfc2616#section-10.2.7
		content_range  = self.header("range")
		has_range      = content_range and True
		range_start    = None
		range_end      = None
		if content_range:
			content_range = content_range.split("=")
			if len(content_range) > 1:
				content_range = content_range[1].split("-")
				range_start = int(content_range[0] or 0)
				if content_range[1]:
					range_end = int(content_range[1])
				else:
					range_end = None
			else:
				# Range is malformed, so we just skip it
				pass
		# We start by looking at the file, if hasn't changed, we won't bother
		# reading it from the filesystem
		has_changed = True
		headers     = []
		if has_range or lastModified or etag:
			last_modified  = time.gmtime(os.path.getmtime(path))
			headers.append(("Last-Modified", cache_timestamp(last_modified)))
			modified_since = self.header(self.HEADER_IF_MODIFIED_SINCE)
			try:
				modified_since = time.strptime(modified_since, "%a, %d %b %Y %H:%M:%S GMT")
				if modified_since > last_modified:
					has_changed = False
			except Exception as e:
				pass
		# If the file has changed or if we request ranges or stream
		# then we'll load it and do the whole she bang
		data           = None
		content_length = None
		full_length    = None
		content        = None
		etag_sig       = None
		# We now add the content-type
		headers.append(("Content-Type", contentType))
		if has_changed or has_range:
			# We open the file to get its size and adjust the read length and range end
			# accordingly
			with file(path, 'rb') as f:
				f.seek(0,2) ; full_length = f.tell()
				if not has_range:
					content_length = full_length
				else:
					if range_end is None:
						range_end      = full_length - 1
						content_length = full_length - range_start
					else:
						content_length = min(range_end - range_start, full_length - range_start)
			if has_range or etag:
				# We don't use the content-type for ETag as we don't want to
				# have to read the whole file, that would be too slow.
				# NOTE: ETag is indepdent on the range and affect the file is a whole
				etag_sig = '"' + hashlib.sha256("%s:%s" % (path, last_modified)).hexdigest() + '"'
				headers.append(("ETag",          etag_sig))
			if contentLength is True:
				headers.append(("Content-Length", str(content_length)))
			if has_range:
				headers.append(("Accept-Ranges", "bytes"))
				#headers.append(("Connection",    "Keep-Alive"))
				#headers.append(("Keep-Alive",    "timeout=5, max=100"))
				headers.append(("Content-Range", "bytes %d-%d/%d" % (range_start, range_end, full_length)))
			# This is the generator that will stream the file's content
			def pipe_content(path=path, start=range_start, remaining=content_length):
				with file(path, 'rb') as f:
					f.seek(start or 0)
					while remaining:
						# FIXME: For some reason, we have to read the whole thing in Firefox
						chunk      = f.read(min(buffer, remaining))
						read       = len(chunk)
						remaining -= read
						if read:
							yield chunk
						else:
							break
			content = pipe_content()
		# File system modification date takes precendence (but for stream we'll test ETag instead)
		if lastModified and not has_changed and not has_range:
			return self.notModified(contentType=contentType)
		# Otherwise we test ETag
		elif etag is True and etag_sig and self.header(self.HEADER_IF_NONE_MATCH) == etag_sig:
			return self.notModified(contentType=contentType)
		# and if nothing works, we'll return the response
		else:
			if has_range: status = 206
			return Response(content=content, headers=self._mergeHeaders(headers), status=status, compression=self.compression())

	def notFound( self, content="Resource not found", status=404 ):
		"""Returns an Error 404"""
		return Response(content, status=status, compression=False)

	def notModified( self, content="Not modified", status=304, contentType=None):
		"""Returns an OK 304"""
		headers = None
		if contentType: headers = [(self.HEADER_CONTENT_TYPE, contentType)]
		return Response(content, status=status, headers=headers, compression=False)

	def fail( self, content=None,status=412, headers=None ):
		"""Returns an Error 412 with the given content"""
		return Response(content, status=status, headers=self._mergeHeaders(headers), compression=self.compression())

	def cacheID( self ):
		return "%s:%s" % (self.method(), self.uri())

	def _mergeHeaders( self, headersA, headersB=NOTHING ):
		"""Returns headersB + headersA, where headersB is self._responseHeaders
		by default."""
		if headersB is NOTHING: headersB = self._responseHeaders
		if headersB:
			keys     = [_[0] for _ in headersA]
			headersB = [_ for _ in headersB if _[0] not in keys]
			return headersB + headersA
		else:
			return headersA

	def _addParam( self, name, value ):
		"""A wrapper function that will add the given value to the parameters,
		ensuring that:

		- if there is only 1 value, it will be `param[name] = value`
		- if there are more values, it will be `param[name] = [value,value]`

		"""
		if self._params is None: self._params = {}
		# We flatten the  value if it's an array with one element (as this
		# is what is returned when parsing query strings).
		if value and type(value) is list and len(value) == 1: value = value[0]
		if name not in self._params:
			self._params[name] = value
		else:
			if type(self._params[name]) is list:
				self._params[name].append(value)
			else:
				self._params[name] = [self._params[name], value]

	def _addFile( self, name, value ):
		"""A wrapper function to add files. This is used when decoding
		the request body."""
		assert isinstance(value, File)
		if self._files is None: self._files = []
		self._files.append((name, value))

# -----------------------------------------------------------------------------
#
# FILE
#
# -----------------------------------------------------------------------------

class File:
	"""Represents a File object as submitted as POSTED form-data."""

	def __init__( self, data, contentType=None, name=None):
		self.data          = data
		self.contentLength = len(self.data)
		self.name          = name
		self.contentType   = contentType

	# NOTE: This is to keep compatibility with previous Retro API
	def __getitem__( self, name ):
		if hasattr(self, name):
			return getattr(self, name)
		else:
			return None

# -----------------------------------------------------------------------------
#
# REQUEST BODY LOADER
#
# -----------------------------------------------------------------------------

class RequestBodyLoader:
	"""Allows to load the body of a request in chunks and by using a spooled
	memory file so that downloading and processing an incoming request does
	not hog the memory.

	This is an internal class used by the Request class.
	"""

	def __init__( self, request, complete=False ):
		"""Creates a new request body loader. If `complete` is set to `True`,
		then the data request body will be considered as completely read
		and decoded."""
		# NOTE: Referencing request creates a circular reference, so we'll
		# make sure to delete the reference once the load is complete
		# (although Python deals with circular references fine).
		self.request       = request
		self.contentRead   = 0
		self.contentLength = request.contentLength()
		self.contentFile   = None
		self._decoded      = complete
		if complete: self.contentRead = self.contentLength

	def isComplete( self ):
		return self.contentLength == self.contentRead

	def isDecoded( self ):
		return self._decoded

	def remainingBytes( self ):
		return self.contentLength - self.contentRead

	def progress( self, inBytes=False ):
		if inBytes:
			return self.contentRead
		elif self.contentLength > 0:
			return int(100*float(self.contentRead)/float(self.contentLength))
		else:
			return 0

	def load( self, size=None, writeData=True ):
		"""Loads the data in chunks. Return the loaded and writes it to the
		request data and returns it."""
		# If the load is complete, we don't have anything to do
		if self.isComplete(): return None
		if size == None: size = self.contentLength
		to_read   = min(self.remainingBytes(), size)
		read_data = self.request._environ['wsgi.input'].read(to_read)
		self.contentRead += to_read
		assert len(read_data) == to_read
		if writeData: self.request._data.write(read_data)
		return read_data

	def decode( self, dataFile=None ):
		"""Post-processes the data loaded by the loader, this will basically
		parse and decode the data contained in the given data file and
		update the request object according to the data.

		For instance, a (hmultipart) form-encoded data will assign parameters
		and files to the request object, and a JSON content will also assign
		parameters.

		If the encoding is not recognized, then nothing will happen.
		"""
		if self.isDecoded(): return
		dataFile = self.request._data if dataFile is None else dataFile
		# NOTE: See http://www.cs.tut.fi/~jkorpela/forms/file.html
		content_type   = self.request._environ[Request.CONTENT_TYPE] or "application/x-www-form-urlencoded"
		params         = self.request.params(load=False)
		files          = []
		# We handle the case of a multi-part body
		if content_type.startswith('multipart'):
			# TODO: Rewrite this, it fails with some requests
			# Creates an email from the HTTP request body
			lines     = ['Content-Type: %s' % self.request._environ.get(Request.CONTENT_TYPE, '')]
			for key, value in list(self.request._environ.items()):
				if key.startswith('HTTP_'): lines.append('%s: %s' % (key, value))
			# We use a spooled temp file to decode the body, in case the body
			# is really big
			raw_email = tempfile.SpooledTemporaryFile(max_size=64 * 1024)
			raw_email.write('\r\n'.join(lines))
			raw_email.write('\r\n\r\n')
			# We copy the contents of the data file there to enable the decoding
			# FIXME: This could maybe be optimized
			dataFile.seek(0)
			data = dataFile.read()
			raw_email.write(data)
			raw_email.seek(0)
			# And now we decode from the file
			# FIXME: This will probably allocate the whole file in memory
			message   = email.message_from_file(raw_email)
			for part in message.get_payload():
				# FIXME: Should remove that
				part_meta = cgi.parse_header(part['Content-Disposition'])[1]
				if 'filename' in part_meta:
					assert type([]) != type(part.get_payload()), 'Nested MIME Messages are not supported'
					if not part_meta['filename'].strip(): continue
					filename = part_meta['filename']
					filename = filename[filename.rfind('\\') + 1:]
					if 'Content-Type' in part:
						part_content_type = part['Content-Type']
					else:
						part_content_type = None
					param_name = part_meta['name']
					# NOTE: This is also proably going to alloce the whole file in memory
					new_file   = File(
						data        = part.get_payload(),
						contentType = part_content_type,
						name        = filename,
					)
					self.request._addFile (param_name, new_file)
					self.request._addParam(param_name, new_file)
				else:
					value = part.get_payload()
					# TODO: decode if charset
					# value = value.decode(self._charset, 'ignore')
					self.request._addParam(part_meta['name'], value)
			raw_email.close()
		elif content_type.startswith("application/x-www-form-urlencoded"):
			# Ex: "application/x-www-form-urlencoded; charset=UTF-8"
			charset = content_type.split("charset=",1)
			if len(charset) > 1: charset = charset[1].split(";")[0].strip()
			# FIXME: Should this be request.charset instead?
			else: charset = "utf-8"
			dataFile.seek(0)
			data = dataFile.read()
			# NOTE: Encoding is not supported yet
			query_params = cgi.parse_qs(data)
			for k,v in list(query_params.items()): self.request._addParam(k,v)
		elif content_type.startswith("application/json"):
			dataFile.seek(0)
			data = simplejson.load(dataFile)
			if type(data) is dict:
				for key in data:
					self.request._addParam(key, data[key])
			else:
				self.request._addParam("",data)
		else:
			# There is nothing to be decoded, we just need the raw body data
			pass
		# NOTE: We can remove the reference to the request now, as the
		# processing is done.
		self.request  = None
		self._decoded = True

# -----------------------------------------------------------------------------
#
# RESPONSE
#
# -----------------------------------------------------------------------------

# FIXME: setXXX methods should be renamed to XXX
class Response:
	"""A response is sent to a client that sent a request."""

	DEFAULT_CONTENT = "text/html"
	REASONS         = BaseHTTPRequestHandler.responses

	def __init__( self, content=None, headers=None, status=200, reason=None,
	produceWhen=None, compression=None):
		if headers == None: headers = []
		self.status  = status
		self.reason  = reason
		if type(headers) == tuple: headers = list(headers)
		self.headers = [(k,v) for k,v in headers] if headers else [("Accept-Ranges", "bytes")]
		self.content = content
		self.produceEventGuard = None
		self.compression = compression
		self.isCompressed = False

	def cache( self, seconds=0,  minutes=0, hours=0, days=0, weeks=0, months=0, years=0, cacheControl=True, expires=True ):
		duration     = seconds + minutes * 60 + hours * 3600 + days * 3600 * 24 + weeks * 3600 * 24 * 7 + months * 3600 * 24 * 31 + years * 3600 * 24 * 365
		if duration > 0:
			if cacheControl is True:
				self.headers = [h for h in self.headers if h[0] != Request.HEADER_CACHE_CONTROL]
				self.headers.append((Request.HEADER_CACHE_CONTROL, "max-age=%d, public" % (duration)))
			if expires is True:
				expires      = cache_timestamp(time.gmtime(time.time() + duration))
				self.headers.append((Request.HEADER_EXPIRES, expires))
		return self

	def produceOn( self, event ):
		"""Guards the production of the response by this event. This allows the
		reactor (if any) to now when to start."""
		self.produceEventGuard = event
		return self

	def hasHeader(self, name):
		"""Tells if the given header exists. If so, it returns its value (which
		cannot be None), or None if it was not found"""
		name = name.lower()
		for header in self.headers:
			if header[0].lower() == name:
				return header[1]
		return None

	def getHeader( self, name ):
		return self.hasHeader(name)

	def setHeader( self, name, value, replace=True ):
		"""Sets the given header with the given value. If there is already a
		value and that replace is Fasle, nothing will be done."""
		lower_name = name.lower()
		for i in range(0, len(self.headers)):
			header = self.headers[i]
			if header[0].lower() == lower_name:
				if not replace: return self
				self.headers[i] = (name, value)
				return self
		self.headers.append((name, value))
		return self

	def setCookie( self, name, value, path="/" ):
		"""Sets the cookie with the given name and value."""
		# NOTE: This is the same code as a branch of Request.cookie
		found = False
		i     = 0
		for header in self.headers:
			if header[0] == Request.HEADER_SET_COOKIE:
				self.headers[i] = (header[0], "%s=%s; path=%s" % (name, value, path))
				found = True
			i += 1
			break
		if not found:
			self.headers.append((Request.HEADER_SET_COOKIE, "%s=%s; path=%s" % (name, value, path)))
		return self

	def setContentType( self, mimeType ):
		self.headers.append(("Content-Type", mimeType))

	def compress( self, compress=True ):
		if compress and not self.isCompressed:
			if self.compression == "gzip":
				encoding = self.getHeader("Content-Encoding")
				# FIXME: How to support gzip when it's already encoded?
				if not encoding:
					self.content = compress_gzip(self.content)
					self.setHeader("Content-Length", str(len(self.content)), replace=True)
					assert not encoding
					self.setHeader("Content-Encoding", "gzip")
					self.isCompressed = True
		return self

	def prepare( self ):
		"""Sets default headers for the request before sending it."""
		# FIXME: Ensure this is only called once
		self.setHeader("Content-Type", self.DEFAULT_CONTENT, replace=False)

	def asWSGI( self, startResponse, charset=None ):
		"""This is the main WSGI function handler. This is what generates the
		actual request and produces the response from the attached 'content'."""
		# FIXME: Ensure this is only called once
		# TODO: Document this, and explain the use of yield
		self.prepare()
		# TODO: Take care of encoding
		reason = self.REASONS.get(int(self.status)) or self.REASONS[500]
		if reason: reason = reason[0]
		status = "%s %s" % (self.status, self.reason or reason)
		startResponse(status, self.headers)
		def encode(v):
			# The response needs to be str-encoded (binary and not unicode)
			# SEE: File "/usr/lib/python2.7/socket.py", line 316, in write
			#	data = str(data) # XXX Should really reject non-string non-buffers
			if type(v) == unicode:
				return v.encode(charset or "UTF-8")
			else:
				return v
		# If content is a generator we return it as-is
		if type(self.content) == types.GeneratorType:
			# NOTE: We really don't want to wrap the generator in a try/except
			# as otherwise it will swallow the traceback -- Retro now provides
			# good error handlers.
			for c in self.content:
				yield encode(c)
		# Otherwise we return a single-shot generator
		else:
			yield encode(self.content)

	def asString( self ):
		# FIXME: Ensure this is only called once
		self.prepare()
		# TODO: Take care of encoding
		reason = self.REASONS.get(int(self.status)) or self.REASONS[500]
		if reason: reason = reason[0]
		return "%s %s\r\n" % (self.status, self.reason or reason)

# -----------------------------------------------------------------------------
#
# SESSION
#
# -----------------------------------------------------------------------------

class Session:

	def __init__(self):
		pass

	@staticmethod
	def hasSession( request ):
		"""Tells if there is a session related to the given request, and returns
		it if found. If not found, returns None"""

	def isNew( self ):
		"""Tells if the session is a new session or an existing one."""

	def get( self, key=NOTHING, value=NOTHING ):
		"""Alias to 'self.value(key,value)'"""
		return self.value(key, value)

	def value( self, key=NOTHING, value=NOTHING ):
		"""Sets or gets the 'value' bound to the given 'key'"""


CRAWLERS = {'plumtreewebaccessor': True, 'suke': True, 'javabee': True, 'infoseek sidewinder': True, 'checkbot': True, 'patric': True, 'iajabot': True, 'moget': True, 'gcreep': True, 'yes': True, 'w3mir': True, 'jbot (but can be changed by the user)': True, 'borg-bot': True, 'rixbot (http:': True, 'anthillv1.1': True, "'iagent": True, 'webcatcher': True, 'scooter': True, 'openfind data gatherer, openbot': True, 'fish-search-robot': True, "hazel's ferret web hopper,": True, 'grabber': True, 'explorersearch': True, 'combine': True, 'kdd-explorer': True, 'aitcsrobot': True, 'tarspider': True, 'wget': True, 'fido': True, 'weblayers': True, 'esther': True, 'orbsearch': True, 'site valet': True, 'rules': True, 'esculapio': True, 'kit-fireball': True, 'nhsewalker': True, 'lycos': True, 'tlspider': True, 'gestalticonoclast': True, 'road runner: imagescape robot (lim@cs.leidenuniv.nl)': True, 'techbot': True, 'bbot': True, 'spiderbot': True, 'emacs-w3': True, 'w3index': True, 'sitetech-rover': True, 'bspider': True, 'robbie': True, 'portaljuice.com': True, 'poppi': True, 'valkyrie': True, 'cmc': True, 'esismartspider': True, 'diibot': True, 'computingsite robi': True, 'jcrawler': True, "shai'hulud": True, 'appie': True, 'ingrid': True, 'robozilla': True, 'arks': True, 'netcarta cyberpilot pro': True, 'katipo': True, 'infospiders': True, 'i robot 0.4 (irobot@chaos.dk)': True, 'larbin (+mail)': True, 'dienstspider': True, 'solbot': True, 'portalbspider': True, 'evliya celebi v0.151 - http:': True, 'titin': True, 'wwwwanderer v3.0': True, 'ontospider': True, 'linkwalker': True, 'informant': True, 'webreaper [webreaper@otway.com]': True, 'ucsd-crawler': True, 'linkidator': True, 'golem': True, 'pageboy': True, 'atomz': True, 'emc spider': True, 'ebiness': True, 'uptimebot': True, 'spiderman 1.0': True, 'pioneer': True, 'gulper web bot 0.2.4 (www.ecsl.cs.sunysb.edu': True, 'peregrinator-mathematics': True, 'ndspider': True, 'digimarc cgireader': True, 'calif': True, 'geturl.rexx v1.05': True, 'wlm-1.1': True, 'udmsearch': True, 'cienciaficcion.net spider (http:': True, 'fastcrawler 3.0.x (crawler@1klik.dk) - http:': True, 'atn_worldwide': True, 'raven-v2': True, 'marvin': True, 'gammaspider xxxxxxx ()': True, 'webcopy': True, 'coolbot': True, 'freecrawl': True, 'not available': True, 'arachnophilia': True, 'infoseek robot 1.0': True, 'alkalinebot': True, 'aspider': True, 'speedy spider ( http:': True, 'image.kapsi.net': True, 'awapclient': True, 'jubiirobot': True, 'webwalk': True, 'hku www robot,': True, 'momspider': True, 'cusco': True, 'htmlgobble v2.2': True, 'lockon': True, 'vision-search': True, 'cactvs chemistry spider': True, 'tarantula': True, 'perlcrawler': True, 'lwp::': True, 'ssearcher100': True, 'nec-meshexplorer': True, 'googlebot': True, 'boxseabot': True, 'webvac': True, 'dnabot': True, 'ibm_planetwide,': True, 'backrub': True, 'piltdownman': True, 'slurp': True, 'muscatferret': True, 'safetynet robot 0.1,': True, 'motor': True, 'netscoop': True, 'ko_yappo_robot': True, 'northstar': True, 'objectssearch': True, 'digimarc webreader': True, 'webbandit': True, 'spiderline': True, 'jobo (can be modified by the user)': True, 'phpdig': True, 'cyberspyder': True, 'w@pspider': True, 'lwp': True, 'msnbot': True, 'gazz': True, 'esirover v1.0': True, 'sg-scout': True, 'incywincy': True, 'araybot': True, 'jumpstation': True, 'weblinker': True, 'labelgrab': True, 'straight flash!! getterroboplus 1.5': True, 'titan': True, 'packrat': True, 'robofox v2.0': True, 'urlck': True, 'crawlpaper': True, 'wolp': True, "due to a deficiency in java it's not currently possible to set the user-agent.": True, 'resume robot': True, 'webmoose': True, 'dragonbot': True, 'gromit': True, 'nomad-v2.x': True, 'logo.gif crawler': True, "'ahoy! the homepage finder'": True, 'merzscope': True, 'digger': True, 'h\xe4m\xe4h\xe4kki': True, 'libwww-perl-5.41': True, 'none': True, 'legs': True, 'newscan-online': True, 'occam': True, 'linkscan server': True, 'architextspider': True, 'felixide': True, 'robocrawl (http:': True, 'webs@recruit.co.jp': True, 'monster': True, 'elfinbot': True, 'searchprocess': True, 'mwdsearch': True, 'cosmos': True, 'w3m2': True, 'root': True, 'bayspider': True, 'http:': True, 'auresys': True, 'gulliver': True, 'templeton': True, 'israelisearch': True, 'm': True, 'die blinde kuh': True, 'simbot': True, 'snooper': True, 'shagseeker at http:': True, 'duppies': True, 'havindex': True, 'htdig': True, 'pgp-ka': True, 'psbot': True, 'desertrealm.com; 0.2; [j];': True, 'webfetcher': True, 'abcdatos botlink': True, 'no': True, 'wired-digital-newsbot': True, 'bjaaland': True, 'eit-link-verifier-robot': True, 'dlw3robot': True, 'inspectorwww': True, 'nederland.zoek': True, 'magpie': True, 'vwbot_k': True, 'mouse.house': True, 'griffon': True, 'cydralspider': True, 'web robot pegasus': True, 'rhcs': True, 'big brother': True, 'voyager': True, "due to a deficiency in java it's not currently possible": True, 'mindcrawler': True, 'deweb': True, 'webwatch': True, 'netmechanic': True, 'funnelweb-1.0': True, 'void-bot': True, 'victoria': True, 'webquest': True, 'hometown spider pro': True, 'mozilla 3.01 pbwf (win95)': True, 'wwwc': True, 'iron33': True, 'url spider pro': True, 'suntek': True, 'joebot': True, 'dwcp': True, 'verticrawlbot': True, 'whatuseek_winona': True, 'jobot': True, 'webwalker': True, 'xget': True, 'mediafox': True, 'internet cruiser robot': True, 'araneo': True, 'muninn': True, 'roverbot': True, 'robot du crim 1.0a': True, 'senrigan': True, 'blackwidow': True, 'confuzzledbot': True, '???': True, 'parasite': True, 'slcrawler': True}
# EOF - vim: tw=80 ts=4 sw=4 noet
