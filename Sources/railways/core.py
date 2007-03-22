#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Railways - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 14-Mar-2007
# -----------------------------------------------------------------------------

import os, sys, cgi, re, urllib, email, types, BaseHTTPServer, Cookie
import simplejson

NOTHING     = sys

__doc__ = """\
The Railways _core_ module defines classes that are at the basis of writing a
server-side web application. In this respect, this module defines classes:

 - For `Request` and `Response` management
 - For easy headers and cookies management
 - For `Session` management
 - For JSON/JavaScript serialization

This module could be easily re-used in another application, as it is (almost)
completely standalone and separated from Railways Web applications.
"""

# ------------------------------------------------------------------------------
#
# JSON PERSISTANCE
#
# ------------------------------------------------------------------------------

def asJSON( value, **options ):
	"""Converts the given value to a JSON representation. This function is an
	enhanced version of `simplejson`, because it supports more datatypes
	(datetime, struct_time) and provides more flexibilty in how values can be
	serialized."""
	if value in (True, False, None) or type(value) in (float, int, long, str, unicode):
		res = simplejson.dumps(value)
	elif type(value) in (list, tuple):
		res = "[%s]" % (",".join(map(lambda x:asJSON(x,**options), value)))
	elif type(value) == dict:
		r = []
		for k in value.keys():
			r.append('"%s":%s' % (k, asJSON(value[k], **options)))
		res = "{%s}" % (",".join(r))
	elif value.__class__.__name__ == "datetime":
		res = asJSON(str(value), **options)
	elif value.__class__.__name__ == "struct_time":
		res = asJSON("%04d-%02d-%02d %02d:%02d:%02d" % (value[:6]), **options)
	elif hasattr(value, "asJSON"):
		res = value.asJSON(asJSON, **options)
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

	def __init__( self, environ, charset ):
		"""This creates a new request."""
		self._environ          = environ
		self._charset          = charset
		self._loaded           = False
		self._percentageLoaded = False
		self._loaderIterator   = None
		self._data             = None
		self._component        = None
		self._cookies          = None

	def method( self ):
		"""Returns the method (GET, POST, etc) for this request."""
		return self._environ.get(self.REQUEST_METHOD)

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

	def get( self, name ):
		"""Gets the parameter with the given name. It is an alias for param"""
		if not self._loaded: self.load()
		for key, value in self._params.items():
			if name == key:
				if len(value) == 1: return value[0]
				return value
		return None

	def cookies( self ):
		"""Returns the cookies attached to this request."""
		if self._cookies != None: return self._cookies
		cookies = Cookie.SimpleCookie()
		cookies.load(self.environ(self.HTTP_COOKIE) or '')
		self._cookies = cookies
		return self._cookies

	def has(self, name):
		"""Tells if the request has the given parameter."""
		if not self._loaded: self.load()
		return name in self._params.keys()

	def params( self ):
		"""Returns a dictionary with the request parameters"""
		if not self._loaded: self.load()
		return self._params

	def param( self, name ):
		"""Gets the parameter with the given name. It is an alias for get"""
		return self.get(name)

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
		if name == NOTHING:
			return self._component.session(self)
		elif value == NOTHING:
			return self._component.session(self).value(name)
		else:
			return self._component.session(self).value(name, value)

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
			self._loadPostProcess()
			self._loaded = True
		
	def body( self, body=re ):
		"""Gets/sets the request body (it is an alias for data)"""
		return self.data(body)

	def clientIP( self ):
		"""Returns the HTTP client IP for this request. This method will get the
		HTTP_X_FORWARDED_FOR variable instead of the REMOTE_ADDR if it is set."""
		return self.environ("HTTP_X_FORWARDED_FOR") or self.environ("REMOTE_ADDR")

	def clientPort( self ):
		"""Returns the HTTP client port for this request."""
		return self.environ("REMOTE_PORT")

	def _loader( self, chunksize=None ):
		"""Returns a generator that loads the data of this request."""
		content_length  = int(self._environ[self.CONTENT_LENGTH] or 0)
		remaining_bytes = content_length
		if chunksize == None: chunksize = content_length
		while remaining_bytes > 0:
			if remaining_bytes > chunksize: to_read = chunksize
			else: to_read = remaining_bytes
			self._data      += self._environ['wsgi.input'].read(to_read)
			remaining_bytes -= to_read
			self._percentageLoaded = int(100*float(content_length - remaining_bytes) / float(content_length))
			yield to_read
		self._loaderIterator = None
		self._percentageLoaded = 100
		self._loadPostProcess()
		self._loaded = True

	def _loadPostProcess( self ):
		"""Post-processed the data loaded by the loader."""
		content_type   = self._environ[self.CONTENT_TYPE]
		params         = self._params
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
					s = cgi.FieldStorage(names['name'], filename, part_content_type, part.get_payload())
					self._files.append((names['name'], s))
				else:
					value = part.get_payload()
					# TODO: decode if charset
					# value = value.decode(self._charset, 'ignore')
					params[names['name']] =  value
		# Single content
		else:
			d = cgi.parse_qs(self._data)
			# TODO: Decode support
			# if not self._charset is None:
				# for key, value in d.iteritems():
					# d[key] = [i.decode(self._charset, 'ignore') for i in value]
			for key in d.keys():
				params[key] = d[key]

	def load( self, chunksize=None ):
		"""Loads the (POST) data of this request. The optional @chunksize
		argument tells the number of bytes the should be read"""
		# If this is the first time we load the request
		if self._percentageLoaded == 0 and self._loaderIterator == None:
			data   = ''
			files  = self._files  = []
			params = self._params = {}
			query  = self._environ[self.QUERY_STRING]
			if query:
				# We try to parse the query string
				params = cgi.parse_qs(query)
				# In some cases we may only have a string as query, so we consider
				# it as a key
				if not params:
					query = urllib.unquote(query)
					params = { query:'', '':query}
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

	def respond( self, content="", contentType=None, headers=None, status=200):
		"""Responds to this request."""
		if headers == None: headers = []
		if contentType: headers.append(["Content-Type",str(contentType)])
		return Response(content, headers, status)

	def respondMultiple( self, bodies='', contentType="text/html", headers=None, status=200):
		"""Response with multiple bodies returned by the given sequence or
		iterator. This allows to implement 'server push' very easily."""
		BOUNDARY  = "RAILWAYS-Multiple-content-response"
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
		return Response(bodygenerator(), headers, 200)

	def redirect( self, url, **kwargs ):
		"""Responds to this request by a redirection to the following URL, with
		the given keyword arguments as parameter."""
		if kwargs: url += "?" + urllib.urlencode(kwargs)
		return Response("", [("Location", url)], 302)

	def bounce( self, **kwargs ):
		url = self._environ.get("HTTP_REFERER")
		if url:
			if kwargs: url += "?" + urllib.urlencode(kwargs)
			return Response("", [("Location", url)], 302)
		else:
			assert not kwargs
			return Response("", [], 200)

	def returns( self, value=None, js=None, contentType="text/javascript" ):
		if js == None: js = asJSON(value)
		return Response(js, [("Content-Type", contentType)], 200)

	def display( self, template, engine, **kwargs ):
		"""Returns a response built from the given template, applied with the
		given arguments. The engine parameters (KID, CHEETAH, DJANGO, etc) tells
		which engine should be used to apply the template."""
		return Response(self._applyTemplate(template, engine, **kwargs), [], 200)

	def _applyTemplate(self, template, engine, **kwargs):
		"""Applies the given template with the given arguments, and returns a
		string with the serialized template. This hook is called by the
		`display` method, so you should redefine it to suit your needs."""
		if self._component:
			# This is Railways.Web-specific code
			context = {}
			for key, value in self.environ("railways.variables").items(): context[key] = value
			for key in kwargs.keys(): context[key] = kwargs[key]
			context.setdefault('comp', self._component)
			context.setdefault('component', self._component)
			context.setdefault('app', self._component.app())
			context.setdefault('application', self._component.app())
			context.setdefault('req', self)
			context.setdefault('request', self)
			return self._component.app().applyTemplate(template, engine, **context)
		else:
			raise Exception("Apply template not available for this Request subclass.")

	def localfile( self, path, contentType=None ):
		path = os.path.abspath(path)
		if not contentType:
			if   path.endswith(".js"):  contentType = "text/javascript"
			elif path.endswith(".css"): contentType = "text/css"
			elif path.endswith(".html"): contentType = "text/html"
			else: mime = "text/plain"
		f = file(path, 'r') ; r = f.read() ; f.close()
		return Response(r, [("Content-Type", contentType)], 200)

# ------------------------------------------------------------------------------
#
# RESPONSE OBJECT
#
# ------------------------------------------------------------------------------

class Response:
	"""A response is sent to a client that sent a request."""

	DEFAULT_CONTENT = "text/html"
	REASONS = BaseHTTPServer.BaseHTTPRequestHandler.responses

	def __init__( self, content=None, headers=None, status=200, reason=None):
		if headers == None: headers = []
		self.status  = status
		self.reason  = reason
		self.headers = headers
		self.content = content

	def hasHeader(self, name):
		"""Tells if the given header exists. If so, it returns its value (which
		cannot be None), or None if it was not found"""
		name = name.lower()
		for header in self.headers:
			if header[0].lower() == name:
				return header[1]
		return None

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

	def setContentType( self, mimeType ):
		self.headers.append(("Content-Type", mimeType))

	def prepare( self ):
		"""Sets default headers for the request before sending it."""
		self.setHeader("Content-Type", self.DEFAULT_CONTENT, replace=False)

	def asWSGI( self, startResponse, charset=None ):
		# TODO: Document this, and explain the use of yield
		self.prepare()
		# TODO: Take care of encoding
		reason = self.REASONS.get(int(self.status)) or self.REASONS[500]
		if reason: reason = reason[0]
		status = "%s %s" % (self.status, self.reason or reason)
		startResponse(status, self.headers)
		# If content is a generator we return it as-is
		if type(self.content) == types.GeneratorType:
			for c in self.content:
				yield c
		# Otherwise we return a single-shot generator
		else:
			yield self.content

	def asString( self ):
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

	@staticmethod
	def hasSession( request ):
		"""Tells if there is a session related to the given request, and returns
		it if found. If not found, returns None"""
		service = request.environ()['com.saddi.service.session']
		if service.hasSession:
			return Session(request)
		else:
			return None

	def __init__( self, request ):
		self._service = request.environ()['com.saddi.service.session']
		self._data    = self._service.session

	def isNew( self ):
		return self._service.isSessionNew

	def value( self, key=NOTHING, value=NOTHING ):
		if   key == NOTHING:
			return self._data
		elif value == NOTHING:
			return self._data.get(key)
		else:
			self._data[key] = value

	def expire( self, time ):
		raise Exception("Not implemented yet")

# EOF
