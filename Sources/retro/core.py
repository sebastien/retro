#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 27-Aug-2012
# -----------------------------------------------------------------------------

# TODO: Decouple WSGI-specific code and allow binding to Thor

import os, sys, cgi, re, urllib, email, time, types, mimetypes, hashlib, tempfile, string
import BaseHTTPServer, Cookie, gzip, StringIO
import threading, locale

# FIXME: Date in cache support should be locale

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

# -----------------------------------------------------------------------------
#
# COMPRESSION

# -----------------------------------------------------------------------------
 
def compress_gzip(data):
	out = StringIO.StringIO()
	f   = gzip.GzipFile(fileobj=out, mode='w')
	f.write(data)
	f.close()
	return out.getvalue()

# -----------------------------------------------------------------------------
#
# AUTHENTICATION
#
# -----------------------------------------------------------------------------

def crypt_decrypt(text, password):
	"""XOR encryption, decryption"""
	# FROM :http://www.daniweb.com/software-development/python/code/216632/text-encryptiondecryption-with-xor-python
	old = StringIO.StringIO(text)
	new = StringIO.StringIO(text)
	for position in xrange(len(text)):
		bias = ord(password[position % len(password)])  # Get next bias character from password
		old_char = ord(old.read(1))
		new_char = chr(old_char ^ bias)  # Get new charactor by XORing bias against old character
		new.seek(position)
		new.write(new_char)
	new.seek(0)
	return new.read()

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
		name = "-".join(map(string.capitalize, name.split("-")))
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
		return int(self._environ.get(self.CONTENT_LENGTH) or 0)

	def get( self, name, load=False ):
		"""Gets the parameter with the given name. It is an alias for param"""
		params = self.params(load=load)
		return params.get(name)

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
					query        = urllib.unquote(query)
					query_params = {query:'', '':query}
				for k,v in query_params.items(): self._addParam(k,v)
			else:
				self._params = {}
			# We load if we haven't loaded yet and load is True
			if load and not self.isLoaded(): self.load()
		return self._params

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

	def data( self, data=re, asFile=False ):
		"""Gets/sets the request data as a file object. Note that when using
		the `asFile` object, you should be sure to not do any concurrent access
		to the data as a file, as you'll use the same file descriptor.
		"""
		if data == re:
			while not self.isLoaded(): self.load()
			if asFile:
				# NOTE: Mabe we should use dup
				self._data.seek(0)
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

	def body( self, body=re ):
		"""Gets/sets the request body (it is an alias for data)"""
		return self.data(body)

	def isLoaded( self ):
		"""Tells wether the request's body is loaded or not"""
		if self._bodyLoader: return self._bodyLoader.isComplete()
		else: return False

	def loadProgress( self ):
		"""Returns an integer (0-100) that shows the load progress."""
		if self._bodyLoader: return self._bodyLoader.progress()
		else: return 0

	def load( self, size=None ):
		"""Loads `size` more bytes (all by default) from the request
		body."""
		# We make sure that the body loader exists
		if not self._bodyLoader: self._bodyLoader = RequestBodyLoader(self)
		# And then if it is not complete, 
		if not self._bodyLoader.isComplete():
			self._data.write(self._bodyLoader.load(size))
			# If the the body loader is complete, we'll now proceed
			# with the decoding of the request, which will convert the data
			# into params and fields.
			if self._bodyLoader.isComplete():
				self._bodyLoader.decode(self._data)
		return self

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
# REQUEST BODY LOADER
#
# -----------------------------------------------------------------------------

class File:

	def __init__( self, data, contentType=None, name=None):
		self.data          = data
		self.contentLenght = len(self.data)
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
	"""Allows to load the body of a request in chunks. This is an internal
	class that's used by Request.
	"""

	def __init__( self, request, complete=False ):
		# NOTE: Referencing request creates a circular reference, so we'll
		# make sure to delete the reference once the load is complete
		# (although Python deals with circular references fine).
		self.request       = request
		self.contentRead   = 0
		self.contentLength = request.contentLength()
		self.contentFile   = None
		if complete: self.contentRead = self.contentLength
		# FIXME: Deprecated
		# self.contentType   = request.contentType()
		# self.params        = request.params(load=False)
		# self.headers       = []
		# # This is used by decode
		# for key, value in request._environ.items():
		# 	if key.startswith('HTTP_'): self.headers.append('%s: %s' % (key, value))

	def isComplete( self ):
		return self.contentLength == self.contentRead

	def remainingBytes( self ):
		return self.contentLength - self.contentRead

	def progress( self ):
		return int(100*float(self.contentRead)/float(self.contentLength))

	def load( self, size=None ):
		"""Loads the data in chunks. Return the loaded chunk -- it's up to
		you to store and process it."""
		# If the load is complete, we don't have anything to do
		if self.isComplete(): return None
		if size == None: size = self.contentLength
		to_read   = min(self.remainingBytes(), size)
		read_data = self.request._environ['wsgi.input'].read(to_read)
		self.contentRead += to_read
		assert len(read_data) == to_read
		return read_data

	def decode( self, dataFile ):
		"""Post-processes the data loaded by the loader, this will basically
		convert encoded data into an actual object"""
		# NOTE: See http://www.cs.tut.fi/~jkorpela/forms/file.html
		if not self.request: raise Exception("Body already decoded")
		content_type   = self.request._environ[Request.CONTENT_TYPE]
		params         = self.request.params(load=False)
		files          = []
		# We handle the case of a multi-part body
		if content_type.startswith('multipart'):
			# TODO: Rewrite this, it fails with some requests
			# Creates an email from the HTTP request body
			lines     = ['Content-Type: %s' % self.request._environ.get(Request.CONTENT_TYPE, '')]
			for key, value in self.request._environ.items():
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
			# And now we docode from the file
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
			for k,v in query_params.items(): self.request._addParam(k,v)
		else:
			# There is nothing to be decoded, we just need the raw body data
			pass
		# NOTE: We can remove the reference to the request now, as the
		# processing is done.
		self.request = None

# -----------------------------------------------------------------------------
#
# RESPONSE
#
# -----------------------------------------------------------------------------

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
			if type(v) == unicode:
				return v.encode(charset or "UTF-8")
			else:
				return v
		# If content is a generator we return it as-is
		if type(self.content) == types.GeneratorType:
			# we wrap the generator in a try/except
			try:
				for c in self.content:
					yield encode(c)
			except Exception, e:
				raise e
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

# EOF - vim: tw=80 ts=4 sw=4 noet
