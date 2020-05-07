#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 07-May-2020
# -----------------------------------------------------------------------------

import os, re, sys, time, functools, traceback, io, datetime, urllib
from   retro.core import Request, Response, asJSON, json, unjson, NOTHING, urllib_parse, ensureUnicode, ensureSafeUnicode
from   .compat import *

LOG_ENABLED       = True
LOG_DISPATCHER_ON = False

# Rethink exception handling: where should that be handled? Dispatcher or WSGI?

def log(*args):
	"""A log function that outputs information on stdout. It's a good
	idea to replace this function by another if you want to have a custom
	logger."""
	if LOG_ENABLED is True:
		sys.stdout.write(" ".join(map(str, args)) + "\n")

# ------------------------------------------------------------------------------
#
# ERRORS
#
# ------------------------------------------------------------------------------

class WebRuntimeError(Exception):
	"""An runtime error that is augmented with `code` and `data`, and that
	exports to a JSONable object"""

	def __init__( self, message=None, code=None, data=None ):
		Exception.__init__(self, message)
		self.message = message
		self.code    = code
		self.data    = data

	def export( self ):
		return dict(message=self.message, code=self.code, data=self.data)

	def __str__( self ):
		res = self.message
		if self.code: res = "[{0}] {1}".format(self.code, res)
		if self.data: res = "{0}: {1}".format(res, self.data)
		return res

class DispatcherSyntaxError(Exception):
	"""These errors are raised by the @Dispatcher when the syntax is not as
	expected."""
	pass

class ValidationError(Exception):
	"""Validation errors should be raised by @Component handlers when the
	given parameters (for instance, POST parameters) are not as expected."""

	def asJS( self, asJSON ):
		return asJSON(str(self))

class ApplicationError(Exception):

	def __init__( self, message, explanation=None, exception=None ):
		if explanation: message += " (%s)" % (explanation)
		if exception: message += "\n--> %s" % (exception)
		Exception.__init__(self, message)

# ------------------------------------------------------------------------------
#
# DECORATORS
#
# ------------------------------------------------------------------------------

_RETRO_ON                   = "_retro_on"
_RETRO_ON_PRIORITY          = "_retro_on_priority"
_RETRO_EXPOSE               = "_retro_expose"
_RETRO_EXPOSE_JSON          = "_retro_expose_json"
_RETRO_EXPOSE_RAW           = "_retro_expose_raw"
_RETRO_EXPOSE_COMPRESS      = "_retro_expose_compress"
_RETRO_EXPOSE_CONTENT_TYPE  = "_retro_expose_content_type"
_RETRO_WHEN                 = "_retro_when"
_RETRO_IS_PREDICATE         = "_retro_isPredicate"
_RETRO_EXTRA = (
	_RETRO_ON                   ,
	_RETRO_ON_PRIORITY          ,
	_RETRO_EXPOSE               ,
	_RETRO_EXPOSE_JSON          ,
	_RETRO_EXPOSE_RAW           ,
	_RETRO_EXPOSE_COMPRESS      ,
	_RETRO_EXPOSE_CONTENT_TYPE  ,
	_RETRO_WHEN                 ,
	_RETRO_IS_PREDICATE         ,
)

def updateWrapper( wrapper, f):
	functools.update_wrapper(wrapper, f)
	for _ in _RETRO_EXTRA:
		if hasattr(f, _):
			setattr(wrapper, _, getattr(f, _))
	return wrapper

def on( priority=0, **methods ):
	"""The @on decorator is one of the main important things you will use within
	Retro. This decorator allows to wrap an existing method and indicate that
	it will be used to process an HTTP request.

	The @on decorator can take `GET` and `POST` arguments, which take either a
	string or a list of strings, each describing an URI pattern (see
	@Dispatcher) that when matched, will trigger the method.

	The decorated method must take a `request` argument, as well as the same
	arguments as those used in the pattern.

	For instance:

	>	@on(GET='/list/{what:string}'

	implies that the wrapped method is like

	>	def listThings( self, request, what ):
	>		....

	it is also crucuial to return a a response at the end of the call:

	>		returns request.respond(...)

	The @Request class offers many methods to create and send responses."""
	def decorator(function):
		v = function.__dict__.setdefault(_RETRO_ON, [])
		function.__dict__.setdefault(_RETRO_ON_PRIORITY, priority)
		for http_method, url in list(methods.items()):
			if type(url) not in (list, tuple): url = (url,)
			for _ in url:
				v.append((http_method, _))
		return function
	return decorator

# TODO: We could have an extractor method that would extract sepcific parameters from
# the request body. Ex:
# @expose(POST="/api/ads", name=lambda _:_.get("name"), ....)
def expose( priority=0, compress=False, contentType=None, raw=False, **methods ):
	"""The @expose decorator is a variation of the @on decorator. The @expose
	decorator allows you to _expose_ an existing Python function as a JavaScript
	(or JSON) producing method.

	Basically, the @expose decorator allows you to automatically bind a method to
	an URL and to ensure that the result will be JSON-ified before being sent.
	This is perfect if you have an existing python class and want to expose it
	to the web."""
	def decorator(function):
		function.__dict__.setdefault(_RETRO_EXPOSE, True)
		function.__dict__.setdefault(_RETRO_EXPOSE_JSON, None)
		function.__dict__.setdefault(_RETRO_EXPOSE_RAW , raw)
		function.__dict__.setdefault(_RETRO_EXPOSE_COMPRESS, compress)
		function.__dict__.setdefault(_RETRO_EXPOSE_CONTENT_TYPE, contentType)
		# This is copy and paste of the @on body
		v = function.__dict__.setdefault(_RETRO_ON,   [])
		function.__dict__.setdefault(_RETRO_ON_PRIORITY, int(priority))
		for http_method, url in list(methods.items()):
			if type(url) not in (list, tuple): url = (url,)
			for _ in url:
				if http_method == "json":
					function.__dict__[_RETRO_EXPOSE_JSON] = _
				else:
					v.append((http_method, _))
		return function
	return decorator

def predicate(function):
	setattr(function, _RETRO_IS_PREDICATE, True)
	return function

def when( *predicates ):
	"""The @when(...) decorate allows to specify that the wrapped method will
	only be executed when the given predicate (decorated with `@on`)
	succeeds."""
	def decorator( function ):
		v = function.__dict__.setdefault(_RETRO_WHEN, [])
		v.extend(predicates)
		return function
	return decorator

def restrict( *predicates ):
	"""An alias to `when`"""
	return when(*predicates)

def cache_id(value):
	"""Returns a cache id for the given value"""
	try:
		return getattr(value,"cacheID")()
	except Exception:
		return str(value)

def cache_signature( prefix, args=[], kwargs=dict() ):
	"""Returns the cache signature for the given arguments and keyword arguments"""
	base_key = ",".join(map(cache_id, args))
	rest_key = ",".join([kv[0] + "=" + kv[1] for kv in list(map(cache_id, list(kwargs.items())))])
	key      = prefix + ":" + (",".join((base_key, rest_key)))
	return key

# FIXME: Cache deos not seem to work well when there is an authentication
def cache( store, signature=None ):
	"""The @cache(store) decorator can be used to decorate functions (including request handlers)
	cache the response into the given cache object that must have 'has', 'get'
	and 'set' methods, and should be able to store response objects."""
	def decorator( f ):
		# FIXME: Cache should work with both @expose and @on
		def wrapper( *args, **kwargs ):
			key = cache_signature(f.__name__, args, kwargs) if signature is None else signature(f, args, kwargs)
			if store.enabled:
				result   = None
				if store.has(key):
					result = store.get(key)
				if not result:
					result = f(*args, **kwargs)
					store.set(key, result)
					return result
				else:
					return result
			else:
				return f(*args, **kwargs)
		functools.update_wrapper(wrapper, f)
		return wrapper
	return decorator

# ------------------------------------------------------------------------------
#
# DISPATCHER
#
# ------------------------------------------------------------------------------

class HandlerException(Exception):
	"""Wraps an exception that occured within a handler. This allows to Test
	for this specific type of error (when the callback of the dispatcher failed)."""

	def __init__( self, e, request ):
		self.e       = e
		self.request = request
		self.trace   = traceback.format_exc()
		# NOTE: This is a way to circumvent these awful encoding errors
		if hasattr(self.e, "message"):
			s = ensureUnicode(e.message)
		else:
			s = ensureUnicode(str(e))
		self.message = s
		Exception.__init__(self, s)

	def __str__( self ):
		return self.message

class Dispatcher:
	"""Dispatcher is a WSGI middleware loosely inspired from Luke Arno own
	Selector module, only more tailored to the needs of Retro (that is
	trimmed down and slightly extended).

	The dispatcher is used as follows:

	1) Handlers are registered using the @on method
	2) The dispatch method is called by the Web application
	3) Dispatcher tries to identify a matching handler
	4) It processes the URL into a dict of variables (as declared)
	5) The @__call__ method is invoked
	6) The handler is invoked with the generated variables

	For the story, the main reason for re-implementing Selector instead of
	subclassing it was a license problem: I wanted Retro to be BSD, while
	Selector was GPLed."""

	fromRetro = True
	PATTERNS = {
		'word'   : (r'\w+'       , str   ),
		'alpha'  : (r'[a-zA-Z]+' , str   ),
		'string' : (r'[^/]+'     , str   ),
		'digits' : (r'\d+'       , int   ),
		'number' : (r'\-?\d*\.?\d+' , lambda x:x.find(".") != -1 and float(x) or int(x)),
		'int'    : (r'\-?\d+'       , int   ),
		'integer': (r'\-?\d+'       , int   ),
		'float'  : (r'\-?\d*.?\d+'  , float ),
		'file'   : (r'\w+(.\w+)' , str   ),
		'chunk'  : (r'[^/^.]+'   , str   ),
		'path'   : (r'[^:@]+'   , str   ),
		'segment': (r'[^/]+'     , str   ),
		'any'    : (r'.+'        , str   ),
		'rest'   : (r'.+'        , str   ),
		'range'  : (r'\-?\d*\:\-?\d*', lambda x:x.split(':')),
		'lang'   : (r"((\w\w)/)?", lambda x: x[:-1]),
	}

	@staticmethod
	def EnableLog(value=True):
		global LOG_DISPATCHER_ON
		LOG_DISPATCHER_ON = value
		return LOG_DISPATCHER_ON

	def __init__( self, app ):
		"""Creates a new Dispatcher instance. The @_handlers attribute stores
		couple of (regexp, http_handlers)."""
		self._requestClass = Request
		self._handlers    = []
		self._app         = app
		self.patterns     = {}
		self._routesInfo  = []
		self._onException = []
		for key, value in list(self.PATTERNS.items()):
			self.patterns[key]=value

	@property
	def app( self ):
		"""Returns a reference to the Retro application bound to this
		dispatcher."""
		return self._app

	def onException( self, callback ):
		"""Registers a callback `(exception, dispatcher)` to be called when
		an exception occurs in the handler."""
		self._onException.append(callback)
		return self


	def _parseExpression( self, expression, isStart=True ):
		"""Handler expressions are paths (URLs) that can contain typed variables
		that will match integers, strings, dates, etc, and optional groups.

		Typed variables are like `{name:type}` (where type is optional), and
		optional groups are like `[optional/group]`. Of course, everything can
		be nested."""
		offset   = 0
		result   = ""
		escape   = lambda s:s.replace("/", "\/").replace(".", "\\.").replace("+","\\+").replace("-","\\-").replace("*","\\*")
		convert  = {}
		params   = None
		if isStart:
			q = expression.rfind("?")
			if q != -1:
				open_bracket_before  = expression.rfind("{", 0, q)
				close_bracket_before = expression.rfind("}", 0, q)
				# We want to make sure we're not in a {} block
				if not (open_bracket_before >= 0 and close_bracket_before < open_bracket_before):
					query      = expression[q+1:]
					expression = expression[:q]
					if query: params = query.strip()[1:-1].split(":")[0]
		while expression:
			var_group = expression.find("{")
			opt_group = expression.find("[")
			# We have found a variable group
			if   var_group != -1 and ( var_group < opt_group or opt_group == -1 ):
				result += escape(expression[:var_group])
				end_group = expression.find("}")
				if end_group == -1: raise DispatcherSyntaxError("Unclosed variable block")
				# The variable group is like {name} or {name:type} or {:regexp}
				variable  = expression[var_group+1:end_group].split(":")
				if len(variable) == 1:
					var_name = variable[0]
					var_type = "chunk"
				elif len(variable) == 2:
					var_name = variable[0]
					var_type = variable[1]
				# We warn of unsupported variable type
				if not var_type.lower() in list(self.patterns.keys()):
					if var_name:
						result += "(?P<%s>%s)" % (var_name, var_type)
						convert[var_name] = lambda x: x
					else:
						# This is a regexp
						result += "(%s)" % (var_type)
				else:
					# We generate the expression
					result += "(?P<%s>%s)" % (var_name, self.patterns[var_type.lower()][0])
					if convert.get(var_name):
						raise DispatcherSyntaxError("Two variables with same name: " +
						var_name + " in " + str(convert))
					convert[var_name] = self.patterns[var_type.lower()][1]
				offset = min(end_group + 1, len(expression))
				expression = expression[offset:]
			# Or we found an optional group
			elif opt_group != -1 and ( opt_group < var_group or var_group == -1 ):
				result   += escape(expression[offset:opt_group])
				end_group = expression.rfind("]")
				if end_group == -1: raise DispatcherSyntaxError("Unclosed optional group")
				# The optional group is like [...]
				_result, _convert, _ = self._parseExpression(expression[opt_group+1:end_group], False)
				result   += "(%s)?" % (_result)
				convert.update(_convert)
				offset = min(end_group + 1, len(expression))
				expression = expression[offset:]
			# Or we're done
			else:
				result += escape(expression)
				expression = None
		if isStart: result = "^%s$" % (result)
		return result, convert, params

	# FIXME: That's not used anymore, but I suspect this is useful for debugging
	@staticmethod
	def decomposeExpression( expression ):
		"""Converts the given expression pattern into a list of 'chunks' that
		are tuples (t, chunk), where 't' is 'u' when the chunk is a litteral
		url, 'v' when the chunk is a variable, and 'uo' or 'vo' when the chunk is
		optional."""
		length = len(expression)
		offset = 0
		chunks = []
		# FIXME: Handle optional groups
		while offset < length:
			var_group = expression.find("{", offset)
			opt_group = expression.find("[", offset)
			if var_group == opt_group == -1:
				chunks.append(('u',expression[offset:]))
				break
			if var_group == -1: var_group = length + 1
			if opt_group == -1: opt_group = length + 1
			if var_group < opt_group:
				if var_group != offset: chunks.append(('u',expression[offset:var_group]))
				end_offset = expression.find("}",offset)
				name = expression[var_group+1:end_offset].split(":")[0]
				chunks.append(("v", name))
				offset = end_offset + 1
			else:
				raise Exception("Optional groups not supported yet")
		return chunks

	def on( self, expression, prefix="", handlers={}, priority=0 ):
		"""Tells that the given list of http methods will be handled by the
		associated handlers for the given expression. For instance, you can use
		`on("/{path}", GET=myGetHandler, POST=myPostHandler)
		"""
		if not prefix or prefix[-1] == "/": prefix = prefix[:-1]
		if not type(expression) in (tuple, list): expression = [expression]
		for ex in expression:
			if not ex or ex[0] != "/": ex = "/" + ex
			ex = prefix + ex
			if LOG_DISPATCHER_ON:
				log("Dispatcher:", " ".join(["%4s" % (x) for x in list(handlers.keys())]), ex)
			self._routesInfo.append((list(handlers.keys()), ex))
			regexp_txt, converters, params = self._parseExpression(ex)
			# log("Dispatcher: regexp=", repr(regexp_txt))
			regexp = re.compile(regexp_txt)
			self._handlers.insert(0, (priority, regexp, params, converters, handlers))

	def list( self ):
		return self._routesInfo

	def info( self ):
		res = []
		for methods, url in self._routesInfo:
			res.append("Dispatcher: " + " ".join(["%4s" % (x) for x in methods]) + " " + url)
		return "\n".join(res)

	def match(self, environ, path=None, method=None):
		"""Figure out which handler to delegate to or send 404 or 405. This
		returns the handler plus a map of variables to pass to the handler."""
		if path == None: path     = urllib_parse.unquote(environ['PATH_INFO'])
		if method == None: method = environ['REQUEST_METHOD']
		fallback_handler = self.app.notFound
		matched_handlers = []
		for priority, regexp, params_name, converters, method_dict in self._handlers:
			match = regexp.search(path)
			if not match: continue
			# We check if there was a handler registered for the HTTP
			# request which name corresponds to method (GET, POST, ...)
			method_handler = method_dict.get(method)
			if method_handler != None :
				variables = match.groupdict()
				# We convert the variables to the proper type using the
				# converters
				for key in list(variables.keys()):
					variables[key] = converters[key](variables[key])
				# We return the handler along with the variables
				matched_handlers.append((priority, method_handler, variables, params_name))
		if not matched_handlers:
			fallback_handler = self.app.notSupported
		if matched_handlers:
			# NOTE: Was matched_handlers.sort(lambda a,b:cmp(b[0],a[0]))
			# Make sure this is the same order.
			matched_handlers.sort(key=lambda _:_[0], reverse=True)
			matched_handlers.append((-1, fallback_handler, {}, None))
			return matched_handlers
		elif path and path[0] == "/":
			# If we didn't found any matching handler, we try without the
			# / prefix
			return self.match(environ, path[1:], method)
		else:
			return [(0, fallback_handler, {}, None)]

	def createRequest( self, environ, charset ):
		return self._requestClass(environ, self.app.config("charset"))

	def dispatch( self, environ, handlers=NOTHING, processor=(lambda r,h,v:h(r,**v)), request=None ):
		"""Dispatches the given `environ` or `request` to the given handlers
		previously obtained by calling `match`, returns a `Response` instance."""
		# We try the handlers (the fallback handler is contained within the
		# list)
		if handlers is NOTHING: handlers = self.match(environ)
		if request == None:
			assert environ, "Dispatcher.dispatch: request or environ is required"
			request = self.createRequest(environ, self.app.config("charset"))
		for _, handler, variables, params_name in handlers:
			can_handle = True
			# NOTE: If there is a failure here (like AttributeError:
			# 'function' object has no attribute 'im_self'), it is
			# probably because the given handler is not a method
			# from a component
			component = None
			if hasattr(handler, "_component"):
				component = handler._component
			elif hasattr(handler, "_component"):
				component = handler.__self__
			else:
				# NOTE: We might want to log an error for a missing
				# component.
				pass
			request._component = component
			# If there was a required parameter variables, we set the request
			# parameters to it
			if params_name:
				variables[params_name] = request.params()
			environ["_variables"] = variables
			if hasattr(handler, _RETRO_WHEN):
				for predicate in getattr(handler, _RETRO_WHEN):
					if isinstance(predicate, str):
						predicate = getattr(component, predicate)
					if not predicate(request):
						can_handle = False
						break
			if can_handle:
				try:
					# The processor is expected to take the request,
					# the handler function and the variables.
					return processor(request, handler, variables)
				except Exception as e:
					for _ in self._onException:
						_(e, self)
					raise e if isinstance(e,HandlerException) else HandlerException(e, request)
			else:
				handler = lambda request, **variables: Response("Not authorized",[],401)
				return processor( request, handler, variables)
		assert WebRuntimeError("No handler found")

	#async
	def _processWSGI( self, request, handler, variables, start_response ):
		# FIXME: Add a charset option
		# We bind the component to the request
		request.environ("retro.start_response", start_response)
		request.environ("retro.variables",      variables)
		# TODO: ADD PROPER ERROR HANDLER
		# The app is expected to produce a response object
		response = handler(request, **variables)
		if asyncio_iscoroutine(response):
			return response
		# try:
		# 	response = handler(request, **variables)
		# except Exception as e:
		# 	# NOTE: We do this so that we actually intercept the stack
		# 	# trace where the error occured
		# 	raise HandlerException(e, request)
		if isinstance(response, Response):
			result = response.asWSGI(start_response, self.app.config("charset"))
			return result
		# TODO: Add an option to warn on None returned by handlers
		elif response == None:
			response = Response("",[],200)
			return response.asWSGI(start_response, self.app.config("charset"))
		elif hasattr(response, "asWSGI"):
			return response.asWSGI(start_response, self.app.config("charset"))
		else:
			raise WebRuntimeError("Handler {0} for {1} should return a Response object, got {2}".format(handler, request.path(), response))

	def __call__(self, environ, start_response, request=None):
		"""Delegate request to the appropriate Application. This is the main
		method of the dispatcher, which is WSGI-compatible."""
		processor = lambda r,h,v:self._processWSGI(r,h,v,start_response)
		return self.dispatch(environ, processor=processor, request=request)

# ------------------------------------------------------------------------------
#
# COMPONENT
#
# ------------------------------------------------------------------------------

class Component:
	"""A Component is a class that contains methods that can handle URLs. Use
	the decorators provided by Retro and register the component into the
	application."""

	PREFIX    = ""
	PRIORITY  = 0
	fromRetro = True

	@staticmethod
	def introspect( component ):
		"""Returns a list of (name, method, {on:...,priority:...,expose:...})
		for each slot that was decorated by Retro decorators."""
		res = []
		for slot in dir(component):
			value = getattr(component, slot)
			# We look for components with the "@on" decorator
			if hasattr(value, _RETRO_ON):
				methods  = getattr(value, _RETRO_ON)
				priority = getattr(value, _RETRO_ON_PRIORITY) or 0
				if hasattr(value, _RETRO_EXPOSE):
					expose_value = getattr(value, _RETRO_EXPOSE)
				else:
					expose_value = None
				res.append((slot, value,{
					"on":methods,
					"priority":priority,
					"expose": expose_value
				}))
		return res

	def __init__( self, name=None, prefix=None, priority=None ):
		if name == None: name = self.__class__.__name__
		self._name      = name
		self._app       = None
		self._context   = {}
		self._priority  = self.PRIORITY if priority is None else priority
		self._isRunning = True
		self.startTime  = None
		if prefix:
			self.PREFIX = prefix
		else:
			self.PREFIX = self.__class__.PREFIX

	@property
	def isRunning( self ):
		"""Tells if the component is running."""
		return self._isRunning

	def setPrefix( self, prefix ):
		self.PREFIX = prefix
		return self

	def setPriority( self, level ):
		"""Sets the priority level for this component. The component
		priority level (0 by default) will be added to the individual
		dispatcher priorities."""
		self._priority = int(level)

	def getPriority( self ):
		"""Returns the priority level for this component (usually 0)."""
		return self._priority

	def start( self ):
		"""Start is called when the component is registered within its parent
		application. You can redefine this method to make your custom
		initialization."""
		pass

	def registerHandler(self, handler, urls, priority=0):
		"""This method takes a function, a list of (HTTPMethod,
		DispatcherExpression) and a priority, describing a handler for a
		specific URL within this component. The parameters are actually
		the same as the ones given to the `@on` decorator."""
		if type(urls) is dict: urls = list(urls.items())
		for http_methods, path in urls:
			handlers = {}
			for method in http_methods.split("_"):
				# We need to set a component to the handler
				if not hasattr(handler, "im_self"):
					# NOTE: setattr was not working here
					handler.__dict__["component"] = self
				handlers[method.upper()] = handler
				prefix = self.PREFIX
				if prefix and prefix[0] != "/": self.PREFIX = prefix = "/" + prefix
				priority += self._priority
				self._app.dispatcher().on(path, prefix=prefix, handlers=handlers, priority=priority)

	@property
	def context( self ):
		return self._context

	@property
	def app( self ):
		return self._app

	def config( self, name=re, value=re ):
		return self._app.config(name,value)

	@property
	def name( self ):
		"""Returns the name for the component."""
		return self._name

	@property
	def location( self ):
		"""Returns the location for this component. It is guaranteed to start
		with a slash, and not end with one. If it starts with a slash, then
		nothing is returned."""
		loc = self.app.location
		pre = self.PREFIX
		if not loc or loc[-1] != "/": loc += "/"
		if pre and pre[0] == "/": pre = pre[1:]
		res = loc + pre
		if not res or res[0] != "/": res = "/" + res
		if res and res[-1] == "/": res = res[:-1]
		return res

	def log( self, *args):
		self._app.log(*args)

	def set( self, key, value ):
		self._context[key] = value

	def get( self, key ):
		return self._context.get(key)


	# FIXME: Deprecated, might refactor
	# def session( self, request, create=True ):
	# 	"""Tells if there is a session attached with this request, creating it
	# 	if `create` is true (by default).
	# 	"""
	# 	session_type = self.app.config("session")
	# 	res = Session.hasSession(request)
	# 	if res: return res
	# 	elif create: return Session(request)
	# 	else: return None


	def shutdown( self ):
		"""This will trigger 'onShutdown' in this application and in all the
		registered components."""
		self._isRunning = False
		self.onShutdown()

	def onShutdown( self ):
		"""A stub to be overriden by subclasses."""


# ------------------------------------------------------------------------------
#
# APPLICATION
#
# ------------------------------------------------------------------------------

class Application(Component):

	class EXPOSEWrapper:
		"""This class allows to wrap a function so that its result will be
		returned as a JavaScript (JSON) object.
		This class should be not instanciated directly by the user, as it is
		automatically created by the @Application upon component
		registration."""

		def __init__(self, component, function ):
			self.component     = component
			self.__self__       = component
			self.function      = function
			defaults           = function.__defaults__
			code               = function.__code__
			self.functionArgs  = list(code.co_varnames[:code.co_argcount])

		def __call__( self, request, **kwargs ):
			# We try to invoke the function with the optional arguments
			for key, value in list(request.params().items()):
				if key and (key in self.functionArgs): kwargs.setdefault(key, value)
			r = self.function(**kwargs)
			try:
				pass
			except TypeError as e:
				raise ApplicationError(
					"Error when invoking %s" % (self.function),
					"This is probably because there are not enough arguments",
					e
				)
			# And now we return the response as JS
			return request.returns(
				r,
				contentType=getattr(self.function,_RETRO_EXPOSE_CONTENT_TYPE),
				raw=getattr(self.function,_RETRO_EXPOSE_RAW),
				options=getattr(self.function,_RETRO_EXPOSE_JSON)
			).compress(getattr(self.function,_RETRO_EXPOSE_COMPRESS))

	def __init__( self, components=(), prefix='', config=None, defaults=None ):
		Component.__init__(self)
		if isinstance(config, dict):
			config = Configuration(defaults=defaults).merge(config)
		elif config:
			config = Configuration(path=config, defaults=defaults)
		else:
			config = Configuration(defaults=defaults)
		self.isStarted   = False
		self._config     = config
		self._dispatcher = Dispatcher(self)
		self._app        = self
		self._components = []
		self.PREFIX      = prefix
		if type(components) not in (list, tuple): components = [components]
		# We register the components first so that if component try to reference
		# each other at 'start()' phase, it will still work.
		for component in components:
			if type(component) in (list, tuple):
				for _ in component: self.register(_)
			else:
				self.register(component)

	def info( self ):
		return self._dispatcher.info()

	def start( self ):
		for component in self._components:
			self._startComponent(component)
		self.isStarted = True

	def _startComponent( self, component ):
		component.startTime = datetime.datetime.utcnow()
		component.start()

	def notFound(self, request):
		return Response("404 Not Found", [], 404)

	def notSupported(self, request):
		return Response("404 No resource at the given URI", [], 404)

	@property
	def location( self ):
		"""Returns the location of this application. The location will not
		finish by a slash. If the prefix is `/` then an empty string will be
		returned."""
		pre = self.PREFIX
		if pre and pre[-1] == "/": pre = pre[:-1]
		return pre

	def configure( self, **kwargs ):
		"""Configures this application. The arguments you can use as the same as
		the properites offered by the `Configuration` objects."""
		for key, value in list(kwargs.items()):
			self._config.set(key, value)
		return self

	def dispatcher( self ):
		"""The dispatcher is the main interface between the RW app and the
		webserver. This returns the dispatcher currently bound to the
		application."""
		return self._dispatcher

	def log( self, *args):
		self.config().log(*args)

	def config( self, name=re, value=re ):
		"""Returns the configuration value for the given name. Please note that
		this may raise an exception if the property is not part of the
		configuration properties.

		When no configuration property name is given, the whole configuration is
		returned.
		"""
		if isinstance(name, Configuration):
			self._config = name
			return self._config
		if name == re:
			return self._config
		elif value == re:
			return self._config.get(name)
		else:
			return self._config.set(name, value)

	@property
	def rootPath( self ):
		"""Returns the absolute path where this application is rooted. This is
		only set at the execution.

		This is an alias for 'config("root")'"""
		return self._config.get("root")

	def localPath( self, path ):
		"""Returns an absolute path expressed relatively to the root."""
		if os.path.abspath(path) == path: return path
		else: return os.path.abspath(os.path.join(self.rootPath, path))

	def load( self, path, sync=True, mustExist=False ):
		"""Loads the file at the given path and returns its content."""
		flags = os.O_RDONLY
		# NOTE: On OSX, the following will fail
		try:
			if sync: flags = flags | os.O_RSYNC
		except AttributeError as e:
			pass
		if not mustExist and not os.path.exists(path): return None
		fd    = os.open(path, flags)
		data  = None
		try:
			last_read = 1
			data      = []
			while last_read > 0:
				# FIXME: Should abstract that
				t = os.read(fd, 128000)
				data.append(t)
				last_read = len(t)
			data = b"".join(data)
			os.close(fd)
		except Exception as e:
			os.close(fd)
			raise e
		return data

	def save( self, path, data, sync=True, append=False, mkdir=True ):
		"""Saves/appends to the file at the given path."""
		flags  = os.O_WRONLY | os.O_CREAT
		parent = os.path.dirname(os.path.abspath(path))
		if not os.path.exists(parent) and mkdir: os.makedirs(parent)
		# FIXME: The file is created a +x... weird!
		try:
			if sync:
				flags = flags | os.O_DSYNC
		except AttributeError as e:
			pass
		if append:
			flags = flags | os.O_APPEND
		else:
			flags = flags | os.O_TRUNC
		fd    = os.open(path, flags)
		try:
			os.write(fd, data)
			os.close(fd)
		except Exception as e:
			os.close(fd)
			raise e
		return self

	def append( self, path, data, sync=True ):
		return self.save(path,data,sync=sync,append=True)

	def register( self, *components ):
		"""Registers the given component into this Web application. The
		component handlers will be bound to the proper URLs, and the component
		consistency will be checked against available resources.

		This is where all the "gluing" occurs. The component attriutes are
		introspected to see if there are decorated with Retro decorators. If
		so, then the corresponding registration/initialization is made.
		"""
		for component in components:
			if component is None: continue
			if type(component) in (tuple, list):
				self.register(*component)
				continue
			assert isinstance(component, Component), "retro.web: Cannot register object because it is not a Component instance: {0}".format(component)
			# FIXME: Make sure that we don't register a component twice
			component._app = self
			# We iterate on the component slots
			for slot, method, handlerinfo in self.introspect(component):
				# Or aroud an expose wrapper
				if handlerinfo.get("expose"):
					method = Application.EXPOSEWrapper(component, method)
				# We register the handler within the selector
				# FIXME: Handle exception when @on("someurl") instead of @on(GET="someurl")
				component.registerHandler(method,
					handlerinfo.get("on"),
					component.getPriority() + int(handlerinfo.get("priority"))
				)
			if component not in self._components:
				self._components.append(component)
				if self.isStarted:
					self._startComponent(component)

	def shutdown( self ):
		"""This will trigger 'onShutdown' in this application and in all the
		registered components."""
		Component.shutdown(self)
		for component in self._components:
			component.shutdown()

	def component( self, nameOrClass ):
		"""Returns the component with the given class name (not case sensitive)
		or the component(s) that are instances of the given class. If no
		component matches, 'None' is returned, otherwise the component is
		returned, if there are many, a list of components is returned."""
		res = []
		if type(nameOrClass) in (str,str):
			nameOrClass = nameOrClass.lower().strip()
			res = [c for c in self._components if c.__class__.__name__.lower() == nameOrClass.lower()]
		else:
			res = [c for c in self._components if isinstance(c, nameOrClass)]
		if not res: return None
		elif len(res) == 1: return res[0]
		else: return res

	def __call__(self, environ, start_response, request=None):
		"""Just a proxy to 'Dispatcher.__call__' so that Application can be
		directly used as an WSGI app"""
		return self._dispatcher.__call__(environ, start_response, request=None)

# ------------------------------------------------------------------------------
#
# CONFIGURATION
#
# ------------------------------------------------------------------------------

class Configuration:
	"""Configuration objects allow to store configuration information for
	Retro applications. The supported properties are the following:

	- `name`      is the application name
	- `logfile`   is the path to the log file
	- `charset`   is the default charset for handling request/response data
	- `root`      is the location of the server root (default '.')
	- `session`   is the name of the session adapter (for now, 'FLUP' or 'BEAKER')

	It should be noted that unless absolute, paths are all relative to the
	configured application root, which is set by default to the current working
	directory when the application is first run."""

	def __init__( self, defaults={}, path=None ):
		self._properties = {
			"root"     :".",
			"charset"  :"UTF-8",
			"prefix"   :None,
			"port"     :None,
		}
		self._logfile   = None
		if defaults:
			self.merge(defaults)
		if path:
			self.merge(self.load(path))

	def save( self, path ):
		with open(path, 'w') as f:
			f.write(json(self._properties, sort_keys=True, indent=4))

	def load( self, path):
		if os.path.exists(path):
			with open(path, 'r') as f:
				d = f.read()
				p = {}
				if d:
					p = unjson(d)
			f.close()
			return p
		else:
			return {}

	def merge( self, config ):
		"""Merges the configuration from the given configuration into this
		one."""
		for key, value in list(config.items()):
			self.set(key,value)
		return self

	def set( self, name, value ):
		"""Sets the given property with the given value."""
		self._properties[name] = value

	def setdefault( self, name, value ):
		"""Sets the given property with the given value only if the property did
		not exist before."""
		if not self._properties.get(name):
			self._properties[name] = value

	def get( self, name, value=re):
		"""Returns the value bound to the given property."""
		if value != re:
			self._properties[name] = value
		return self._properties.get(name)

	def items( self ):
		"""Returns the key/values pairs of this configuration."""
		return list(self._properties.items())

	def _abspath( self, path ):
		"""Ensures that the given path is absolute. It will be made relative to
		the root if it is not already absolute."""
		if type(path) in (tuple,list): return list(map(self._abspath, path))
		abspath = os.path.abspath(path)
		if path != abspath:
			return os.path.abspath(os.path.join(self.get("root") or ".", path))
		else: return path

	def __repr__( self ):
		return json(self._properties, sort_keys=True, indent=4)

	def __call__( self, key ):
		return self.get(key)

# EOF - vim: tw=80 ts=4 sw=4 noet
