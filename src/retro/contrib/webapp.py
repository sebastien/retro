#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 17-Dec-2012
# Last mod  : 21-Apr-2017
# -----------------------------------------------------------------------------

import os, time, sys, datetime, glob
from retro                    import Dispatcher, Application, Component, on, expose, run, asJSON, asPrimitive, escapeHTML, STANDALONE, WSGI, NOTHING
from retro.contrib.localfiles import LibraryServer
from retro.contrib.i18n       import Translations, localize, guessLanguage, DEFAULT_LANGUAGE, setLocales
from retro.contrib.hash       import crypt_decrypt
from retro.contrib.cache      import FileCache, SignatureCache, NoCache, MemoryCache

try:
	import templating
	templating.FORMATTERS["json"]       = lambda v,o,t:asJSON(v)
	templating.FORMATTERS["primitive"]  = lambda v,o,t:asPrimitive(v)
	templating.FORMATTERS["escapeHTML"] = lambda v,o,t:escapeHTML(v)
except ImportError as e:
	pass
	templating = None

try:
	import paml.engine as paml_engine
except ImportError as e:
	paml_engine = None

try:
	import wwwclient
except ImportError as e:
	pass

try:
	import reporter
except ImportError as e:
	pass

__doc__ = """
A set of classes and functions that can be used as a basic building block for
web applications.
"""

APPNAME       = "webapp"
VERSION       = "0.0.0"
PORT          = 8080
LANGUAGE      = DEFAULT_LANGUAGE
LOCALES       = []
E             = lambda v,d,f=(lambda _:_): f(os.environ.get(APPNAME.upper() + "_" + v) or d)
T             = lambda v,l=None: Translations.Get(v,l or LANGUAGE)
API_CACHE     = MemoryCache   ()
LIBRARY_CACHE = SignatureCache()
ON_INIT       = []
info          = lambda _:sys.stdout.write(str(_) + "\n")

# -----------------------------------------------------------------------------
#
# PERMISSIONS
#
# -----------------------------------------------------------------------------

class Permissions:
	"""A singleton that implements authentication-related functions that
	can detect wether a request comes from a connected user and manage a
	sessoin cookie.

	Note that you should set `COOKIE_CONNECTION_SALT` and `CRYPT_KEY` to
	random strings to make sure that the cookies are secure."""

	COOKIE_CONNECTION      = "connection"
	COOKIE_CONNECTION_SALT = "cZBzELXzehqDF7FQfPKs6Rfg"
	CRYPT_KEY              = "vdtwmwq68JWdYhc7RX7EEssMJUkYrNah"

	@classmethod
	def IsConnected( cls, request ):
		"""The connection status is determined by the session cookie."""
		connection_cookie = request.cookie(cls.COOKIE_CONNECTION)
		if connection_cookie and len(connection_cookie) > 64:
			connection_cookie = connection_cookie[:64]
			return connection_cookie == cls.CreateSessionCookie(request)[:64]
		else:
			return False

	@classmethod
	def CreateSessionCookie( cls, request, userid="anonymous" ):
		"""The session cookie is made of two part, separated by a `:`. The
		first part is a salted hash of the client's IP and user agent,
		the second one is an encrypted user id.

		This mechanism is definitely not very secure against cookie stealing,
		as if the attacker has the same IP and uses the same user agent
		he will be able to access this.
		"""
		# FIXME: Add userAgent as well is the first part
		address = str(request.clientIP()) + cls.COOKIE_CONNECTION_SALT
		# FIXME: UserId should be encrypted with some part of the request as well
		user_id = base64.encodestring(crypt_decrypt(str(userid), cls.CRYPT_KEY))[:-1]
		return hashlib.sha256(address).hexdigest() + str(user_id)

	@classmethod
	def GetUserID( cls, request ):
		"""Gets the user ID associated to this request, if any."""
		connection_cookie = request.cookie(cls.COOKIE_CONNECTION)
		if connection_cookie > 64:
			crypted = base64.decodestring(connection_cookie[64:])
			user_id = crypt_decrypt(crypted, cls.CRYPT_KEY)
			if user_id != "anonymous":
				return user_id
		return None

# -----------------------------------------------------------------------------
#
# PAGE SERVER
#
# -----------------------------------------------------------------------------

class PageServer(Component):

	DEFAULTS = dict(
		base    = None,
		prefix  = None,
		lib     = None,
		build   = None,
		version = None,
		site    = APPNAME,
		appname = APPNAME,
		tagline = "",
		year    = time.localtime()[0],
		meta    = dict(
			description = "TODO",
			keywords    = "TODO,TODO,TODO",
			updated     = datetime.date.today().strftime("%Y-%m-%d"),
		)
	)

	def __init__( self, prefix=None ):
		Component.__init__(self, prefix=prefix )
		self._templates = {}
		self.DEFAULTS   = {}

	def mergeDefaults( self, app ):
		for key in self.__class__.DEFAULTS:
			if key not in self.DEFAULTS:
				value = app.config(key)
				if value is None or value is NOTHING:
					self.DEFAULTS[key] = self.__class__.DEFAULTS[key]
				else:
					self.DEFAULTS[key] = value

	def start( self ):
		self.mergeDefaults(self.app)

	# -------------------------------------------------------------------------
	# MAIN PAGES
	# -------------------------------------------------------------------------

	def getUser( self, request ):
		"""Returns the user associated with the given request. Must be
		implemented by subclasses."""
		if hasattr(self.app, "getUser"):
			return self.app.getUser(request)
		else:
			return None

	def listLinks( self ):
		"""Lists the links defined in the base templates"""
		if not wwwclient:
			raise Exception("wwwclient is required")
		else:
			path  =  os.path.join(self.app.config("library.path"))
			links = []
			for ext in ("paml", "html"):
				for tmpl_path in glob.glob(path + "/*/*." + ext):
					tmpl = self.loadTemplate(os.path.basename(tmpl_path).split(".")[0], ext)
					text = self._applyTemplate(tmpl)
					links.extend((_[1] for _ in wwwclient.HTML.links(text)))
			return links

	# -------------------------------------------------------------------------
	# MAIN PAGES
	# -------------------------------------------------------------------------

	@on(GET=("{lang:lang}", "/{lang:lang}", "/{lang:lang}/"), priority=-9)
	@on(GET=("/{lang:lang}{path:rest}"), priority=-10)
	@localize
	def page( self, request, lang=NOTHING, template=None, path="index", templateType=None, properties=None ):
		"""Renders the given `template` (by default, will find it based on the path) in the given `lang`. Templates
		are located in `templates.path`"""
		properties = properties.copy() if properties else {}
		if lang is NOTHING: lang = LANGUAGE
		if path in ("", "/", "/.html") and not template: template == "index"
		properties.setdefault("lang", lang)
		properties.setdefault("page",      path)
		properties.setdefault("path",      path)
		properties.setdefault("template",  template)
		properties.setdefault("title",     Translations.Get("site_title", lang))
		meta = self.DEFAULTS["meta"].copy()
		meta["description"] = Translations.Get("site_description", lang)
		meta["keywords"]    = Translations.Get("site_keywords",    lang)
		properties.setdefault("meta",      meta)
		res = self.render(request, path if not template else template, lang, properties=properties, templateType=templateType )
		return res

	@on(GET=("/favicon.ico"), priority=2)
	def favicon(self, request):
		"""The default favicon handler"""
		return request.respondFile(self.app.config("library.path") + "/images/favicon.ico")

	# -------------------------------------------------------------------------
	# UTILITIES
	# -------------------------------------------------------------------------

	def merge( self, *dicts ):
		"""Merges the given dictionaries with the `DEFAULTS` dictionary."""
		res = self.DEFAULTS.copy()
		for d in dicts:
			res.setdefault("base", self.app.config("base") or "")
			res.update(d)
		return res

	def render( self, request, template, language=None, properties=None, storable=NOTHING, templateType=None, **options ):
		"""Renders a given page `template`, merging the giving `properties`
		in the template environment, and optionally serializing the given
		`storable` so that it becomes available as JSON"""
		properties = properties or {}
		template   = template.split("#")[0].split("?")[0]
		user       = self.getUser(request)
		language   = language or guessLanguage(request)
		if not (storable is NOTHING):
			options["target"] = "web"
			if not storable:
				return request.notFound()
		else:
			storable = None
		path = request.path()
		path = path[len(self.DEFAULTS["base"]):]
		if path.startswith(language): path = path[len(language):]
		context = dict(
			path        = path,
			title       = template,
			language    = language,
			isConnected = user and "true" or "false",
			user        = asPrimitive(user, target="template"),
			object      = asPrimitive(storable, **options),
			cachebuster = time.time(),
			currentUrl  = request.path()
		)
		context  = self.merge(context, properties)
		if self.app.config("devmode") or template not in self._templates:
			tmpl = self.loadTemplate(template, type=templateType)
			self._templates[template] = tmpl
		else:
			tmpl = self._templates[template]
		page = self._applyTemplate(tmpl, context, language)
		response = request.respond(page)
		return response

	def hasTemplate( self, name, type="paml", ext=None ):
		if type=="paml" and not self.app.config("devmode"): type = "html"
		path = os.path.join(self.app.config("library.path"), type, name + (ext if ext else "." + type))
		key  = type + ":" + name
		return key in self._templates or os.path.exists(path)

	def loadTemplate( self, name, raw=False, type=None ):
		"""Loads the template with the given name. By default, this will look into
		the `${library.path}/<type>` configuration path, parse the file as Pamela markup
		and return it as a `templating.Template` instance. If you do not wish to use these
		two modules, simply override this method and return an object that has an
		`apply(properties:dict, lang:str):str` method to fill the templates with the
		given properties in the given language.
		"""
		if type == "paml" or not type:
			return self.loadPAMLTemplate(name, raw)
		else:
			return self.loadPlainTemplate(name, raw, type)

	def loadPlainTemplate( self, name, raw=False, type="html", ext=None  ):
		ext = ext or ("." + type)
		if self.app.config("devmode"):
			path   = os.path.join(self.app.config("library.path"), type, name + ext)
			text   = None
			with open(path, "r") as f: text = f.read()
			# NOTE: We do not cache templates in dev mode
			if raw:
				return text
			else:
				return self._createTemplate(text)
		else:
			key = type + ":" + name + ":raw"
			if key not in self._templates:
				path   = os.path.join(self.app.config("library.path"), type, name + ext)
				text   = None
				with open(path, "r") as f: text   = f.read()
				self._templates[key] = text
			text = self._templates[key]
			if raw:
				return text
			else:
				key = type + ":" + name
				if key not in self._templates:
					assert templating, "retro.contrib.webapp.templating must be defined to use templates"
					result = templating.Template(text)
					self._templates[key] = result
					return result
				else:
					return self._templates[key]

	def loadPAMLTemplate( self, name, raw=False ):
		"""Paml templates are converted to HTML templates in production,
		so we only do the PAML conversion in dev mode"""
		if self.app.config("devmode"):
			# We assume that PAML is only used in devlopment.
			assert paml_engine, "retro.contrib.webapp.loadPAMLTemplate requires the paml.engine module"
			parser = paml_engine.Parser()
			path   = os.path.join(self.app.config("library.path"), "paml", name + ".paml")
			# We load the template plain and parse it with PAML, so that we
			# get a consistent result with the non-devmode HTML step. I
			# tried adding the PAML expansion as a post-processing step
			# but this break the consistency between using the .paml or
			# the .html file (which would each yield a different result)
			text   = self.loadPlainTemplate(name, True, "paml")
			text   = parser.parseString(text, path)
			# NOTE: We do not cache templates in dev mode
			assert templating, "retro.contrib.webapp.templating must be defined to use templates"
			return templating.Template(text)
		else:
			# We assume that paml files are simply pre-compiled to HTML in
			# production, so they fall back to the plain template
			# processing in that case.
			return self.loadPlainTemplate(name, raw, "html")

	def _createTemplate( self, text ):
		"""Creates a new template from the given text. By default, uses the
		`templating` module."""
		assert templating, "templating module is required"
		return templating.Template(text)

	def _applyTemplate( self, tmpl, context=None, language=None ):
		"""Applies the  given context data and the given language to the
		given template. By default, will call `tmpl.apply(context,language)`.
		"""
		return tmpl.apply(context or self.DEFAULTS, language or DEFAULT_LANGUAGE)

# -----------------------------------------------------------------------------
#
# WEB APPLICATION
#
# -----------------------------------------------------------------------------

class WebApp( Application ):

	CONFIG_EXT = ".json"
	DEFAULT_DIRECTORES = ("cache.path", "data.path", "cache.api.path")

	# This is the default configuration for the sphere chat, which is created if an
	# existing configuration is not found.
	@classmethod
	def DefaultConfig( cls, key=None ):
		if key:
			return cls.DefaultConfig().get(key)
		else:
			return {
				"devmode"             : E("DEVMODE",            0,     int),
				"base"                : E("BASE",               "/"),
				"lib"                 : E("LIB",                E("BASE", "/") + "lib"),
				"host"                : E("HOST",               "0.0.0.0"),
				"port"                : E("PORT",               PORT,  int),
				"appname"             : E("APPNAME",            APPNAME),
				"prefix"              : E("PREFIX",             ""),
				"version"             : E("VERSION",            VERSION),
				"build"               : E("BUILD",              "development"),
				"run.path"            : E("RUN_PATH",           os.path.abspath(os.getcwd())),
				"log.path"            : E("LOG_PATH",           os.path.abspath("logs")),
				"data.path"           : E("DATA_PATH",          os.path.abspath("data")),
				"cache.path"          : E("CACHE_PATH",         os.path.abspath("cache")),
				"cache.api.path"      : E("CACHE_PATH",         os.path.abspath("cache")) + "/api",
				"library.path"        : E("LIBRARY_PATH",       os.path.abspath("lib")),
				"library.python.path" : E("LIBRARY_PYTHON_PATH",os.path.abspath(".")),
			}

	def __init__( self, config=None, components=[], pageServer=None, libraryServer=None):
		"""Creates a new webapp, setting the `isProduction` property if `$devmode` is enabled,
		creates the `${cache.path}`, `${data.path}` and `${cache.api.path}` if necessary` and
		registers the given `pageServer`, `libraryServer` and `components`. By default this
		module `PageServer` and `LibraryServer` will be instanciated."""
		global APPLICATION
		APPLICATION = self
		Application.__init__(self,
			defaults  = self.DefaultConfig(),
			config    = config or APPNAME.lower() + self.CONFIG_EXT
		)
		is_production = self.isProduction = (self.config("devmode")!=1)
		if not is_production:
			# On development, we try to import ipdb. If this doesn't work, it's OK
			# as it is merely a nice to have
			try:
				import ipdb
			except ImportError as e:
				pass
		for d in (self.config(_) for _ in self.DEFAULT_DIRECTORES):
			if not os.path.exists(d):
				os.makedirs(d)
		self.isProduction = is_production
		if isinstance(API_CACHE, FileCache):
			API_CACHE.setPath(self.config("cache.api.path"))
		if components is not NOTHING and components is not None:
			components = ([
				(pageServer    or PageServer()) if pageServer is not NOTHING else None,
				(libraryServer or self.createDefaultLibraryServer()) if libraryServer is not NOTHING else None,
			] + components)
			self.register(*components)

	def createDefaultLibraryServer( self ):
		return LibraryServer(
			self.config("library.path"),
			prefix          = self.config("base"),
			cache           = LIBRARY_CACHE,
			cacheAggregates = self.isProduction,
			# NOTE: We don't use minification by default now
			minify          = False,
			compress        = self.isProduction,
			cacheDuration   = self.isProduction and 60 * 60 or 0
		)

# -----------------------------------------------------------------------------
#
# CATCHALL
#
# -----------------------------------------------------------------------------

class Catchall(Component):
	"""Catches all the requests and does a corresponding action"""

	def __init__( self, redirect=None, handler=None, prefix=None ):
		Component.__init__(self, prefix=prefix )
		self.redirect = redirect
		self.handler  = handler
		assert redirect or handler

	@on(GET=("", "{path:any}"), priority=-1)
	def catchall( self, request, path=None ):
		if self.handler:  return self.handler(request)
		else: return request.redirect(self.redirect)

# -----------------------------------------------------------------------------
#
# MAIN
#
# -----------------------------------------------------------------------------

def createApp(config=None, components=None, pageServer=None, libraryServer=None):
	"""Creates the application with given path as config file."""
	return WebApp(config or (APPNAME.lower() + ".json"), components or (), pageServer, libraryServer)

def start( app=None, port=None, runCondition=True, method=None, debug=False, color=False, log=False, config=None ):
	"""Runs the given application (by default created by 'createApp()' as
	standalone."""
	setLocales (LOCALES)
	if (debug or log) and reporter:
		reporter.register(reporter.StdoutReporter(color=color))
		if debug:
			reporter.setLevel(reporter.DEBUG)
	if app is None: app = createApp(config=config)
	name     = app.config("appname")
	port     = port or app.config("port") or PORT
	lib_python_path = app.config("library.python.path")
	method = method or app.config("method") or STANDALONE
	info("Starting Web application {0} on {2}:{3} [{1}] ".format(name, method, app.config("host") or "0.0.0.0", app.config("port")))
	if method == STANDALONE:
		info(app.config)
		info(app.info())
		Dispatcher.EnableLog()
	if not lib_python_path in sys.path:
		sys.path.insert(0, lib_python_path)
	return run(
		app          = app,
		port         = port,
		name         = name,
		method       = method,
		sessions     = False,
		# FIXME: withReactor doesn't work!!
		withReactor  = False,
	)

def command():
	"""Commmand-line handler for webapp"""
	import argparse
	parser = argparse.ArgumentParser(description="Web application command-line arguments")
	parser.add_argument("-p", "--port"   , dest="port"    ,type=int,  default=0,    help="Port to run the webapp (default is {0})".format(PORT))
	parser.add_argument("-d", "--debug"  , dest="debug"   ,type=bool, default=False,help="Enables debugging")
	parser.add_argument("-C", "--color"  , dest="color"   ,type=bool, default=True, help="Enables color output")
	parser.add_argument("-l", "--logging", dest="logging" ,type=bool, default=True, help="Enables logging")
	parser.add_argument("-c", "--config" , dest="config"  ,type=str,  default=None, help="Path to JSON configuration file")
	args = parser.parse_args()
	start(port=args.port, debug=args.debug, color=args.color, log=args.logging, config=args.config)

# This is wrapper to make the module WSGI-compatible (like GUnicorn)
APPLICATION = None
def application(environ, startReponse):
	global APPLICATION
	if not APPLICATION:
		APPLICATION = start(method=WSGI)
		for _ in ON_INIT: _(APPLICATION)
	# We make sure the app is set
	if "retro.app" not in environ: environ["retro.app"] = APPLICATION.stack.app
	return APPLICATION(environ, startReponse)

if __name__ == "__main__":
	start(method=STANDALONE)

# EOF - vim: tw=80 ts=4 sw=4 noet
