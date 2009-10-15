#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Retro - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 15-Oct-2009
# -----------------------------------------------------------------------------

__pychecker__ = "unusednames=channel_type,requests_count,request,djtmpl_path"

import os, re, sys, time
from core import Request, Response, BeakerSession, Event, \
RendezVous, asJSON, json, unjson

DEFAULT_LOGFILE  = "retro.log"
TEMPLATE_ENGINES = []
SESSION_ENGINES  = []

try:
	import kid
	kid_serializer = kid.HTMLSerializer()
	kid.enable_import()
	KID = "KID"
	TEMPLATE_ENGINES.append(KID)
except ImportError:
	KID = None

try:
	import genshi
	GENSHI = "GENSHI"
	TEMPLATE_ENGINES.append(GENSHI)
except ImportError:
	GENSHI = None

try:
	# Django support is inspired from the following code
	# http://cavedoni.com/2007/02/venus/planet/shell/dj.py
	try:
		import django.conf, django.template, django.template.loader
	except EnvironmentError:
		# This is really a dirty hack, but I must say that Django
		# really exaggerates when it requires a specific module to
		# hold the configuration.
		os.environ["DJANGO_SETTINGS_MODULE"] = "retro"
		import django.conf, django.template, django.template.loader
	DJANGO = "DJANGO"
	TEMPLATE_ENGINES.append(DJANGO)
except ImportError:
	DJANGO = None

try:
	Cheetah = None
	import Cheetah, Cheetah.Template
	CHEETAH = "CHEETAH"
	TEMPLATE_ENGINES.append(CHEETAH)
except ImportError:
	CHEETAH = None

try:
	from beaker.middleware import SessionMiddleware
	BEAKER_SESSION = "BEAKER"
	SESSION_ENGINES.append(BEAKER_SESSION)
except ImportError:
	BEAKER_SESSION = None
	pass

LOG_ENABLED       = True
LOG_DISPATCHER_ON = True
LOG_TEMPLATE_ON   = True

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
	pass

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

_RAILW_ON              = "_retro_on"
_RAILW_ON_PRIORITY     = "_retro_on_priority"
_RAILW_AJAX            = "_retro_ajax"
_RAILW_AJAX_JSON       = "_retro_ajax_json"
_RAILW_WHEN            = "_retro_when"
_RAILW_TEMPLATE        = "_retro_template"
_RAILW_TEMPLATE_ENGINE = "_retro_template_engine"
_RAILW_IS_PREDICATE    = "_retro_isPredicate"

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
		v = function.__dict__.setdefault(_RAILW_ON, [])
		function.__dict__.setdefault(_RAILW_ON_PRIORITY, priority)
		for http_method, url in methods.items():
			v.append((http_method, url))
		return function
	return decorator

def ajax( priority=0, **methods ):
	"""The @ajax decorator is a variation of the @on decorator. The @ajax
	decorator allows you to _expose_ an existing Python function as a JavaScript
	(or JSON) producing method.

	Basically, the @ajax decorator allows you to automatically bind a method to
	an URL and to ensure that the result will be JSON-ified before being sent.
	This is perfect if you have an existing python class and want to expose it
	to the web."""
	def decorator(function):
		function.__dict__.setdefault(_RAILW_AJAX, True)
		function.__dict__.setdefault(_RAILW_AJAX_JSON, None)
		# This is copy and paste of the @on body
		v = function.__dict__.setdefault(_RAILW_ON,   [])
		function.__dict__.setdefault(_RAILW_ON_PRIORITY, int(priority))
		for http_method, url in methods.items():
			if http_method == "json":
				function.__dict__[_RAILW_AJAX_JSON] = url
			else:
				v.append((http_method, url))
		return function
	return decorator

expose = ajax

def display( template, engine=sys ):
	"""The @display(template) decorator can be used to indicate that the
	decorated  handler will display the given page (only when it returns
	None).
	
	The first argument is the template name with or without the extension (
	it can be guessed at runtime). The second argument is the engine (by
	default, it will be guessed from the extension)"""
	if engine is None:
		raise Exception("Template engine not available")
	elif engine is sys:
		engine = None
	elif not (engine in TEMPLATE_ENGINES):
		raise Exception("Unknown template engine: %s" % (engine))
	def decorator( function ):
		setattr(function, _RAILW_TEMPLATE, template)
		setattr(function, _RAILW_TEMPLATE_ENGINE, engine)
		return function
	return decorator

def predicate(function):
	setattr(function, _RAILW_IS_PREDICATE, True)
	return function

def when( *predicates ):
	"""The @when(...) decorate allows to specify that the wrapped method will
	only be executed when the given predicate (decorated with `@on`)
	succeeds."""
	def decorator( function ):
		v = function.__dict__.setdefault(_RAILW_WHEN, [])
		v.extend(predicates)
		return function
	return decorator

def cache( store ):
	"""The @cache(store) decorator can be used to decorate request handlers and
	cache the response into the given cache object that must have 'has', 'get'
	and 'set' methods, and should be able to store response objects."""
	def decorator( requestHandler ):
		handler_key = str(requestHandler)
		def wrapper( self, request, *args, **kwargs ):
			key = handler_key + str(args) + str(kwargs)
			if store.enabled:
				if store.has(key):
					return store.get(key)
				else:
					response =  requestHandler(self, request, *args, **kwargs)
					store.set(key, response)
					return response
			else:
				return requestHandler(self, request, *args, **kwargs)
		return wrapper
	return decorator

# ------------------------------------------------------------------------------
#
# DISPATCHER
#
# ------------------------------------------------------------------------------

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
		'path'   : (r'.+'        , str   ),
		'segment': (r'[^/]+'     , str   ),
		'any'    : (r'.+'        , str   ),
		'rest'   : (r'.+'        , str   ),
		'range'  : (r'\-?\d*\:\-?\d*', lambda x:x.split(':')),
	}

	def __init__( self, app ):
		"""Creates a new Dispatcher instance. The @_handlers attribute stores
		couple of (regexp, http_handlers)."""
		self._handlers = []
		self._app      = app
		self.patterns  = {}
		for key, value in self.PATTERNS.items():
			self.patterns[key]=value

	def app( self ):
		"""Returns a reference to the Retro application bound to this
		dispatcher."""
		return self._app

	def _parseExpression( self, expression, isStart=True ):
		"""Handler expressions are paths (URLs) that can contain typed variables
		that will match integers, strings, dates, etc, and optional groups.

		Typed variables are like `{name:type}` (where type is optional), and
		optional groups are like `[optional/group]`. Of course, everything can
		be nested."""
		offset   = 0
		result   = ""
		escape   = lambda s:s.replace("/", "\/").replace(".", "\.").replace("+","\+")
		convert  = {}
		params   = None
		if isStart:
			q = expression.rfind("?")
			if q != -1:
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
				# The variable group is like {name} or {name:type}
				variable  = expression[var_group+1:end_group].split(":")
				if len(variable) == 1:
					var_name = variable[0]
					var_type = "chunk"
				elif len(variable) == 2:
					var_name = variable[0]
					var_type = variable[1]
				else:
					raise DispatcherSyntaxError("Variable syntax is {name} or {name:type}, got " + expression[var_group+1:end_group])
				# We warn of unsupported variable type
				if not var_type.lower() in self.patterns.keys():
					result += "(?P<%s>%s)" % (var_name, var_type)
					convert[var_name] = lambda x: x
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
				log("Dispatcher: @on", " ".join(map(lambda x:"%4s" % (x), handlers.keys())), ex)
			regexp, converters, params = self._parseExpression(ex)
			regexp = re.compile(regexp)
			self._handlers.insert(0, (priority, regexp, params, converters, handlers))

	def dispatch(self, environ, path=None, method=None):
		"""Figure out which handler to delegate to or send 404 or 405. This
		returns the handler plus a map of variables to pass to the handler."""
		if path == None: path     = environ['PATH_INFO']
		if method == None: method = environ['REQUEST_METHOD']
		fallback_handler = self.app().notFound
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
				for key in variables.keys():
					variables[key] = converters[key](variables[key])
				# We return the handler along with the variables
				matched_handlers.append((priority, method_handler, variables, params_name))
		if not matched_handlers:
			fallback_handler = self.app().notSupported
		if matched_handlers:
			matched_handlers.sort(lambda a,b:cmp(b[0],a[0]))
			matched_handlers.append((-1, fallback_handler, {}, None))
			return matched_handlers
		elif path and path[0] == "/":
			return self.dispatch(environ, path[1:], method)
		else:
			return [(0, fallback_handler, {}, None)]

	def __call__(self, environ, start_response, request=None):
		"""Delegate request to the appropriate Application. This is the main
		method of the dispatcher."""
		handlers = self.dispatch(environ)
		def handle( handler, variables, start_response):
			# FIXME: Add a charset option
			# We bind the component to the request
			request.environ("retro.start_response", start_response)
			request.environ("retro.variables", variables)
			# TODO: ADD PROPER ERROR HANDLER
			# The app is expected to produce a response object
			response = handler(request, **variables)
			if isinstance(response, Response):
				return response.asWSGI(start_response, self.app().config("charset"))
			# TODO: Add an option to warn on None returned by handlers
			elif response == None:
				response = Response("",[],200)
				return response.asWSGI(start_response, self.app().config("charset"))
			else:
				return response
		# We try the handlers (the fallback handler is contained within the
		# list)
		if request == None:
			request = Request(environ, self.app().config("charset"))
		for _, handler, variables, params_name in handlers:
			can_handle = True
			# NOTE: If there is a failure here (like AttributeError:
			# 'function' object has no attribute 'im_self'), it is
			# probably because the given handler is not a method
			# from a component
			if hasattr(handler, "_component"):
				component = handler._component
			else:
				component = handler.im_self
			request._component = component
			# If there was a required parameter variables, we set the request
			# parameters to it
			if params_name:
				variables[params_name] = request.params()
			if hasattr(handler, _RAILW_WHEN):
				for predicate in getattr(handler, _RAILW_WHEN):
					if not getattr(component, predicate)(request):
						can_handle = False
						break
			if can_handle:
				return handle(handler, variables, start_response)
		assert WebRuntimeError("No handler found")

# ------------------------------------------------------------------------------
#
# COMPONENT
#
# ------------------------------------------------------------------------------

# TODO: Components should be accessible by keys so that they could be passed to
# the Kid templates
class Component:
	"""A Component is a class that contains methods that can handle URLs. Use
	the decorators provided by Retro and register the component into the
	application."""

	PREFIX    = ""
	PRIORITY  = 0
	fromRetro = True

	@staticmethod
	def introspect( component ):
		"""Returns a list of (name, method, {on:...,priority:...,template:...,ajax:...})
		for each slot that was decorated by Retro decorators."""
		res = []
		for slot in dir(component):
			value = getattr(component, slot)
			# We look for components with the "@on" decorator
			if hasattr(value, _RAILW_ON):
				methods  = getattr(value, _RAILW_ON)
				priority = getattr(value, _RAILW_ON_PRIORITY) or 0
				if hasattr(value, _RAILW_TEMPLATE):
					template = getattr(value, _RAILW_TEMPLATE)
					engine   = getattr(value, _RAILW_TEMPLATE_ENGINE)
				else:
					template = engine = None
				if hasattr(value, _RAILW_AJAX):
					ajax_value = getattr(value, _RAILW_AJAX)
				else:
					ajax_value = None
				res.append((slot, value,{
					"on":methods,
					"priority":priority,
					"template":(template, engine),
					"ajax": ajax_value
				}))
		return res

	def __init__( self, name = None, prefix = None ):
		if name == None: name = self.__class__.__name__
		self._name      = name
		self._app       = None
		self._context   = {}
		self._priority  = 0
		self._isRunning = True
		if prefix:
			self.PREFIX = prefix

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
		for http_methods, path in urls:
			handlers = {}
			for method in http_methods.split("_"):
				handlers[method.upper()] = handler
				prefix = self.PREFIX
				if prefix and prefix[0] != "/": self.PREFIX = prefix = "/" + prefix
				priority += self.PRIORITY
				self._app.dispatcher().on(path, prefix=prefix, handlers=handlers, priority=priority)

	def location( self ):
		"""Returns the location for this component. It is guaranteed to start
		with a slash, and not end with one. If it starts with a slash, then
		nothing is returned."""
		loc = self.app().location()
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

	def context( self ):
		return self._context

	def session( self, request, create=True ):
		"""Tells if there is a session attached with this request, creating it
		if `create` is true (by default).
		
		This will required either Flup session middleware or Beaker session
		middleware to be available. The application configuration 'session'
		option will be used to determine which session middleware should be
		used. Beaker is the recommended one, but Flup remains the default one.
		"""
		session_type = self.app().config("session")
		if BEAKER_SESSION and session_type == BEAKER_SESSION:
			res = BeakerSession.hasSession(request)
			if res: return res
			elif create: return BeakerSession(request)
			else: return None
		elif session_type:
			log("Unknown session type: %s" % (session_type))
			return None
		else:
			log("No supported session middleware available")
			return None

	def app( self ):
		return self._app

	def name( self ):
		"""Returns the name for the component."""
		return self._name

	def shutdown( self ):
		"""This will trigger 'onShutdown' in this application and in all the
		registered components."""
		self._isRunning = False
		self.onShutdown()

	def onShutdown( self ):
		"""A stub to be overriden by subclasses."""
	
	def isRunning( self ):
		"""Tells if the component is running."""
		return self._isRunning

	@on(POST="/channels:burst", priority=0)
	def processBurstChannel( self, request ):
		"""The `postRequest` method implements a mechanism that allows the
		Retro _burst channel_ to work properly. It allows to put multiple
		requests into a single request, and then put the corresponding responses
		withing the body of this request."""
		boundary       = request.header("X-Channel-Boundary") or "8<-----BURST-CHANNEL-REQUEST-------"
		channel_type   = request.header("X-Channel-Type")
		requests_count = request.header("X-Channel-Requests")
		requests       = request.body().split(boundary + "\n")
		# We create a fake start response that will simply yield the results
		# The iterate method is a generator that will produce the result
		response_boundary = "8<-----BURST-CHANNEL-RESPONSE-------"
		def iterate(self=self,request=request):
			context = {}
			# When the fake_start_response gets called, we will update the
			# context dict with the response status and header info, so that we
			# can output it within the aggregate response
			def fake_start_response(status, header,context=context):
				s, r = status.split(" ", 1)
				context['status'] = int(s)
				context['reason'] = r
				context['headers'] = header
			has_responded = False
			dispatcher    = self.app()._dispatcher
			# We iterate on each request embedded within the body of this
			# request
			origin = request.uri()
			for request_string in requests:
				req, headers, body = request_string.split("\r\n", 2)
				method, url = req.split(" ",1)
				# We update the current request object (instead of creating one
				# new)
				if not url or url[0] != "/": url = os.path.dirname(origin) + url
				request._environ[request.REQUEST_METHOD]=method
				request._environ[request.REQUEST_URI]=url
				# FIXME: PATH_INFO should be computed properly
				request._environ[request.PATH_INFO]=url
				request.body(body)
				# If we already generated a response, we add the response
				# spearator
				if has_responded:
					yield response_boundary
				# And now we generate the body of the request
				for res in dispatcher(request.environ(), fake_start_response, request):
					if context.items():
						yield "{'status':%s,'reason':%s,'headers':%s,'body':%s}\n\n" % (
							asJSON(context['status']),
							asJSON(context['reason']),
							asJSON(context['headers']),
							asJSON(res)
						)
						del context['status']
						del context['reason']
						del context['headers']
						assert not context.items()
				has_responded = True
		# We respond using the given iterator
		return request.respond(iterate(),headers=[["X-Channel-Boundary", response_boundary]])

# ------------------------------------------------------------------------------
#
# APPLICATION
#
# ------------------------------------------------------------------------------

class Application(Component):

	class TemplateWrapper:
		"""This class allows to wrap a function so that it will display the
		resulting template. This should not be instanciated by the user, but it
		may be good to know that is is created by the Application during the
		@register phase."""

		def __init__(self, component, function, template, engine):
			self.component   = component
			self.im_self     = component
			self.function    = function
			self.template    = template
			self.engine      = engine

		def __call__( self, request, **kwargs ):
			# We try to invoke the function with the request and optional
			# arguments
			r = self.function(request, **kwargs)
			# If it returns a response, then we skip the template processing and
			# display the response
			if r or isinstance(r, Response): return r
			return request.display(self.template, self.engine, **self.component._context)
			# Otherwise we invoke the template
			#context = {'comp':self.component, 'app':self.component._app}
			# Optimize this (context should be inherited, not copied)
			# for key, value in self.component.context().items(): context[key] = value
			#for key, value in request.environ("retro.variables").items(): context[key] = value
			# body = self.component.app().applyTemplate(self.template, **context)
			# return Response(body, [], 200)

		def __str__( self ):
			return "retro.web.TemplateWrapper:%s[%s]:%s" % (self.template, self.engine, self.function)

	class AJAXWrapper:
		"""This class allows to wrap a function so that its result will be
		returned as a JavaScript (JSON) object. As with the @TemplateWrapper.
		this should be not instanciated directly by the user, as it is
		automatically created by the @Application upon component
		registration."""

		def __init__(self, component, function ):
			self.component   = component
			self.im_self     = component
			self.function    = function

		def __call__( self, request, **kwargs ):
			# We try to invoke the function with the optional arguments
			for key, value in request.params().items(): 
				if key: kwargs.setdefault(key, value)
			r = self.function(**kwargs)
			try:
				pass
			except TypeError, e:
				raise ApplicationError(
					"Error when invoking %s" % (self.function),
					"This is probably because there are not enough arguments",
					e
				)
			# And now we return the response as JS
			return request.returns(r, options=getattr(self.function,_RAILW_AJAX_JSON))

	def __init__( self, components=(), prefix='', config=None, defaults=None ):
		Component.__init__(self)
		self._config     = Configuration(path=config, defaults=defaults)
		self._dispatcher = Dispatcher(self)
		self._app        = self
		self._components = []
		self.PREFIX      = prefix
		if type(components) not in (list, tuple): components = [components]
		# We register the components first so that if component try to reference
		# each other at 'start()' phase, it will still work.
		for component in components:
			if type(component) in (list, tuple):
				map(self.register, component)
			else:
				self.register(component)

	def start( self ):
		for component in self._components:
			component.start()

	def notFound(self, request):
		return Response("404 Not Found", [], 404)

	def notSupported(self, request):
		return Response("405 Method Not Supported", [], 405)

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
		for key, value in kwargs.items():
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

	def rootPath( self ):
		"""Returns the absolute path where this application is rooted. This is
		only set at the execution.
		
		This is an alias for 'config("root")'""" 
		return self._config.get("root")

	def localPath( self, path ):
		"""Returns an absolute path expressed relatively to the root."""
		if os.path.abspath(path) == path: return path
		else: return os.path.abspath(os.path.join(self.rootPath(), path))

	def load( self, path ):
		"""Loads the file at the given path and returns its content."""
		f = file(path, 'r')
		t = f.read()
		f.close()
		return t

	def register( self, *components ):
		"""Registeres the given component into this Web application. The
		component handlers will be bound to the proper URLs, and the component
		consistency will be checked against available resources.
		
		This is where all the "gluing" occurs. The component attriutes are
		introspected to see if there are decorated with Retro decorators. If
		so, then the corresponding registration/initialization is made.
		"""
		for component in components:
			if type(component) in (tuple, list):
				apply(self.register, component)
				continue
			assert isinstance(component, Component)
			# FIXME: Make sure that we don't register a component twice
			component._app = self
			# We iterate on the component slots
			for slot, method, handlerinfo in self.introspect(component):
				# We wrape around a template wrapper if necessary
				template = handlerinfo.get("template")
				if template and template != (None, None):
					template, engine = handlerinfo.get("template")
					if not self.ensureTemplate(template, engine):
						raise ApplicationError("No corresponding template for: " + template)
					method = Application.TemplateWrapper(component, method, template, engine)
				# Or aroud an ajax wrapper
				if handlerinfo.get("ajax"):
					method = Application.AJAXWrapper(component, method)
				# We register the handler within the selector
				# FIXME: Handle exception when @on("someurl") instead of @on(GET="someurl")
				component.registerHandler(method,
					handlerinfo.get("on"),
					component.getPriority() + int(handlerinfo.get("priority"))
				)
			if component not in self._components:
				self._components.append(component)

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
		if type(nameOrClass) in (str,unicode):
			nameOrClass = nameOrClass.lower().strip()
			res = filter(lambda c:c.__class__.__name__.lower() == nameOrClass.lower(), self._components)
		else:
			res = filter(lambda c:isinstance(c, nameOrClass), self._components)
		if not res: return None
		elif len(res) == 1: return res[0]
		else: return res

	def _compileCheetahTemplateDeps( self, path ):
		# FIXME: This is really not optimal, we should optimize this
		# like in debug mode, compile all the time, and in live mode
		# compile at start only.
		f = file(path, 'r')
		i = 0
		depends = []
		for line in f:
			if i == 10: break
			line = line.strip()
			if line.startswith("#extends"):
				template = line[len("#extends"):].strip().replace(".", "/") + ".tmpl"
				depends.append(self.ensureTemplate(template, CHEETAH)[1])
			i += 0
		f.close()
		for template in depends:
			dirname  = os.path.dirname(template)
			filename = os.path.basename(os.path.splitext(template)[0])
			temp = Cheetah.Compiler.Compiler(
				file=template,
				moduleName=filename,
				mainClassName=filename
			)
			try:
				temp = str(temp)
			except Cheetah.Parser.ParseError, e:
				raise e
			if temp != None:
				output = open(os.path.splitext(template)[0]+".py", "w")
				output.write("# Encoding: ISO-8859-1\n" + str(temp))
				output.close()
			if not dirname in sys.path:sys.path.append(dirname)

	def ensureTemplate( self, name, engine=None):
		"""Ensures that the a template with the given name exists and returns
		the corresponding path, or None if not found.

		This method supports KID ('.kid'), Cheetah ('.tmpl') or 
		Django('.djtml')."""
		templates = self._config.get("templates")
		if not type(templates) in (list,tuple): templates = [templates]
		for template_dir in templates:
			path        = "%s/%s" % (template_dir, name)
			if os.path.isfile(path):
				if engine:
					return (engine, path)
				elif path.endswith(".kid"):
					return (KID, path)
				elif path.endswith(".tmpl"):
					self._compileCheetahTemplateDeps(path)
					return (CHEETAH, path)
				elif path.endswith(".djtmpl"):
					return (DJANGO, path)
				else:
					raise Exception("Extension unknown and no engine given: %s" % (path))
			kid_path    = "%s/%s.kid"    % (template_dir, name)
			if os.path.isfile(kid_path):
				return  (KID, kid_path)
			tmpl_path   = "%s/%s.tmpl"   % (template_dir, name)
			if os.path.isfile(tmpl_path):
				self._compileCheetahTemplateDeps(path)
				return (CHEETAH, tmpl_path)
			djtmpl_path = "%s/%s.djtmpl" % (template_dir, name)
			if os.path.isfile(tmpl_path):
				return (DJANGO, tmpl_path)
		return (-1, None)

	def applyTemplate( self, name, engine=None, **kwargs ):
		"""Applies the the given arguments to the template with
		the given name. This returns a string with the expanded template. This
		automatically uses the proper template engine, depending on the
		extension:
		
		 - '.kid' for KID templates
		 - '.tmpl' for Cheetah templates
		 - '.dtmpl' for Django templates
		
		"""
		start = time.time()
		res   = None
		templ_type, templ_path = self.ensureTemplate(name, engine)
		# FIXME: Add a proper message handler for that
		#if templ_type is 1:
		#	return "Template not found:" + name
		if not templ_type:
			raise Exception("No matching template engine for template: " + name)
		if templ_type == KID:
			t =  kid.Template(file=templ_path, **kwargs)
			res = t.serialize(output=kid_serializer)
		elif templ_type == CHEETAH:
			# And now we render the template
			template = Cheetah.Template.Template(file=templ_path, searchList=[kwargs])
			res = str(template)
		elif templ_type == DJANGO:
			# FIXME: There is some overhead here, that I think
			# we could try to get rid of.
			import django
			django.conf.settings = django.conf.LazySettings()
			django.conf.settings.configure(
				DEBUG=True, TEMPLATE_DEBUG=True, 
				TEMPLATE_DIRS=(os.path.dirname(templ_path),)
			)
			context = django.template.Context()
			context.update(kwargs)
			template = django.template.loader.get_template(templ_path)
			res = template.render(context)
		if LOG_TEMPLATE_ON:
			log( "Template '%s'(%s) rendered in %ss" % ( templ_path, templ_type, time.time()-start) )
		return res

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
	- `templates` is the path to the templates directory
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
		f = file(path, 'w')
		f.write(json(self._properties, sort_keys=True, indent=4))
		f.close()

	def load( self, path):
		if os.path.exists(path):
			f = file(path, 'r')
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
		for key, value in config.items():
			self.set(key,value)

	def log( self, *args ):
		"""A function to easily log data to the logfile."""
		args = " ".join(map(str, args))
		# Creates the logfile if necessary
		if not self._logfile:
			self._logfile = file(self.get("logfile") or DEFAULT_LOGFILE, 'a')
		# Logs the data
		self._logfile.write(">>> ")
		if type(args) in (tuple,list):
			for a in args: self._logfile.write(str(a) + " ")
		else:
			self._logfile.write(str(args))
		self._logfile.write("\n")
		self._logfile.flush()

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
		return self._properties.items()

	def _abspath( self, path ):
		"""Ensures that the given path is absolute. It will be made relative to
		the root if it is not already absolute."""
		if type(path) in (tuple,list): return map(self._abspath, path)
		abspath = os.path.abspath(path)
		if path != abspath:
			return os.path.abspath(os.path.join(self.get("root") or ".", path))
		else: return path

	def __repr__( self ):
		return json(self._properties, sort_keys=True, indent=4)

# EOF
