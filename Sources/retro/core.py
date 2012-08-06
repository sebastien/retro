#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 08-Aug-2012
# -----------------------------------------------------------------------------

# TODO: Decouple WSGI-specific code and allow binding to Thor

import os, sys, cgi, re, urllib, email, time, types, mimetypes, hashlib
import BaseHTTPServer, Cookie, gzip, cStringIO
import threading

try:
	import json as simplejson
	HAS_JSON = True
except:
	HAS_JSON = False

NOTHING     = sys

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

# ------------------------------------------------------------------------------
#
# JSON PERSISTANCE
#
# ------------------------------------------------------------------------------

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
	if options.has_key("currentDepth"):
		options["currentDepth"] = options["currentDepth"] + 1
	else:
		options["currentDepth"] = 0
	if value in (True, False, None) or type(value) in (float, int, long, str, unicode):
		res = json(value)
	elif type(value) in (list, tuple, set):
		res = "[%s]" % (",".join(map(lambda x:asJSON(x,**options), value)))
	elif type(value) == dict:
		r = []
		for k in value.keys():
			r.append('%s:%s' % (json(k), asJSON(value[k], **options)))
		res = "{%s}" % (",".join(r))
	elif hasattr(value, "__class__") and value.__class__.__name__ == "datetime":
		res = asJSON(tuple(value.timetuple()), **options)
	elif hasattr(value, "__class__") and value.__class__.__name__ == "date":
		res = asJSON(tuple(value.timetuple()), **options)
	elif hasattr(value, "__class__") and value.__class__.__name__ == "struct_time":
		res = asJSON(tuple(value), **options)
	elif hasattr(value, "asJSON")  and callable(value.asJSON):
		res = value.asJSON(asJSON, **options)
	elif hasattr(value, "export") and callable(value.export):
		try:
			value = value.export(**options)
		except:
			value = value.export() 
		res = asJSON(value)
	# The asJS is not JSON, but rather only JavaScript objects, so this implies
	# that there is a library implemented on the client side
	elif hasattr(value, "asJS") and callable(value.asJS):
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

# ------------------------------------------------------------------------------
#
# COMPRESSION
#
# ------------------------------------------------------------------------------
 
def compress_gzip(data):
	out = cStringIO.StringIO()
	f   = gzip.GzipFile(fileobj=out, mode='w')
	f.write(data)
	f.close()
	return out.getvalue()

# ------------------------------------------------------------------------------
#
# EVENT OBJECT
#
# ------------------------------------------------------------------------------

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

	REQUEST_URI    = "REQUEST_URI"
	REQUEST_METHOD = "REQUEST_METHOD"
	CONTENT_TYPE   = "CONTENT_TYPE"
	CONTENT_LENGTH = "CONTENT_LENGTH"
	QUERY_STRING   = "QUERY_STRING"
	HTTP_COOKIE    = "HTTP_COOKIE"
	SCRIPT_NAME    = "SCRIPT_NAME"
	SCRIPT_ROOT    = "SCRIPT_ROOT"
	PATH_INFO      = "PATH_INFO"
	POST           = "POST"
	GET            = "GET"
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
		self._loaded           = False
		self._percentageLoaded = False
		self._loaderIterator   = None
		self._data             = None
		self._component        = None
		self._cookies          = None
		self._files            = None
		self._params           = None
		self._responseHeaders  = []

	def headers( self ):
		if self._headers is None:
			e = self._environ
			headers = {
				"Accept"                      : e.get("HTTP_ACCEPT"),
				"Accept-Charset"              : e.get("HTTP_ACCEPT_CHARSET"),
				"Accept-Encoding"             : e.get("HTTP_ACCEPT_ENCODING"),
				"Accept-Language"             : e.get("HTTP_ACCEPT_LANGUAGE"),
				"Connection"                  : e.get("HTTP_CONNECTION"),
				"Content-Length"              : e.get("HTTP_CONTENT_LENGTH"),
				self.HEADER_CONTENT_TYPE      : e.get("HTTP_CONTENT_TYPE"),
				"Cookie"                      : e.get("HTTP_COOKIE"),
				"Host"                        : e.get("HTTP_HOST"),
				"Keep-Alive"                  : e.get("HTTP_KEEP_ALIVE"),
				"Pragma"                      : e.get("HTTP_PRAGMA"),
				"Referer"                     : e.get("HTTP_REFERER"),
				"User-Agent"                  : e.get("HTTP_USER_AGENT"),
				self.HEADER_CACHE_CONTROL      : e.get("HTTP_CACHE_CONTROL"),
				self.HEADER_IF_MODIFIED_SINCE : e.get("HTTP_IF_MODIFIED_SINCE"),
				self.HEADER_IF_NONE_MATCH     : e.get("HTTP_IF_NONE_MATCH"),
			}
			i = 0
			c = True
			while c:
				k = "HTTP_" + str(i)
				if e.has_key(k):
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
		return self.headers().get(name)

	def method( self ):
		"""Returns the method (GET, POST, etc) for this request."""
		return self._environ.get(self.REQUEST_METHOD)

	def path( self ):
		"""Alias for `self.uri`"""
		return self.uri()

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
		return self._environ.get(self.CONTENT_LENGTH)

	def get( self, name, load=False ):
		"""Gets the parameter with the given name. It is an alias for param"""
		params = self.params(load=load)
		for key, value in params.items():
			if name == key:
				if len(value) == 1: return urllib.unquote(value[0])
				return urllib.unquote(value)
		return None

	def cookies( self ):
		"""Returns the cookies (as a 'Cookie.SimpleCookie' instance)
		attached to this request."""
		if self._cookies != None: return self._cookies
		cookies = Cookie.SimpleCookie()
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

	def param( self, name ):
		"""Gets the parameter with the given name. It is an alias for get"""
		return self.get(name)

	def params( self, load=False ):
		"""Returns a dictionary with the request parameters. Unless you specify
		load as True, this will only return the parameters containes in the
		request URI, not the parameters contained in the form data, in the
		case of a POST."""
		# Otherwise, if the parameters are empty
		if not self._params:
			query = self._environ[self.QUERY_STRING]
			if query:
				# We try to parse the query string
				query_params = cgi.parse_qs(query)
				# TODO: Decode support
				# if not self._charset is None:
					# for key, value in d.iteritems():
						# d[key] = [i.decode(self._charset, 'ignore') for i in value]
				# In some cases we may only have a string as query, so we consider
				# it as a key
				if not query_params:
					query        = urllib.unquote(query)
					query_params = {query:'', '':query}
				self._params = query_params
			else:
				self._params = {}
			# We load if we haven't loaded yet and load is True
			if load and not self._loaded: self.load()
		return self._params

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

	def data( self,data=re ):
		"""Gets/sets the request data (it is an alias for body)"""
		if data == re:
			if not self._loaded: self.load()
			return self._data
		else:
			# We reset the parameters
			self._params = {}
			# We simulate a load if the data was set
			self._environ[self.CONTENT_LENGTH] = len(data)
			self._data = data
			self._loaderIterator   = None
			self._percentageLoaded = 100
			self._loadDecodeBody()
			self._loaded = True

	def body( self, body=re ):
		"""Gets/sets the request body (it is an alias for data)"""
		return self.data(body)

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

	def _loader( self, chunksize=None ):
		"""Returns a generator that loads the data of this request. This will
		gradually update the `_data` attribute."""
		content_length  = int(self._environ[self.CONTENT_LENGTH] or 0)
		remaining_bytes = content_length
		if chunksize == None: chunksize = content_length
		while remaining_bytes > 0:
			if remaining_bytes > chunksize: to_read = chunksize
			else:                           to_read = remaining_bytes
			self._data      += self._environ['wsgi.input'].read(to_read)
			remaining_bytes -= to_read
			self._percentageLoaded = int(100*float(content_length - remaining_bytes) / float(content_length))
			yield to_read
		self._loaderIterator   = None
		self._percentageLoaded = 100
		self._loadDecodeBody()
		self._loaded = True

	def _loadDecodeBody( self ):
		"""Post-processes the data loaded by the loader, this will basically
		convert encoded data into an actual object"""
		content_type   = self._environ[self.CONTENT_TYPE]
		params         = self._params
		# We handle the case of a multi-part body
		if content_type.startswith('multipart'):
			# TODO: Rewrite this, it fails with some requests
			# Creates an email from the HTTP request body
			lines = ['Content-Type: %s' % self._environ.get(self.CONTENT_TYPE, '')]
			for key, value in self._environ.items():
				if key.startswith('HTTP_'): lines.append('%s: %s' % (key, value))
			raw_email = '\r\n'.join(lines) + '\r\n\r\n' + self._data
			message   = email.message_from_string(raw_email)
			for part in message.get_payload():
				names = cgi.parse_header(part['Content-Disposition'])[1]
				if 'filename' in names:
					assert type([]) != type(part.get_payload()), 'Nested MIME Messages are not supported'
					if not names['filename'].strip(): continue
					filename = names['filename']
					filename = filename[filename.rfind('\\') + 1:]
					if 'Content-Type' in part:
						part_content_type = part['Content-Type']
					else:
						part_content_type = None
					param_name = names['name']
					s = {"param":param_name, "filename":filename, "contentType":part_content_type, "data":part.get_payload()}
					self._files.append((param_name, s))
					self._params.setdefault(param_name, part.get_payload())
				else:
					value = part.get_payload()
					# TODO: decode if charset
					# value = value.decode(self._charset, 'ignore')
					params[names['name']] =  value

	def load( self, chunksize=None ):
		"""Loads the (POST) data of this request. The optional @chunksize
		argument tells the number of bytes the should be read. This function
		is used internally, and only useful in an external use if you
		want to split the loading of the data into multiple chunks (using
		an iterator).
		
		This allows you not to block the processing and requests and do
		things like a progress indicator.
		
		This function will return you the percentage of the data loaded
		(an int from 0 to 100). 
		
		Here is an example of how to split the loading into 
		>	while request.load(1024) < 100:
		>		# Do something
		"""
		# If this is the first time we load the request
		if self._percentageLoaded == 0 and self._loaderIterator == None:
			data   = ''
			files  = self._files  = []
			params = self.params(load=False)
			# If this is a post 
			if self.method() == self.POST:
				self._data           = ""
				self._loaderIterator = self._loader(chunksize)
				# If we had no chunksize, we load the full request
				if chunksize == None:
					for _ in self._loaderIterator: pass
				# Or we split the loading of the request
				else:
					self._loaderIterator.next()
			else:
				self._percentageLoaded = 100
				self._loaded           = True
			# We make sure that things like {'param':['value']} gets converted to
			# {'param':'value'}
			for key in params.keys():
				v = params[key]
				if type(v) in (tuple, list) and len(v) == 1: params[key] = v[0]
			self._params = params
			return self._percentageLoaded
		# Otherwise, we iterate through the loader, if any
		elif self._loaderIterator:
			self._loaderIterator.next()
			return self._percentageLoaded
		else:
			return self._percentageLoaded

	def loaded( self ):
		"""Returns the percentage (value between 0 and 100) of this request data
		that was loaded."""
		return self._percentageLoaded

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
		if kwargs: url += "?" + urllib.urlencode(kwargs)
		return Response("", [("Location", url)], 302, compression=self.compression())

	def bounce( self, **kwargs ):
		url = self._environ.get("HTTP_REFERER")
		if url:
			if kwargs: url += "?" + urllib.urlencode(kwargs)
			return Response("", [("Location", url)], 302, compression=self.compression())
		else:
			assert not kwargs
			return Response("", [], 200, compression=self.compression())

	def returns( self, value=None, js=None, contentType="application/json", status=200, headers=None, options=None ):
		if js == None: js = asJSON(value, **(options or {}))
		h = [("Content-Type", contentType)]
		if headers: h.extend(headers)
		return Response(js, headers=self._mergeHeaders(h), status=status, compression=self.compression())

	def respondFile( self, path, contentType=None, status=200, contentLength=True, etag=True, lastModified=True ):
		"""Responds with a local file. The content type is guessed using
		the 'mimetypes' module. If the file is not found in the local
		filesystem, and exception is raised.
		
		By default, this method supports caching and will serve both ETags
		and Last-Modified headers, and will also return a 304 not changed
		if necessary.
		"""
		if not path:
			return self.fail("No path given for image")
		path = os.path.abspath(path)
		if not contentType:
			contentType, _ = mimetypes.guess_type(path)
		if not os.path.exists(path):
			return self.notFound("File not found: %s" % (path))
		# We start by looking at the file, if hasn't changed, we won't bother
		# reading it from the filesystem
		has_changed = True
		headers     = []
		if lastModified is True:
			last_modified  = time.gmtime(os.path.getmtime(path))
			headers.append(("Last-Modified", time.strftime("%a, %d %b %Y %H:%M:%S GMT", last_modified)))
			modified_since = self.header(self.HEADER_IF_MODIFIED_SINCE)
			try:
				modified_since = time.strptime(modified_since, "%a, %d %b %Y %H:%M:%S GMT")
				if modified_since > last_modified:
					has_changed = False
			except Exception, e:
				pass
		# If the file has changed, then we'll load it and do the whoe she bang
		if has_changed:
			# FIXME: This could be improved by returning a generator if the
			# file is too big
			with file(path, 'rb') as f: r = f.read()
			headers.append(("Content-Type", contentType))
			content_sig = None
			if etag is True:
				content_sig    = '"' + hashlib.sha1(r).hexdigest() + '"'
				headers.append(("ETag",          content_sig))
			if contentLength is True:
				content_length = len(r)
				headers.append(("Content-Length", str(content_length)))
		# File system modification date takes precendence
		if   lastModified and not has_changed:
			return self.notModified(contentType=contentType)
		# Otherwise we test ETag
		elif etag is True and content_sig and self.header(self.HEADER_IF_NONE_MATCH) == content_sig:
			return self.notModified(contentType=contentType)
		# and if nothing works, we'll return the response
		else:
			return Response(content=r, headers=self._mergeHeaders(headers), status=status, compression=self.compression())

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
			keys     = map   (lambda _:_[0], headersA)
			headersB = filter(lambda _:_[0] not in keys, headersB)
			return headersB + headersA
		else:
			return headersA

# ------------------------------------------------------------------------------
#
# RESPONSE OBJECT
#
# ------------------------------------------------------------------------------

class Response:
	"""A response is sent to a client that sent a request."""

	DEFAULT_CONTENT = "text/html"
	REASONS = BaseHTTPServer.BaseHTTPRequestHandler.responses

	def __init__( self, content=None, headers=None, status=200, reason=None,
	produceWhen=None, compression=None):
		if headers == None: headers = []
		self.status  = status
		self.reason  = reason
		if type(headers) == tuple: headers = list(headers)
		self.headers = headers or []
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
				expires      = time.gmtime(time.time() + duration)
				expires      = time.strftime("%a, %d %b %Y %H:%M:%S GMT", expires)
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
				if not replace: return
				self.headers[i] = (name, value)
				return
		self.headers.append((name, value))

	def setCookie( self, name, value ):
		"""Sets the cookie with the given name and value."""
		self.headers.append((
			'Set-Cookie',
			'%s=%s; path=/' % (name,value)
		))
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
			if type(v) == unicode:
				return v.encode(charset or "UTF-8")
			else:
				return v
		# If content is a generator we return it as-is
		if type(self.content) == types.GeneratorType:
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

# ------------------------------------------------------------------------------
#
# SESSION OBJECT
#
# ------------------------------------------------------------------------------

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

class BeakerSession(Session):
	"""Implementation of the Session object for Flup Session Middleware"""

	@staticmethod
	def hasSession( request ):
		session = request.environ()['beaker.session']
		if session:
			return BeakerSession(request, session)
		else:
			return None

	def __init__( self, request, session=None ):
		if session is None:
			session = request.environ()['beaker.session']
		self._session = session
		if not session.get("RETRO_SESSION"):
			session["RETRO_SESSION"] = time.time()
			session.save()
			self._isNew = True
		else:
			self._isNew = False

	def isNew( self ):
		return self._isNew

	def get( self, key=NOTHING, value=NOTHING ):
		return self.value(key, value)

	def value( self, key=NOTHING, value=NOTHING ):
		if   key == NOTHING:
			return self._session
		elif value == NOTHING:
			return self._session.get(key)
		else:
			self._session[key] = value
			self._session.save()

	def expire( self, time ):
		raise Exception("Not implemented yet")

# EOF - vim: tw=80 ts=4 sw=4 noet
