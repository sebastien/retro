#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 17-Dec-2012
# Last mod  : 17-Dec-2012
# -----------------------------------------------------------------------------

import os, time, sys, datetime
from retro                    import *
from retro.contrib.localfiles import LibraryServer
from retro.contrib.i18n       import Translations, localize, guessLanguage, DEFAULT_LANGUAGE
from retro.contrib.hash       import crypt_decrypt
from retro.contrib.cache      import FileCache, SignatureCache


__doc__ = """
A set of classes and functions that can be used as a basic building block for
web applications.
"""

APPNAME       = "webapp"
VERSION       = "0.0.0"
PORT          = 8080
LANGUAGE      = DEFAULT_LANGUAGE
E             = lambda v,d,f=(lambda _:_): f(os.environ.get(APPNAME + "_"+v) or d)
T             = lambda v,l=None: Translations.Get(v,l or LANGUAGE)
NOTHING       = os
API_CACHE     = FileCache()
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
	def GetUserId( cls, request ):
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
		base    = "/",
		site    = APPNAME,
		tagline = "",
		year    = time.localtime()[0],
		version = VERSION,
		meta    = dict(
			description = "TODO",
			keywords    = "TODO,TODO,TODO",
			updated     = datetime.date.today().strftime("%Y-%m-%d"),
		)
	)

	def __init__( self ):
		Component.__init__(self)
		self._templates = {}

	def start( self ):
		self.DEFAULTS["version"] = self.app().config("version") or self.DEFAULTS.get("version")
		self.DEFAULTS["build"]   = self.app().config("build")

	# -------------------------------------------------------------------------
	# MAIN PAGES
	# -------------------------------------------------------------------------

	def getUser( self, request ):
		"""Returns the user associated with the given request. Must be
		implemented by subclasses."""
		raise NotImplementedError


	# -------------------------------------------------------------------------
	# MAIN PAGES
	# -------------------------------------------------------------------------

	@on(GET=("{lang:lang}", "/{lang:lang}"), priority=-9)
	@on(GET=("/{lang:lang}{template:rest}"), priority=-10)
	@localize
	def page( self, request, lang=NOTHING, template="index" ):
		"""Renders the given `template` in the given `lang`. Templates
		are located in `templates.path`"""
		properties = {}
		if lang is NOTHING: lang = LANGUAGE
		if template in ("", "/", "/.html"): template == "index"
		if template == "index":
			properties["title"] = Translations.Get("site_title", lang)
			meta = self.DEFAULTS["meta"].copy()
			meta["description"] = Translations.Get("site_description", lang)
			meta["keywords"]    = Translations.Get("site_keywords",    lang)
			properties["meta"]  = meta
		return self.render(request, template, guessLanguage(request), properties=properties)

	@on(GET=("/favicon.ico"), priority=2)
	def favicon(self, request):
		"""The default favicon handler"""
		return request.respondFile(self.app().config("library.path") + "/images/favicon.ico")

	# -------------------------------------------------------------------------
	# UTILITIES
	# -------------------------------------------------------------------------

	def merge( self, *dicts ):
		"""Merges the given dictionaries with the `DEFAULTS` dictionary."""
		res = self.DEFAULTS.copy()
		for d in dicts:
			res.setdefault("base", self.app().config("base") or "")
			res.update(d)
		return res

	def render( self, request, template, language=None, properties=None, storable=NOTHING, **options ):
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
		context = dict(
			page        = template,
			title       = template,
			prefix      = self.app().config("prefix"),
			language    = language,
			isConnected = user and "true" or "false",
			user        = asJSON(user, target="template").replace('"',  "&quot;"),
			object      = asJSON(storable, **options).replace('"',  "&quot;"),
			cachebuster = time.time(),
			currentUrl  = request.path()
		)
		context  = self.merge(context, properties)
		if self.app().config("devmode") or not self._templates.has_key(template):
			tmpl = self.loadTemplate(template)
			self._templates[template] = tmpl
		else:
			tmpl = self._templates[template]
		page     = tmpl.apply(context, language)
		response = request.respond(page)
		return response

	def loadTemplate( self, name, raw=False ):
		"""Loads the template with the given name. By default, this will look into
		the `${library.path}/paml` configuration path, parse the file as Pamela markup
		and return it as a `templating.Template` instance. If you do not wish to use these
		two modules, simply override this method and return an object that has an
		`apply(properties:dict, lang:str):str` method to fill the templates with the 
		given properties in the given language.
		"""
		if self.app().config("devmode"):
			import pamela.engine
			parser = pamela.engine.Parser()
			path   = os.path.join(self.app().config("library.path"), "paml", name + ".paml")
			text   = None
			with file(path, "r") as f: text   = f.read()
			text   = parser.parseString(text, path)
		else:
			key = name + ":raw"
			if not self._templates.has_key(key):
				path   = os.path.join(self.app().config("library.path"), "html", name + ".html")
				text   = None
				with file(path, "r") as f: text   = f.read()
				self._templates[key] = text
			text = self._templates[key]
		if raw:
			return text
		else:
			import templating
			return templating.Template(text)

# -----------------------------------------------------------------------------
#
# WEB APPLICATION
#
# -----------------------------------------------------------------------------

class WebApp( Application ):

	# This is the default configuration for the sphere chat, which is created if an
	# existing configuration is not found.
	@classmethod
	def DefaultConfig( cls ):
		return {
			"devmode"             : E("DEVMODE",            0,     int),
			"base"                : E("BASE",               ""),
			"port"                : E("PORT",               PORT,  int),
			"appname"             : E("APPNAME",            APPNAME),
			"prefix"              : E("PREFIX",             ""),
			"version"             : E("VERSION",            VERSION),
			"build"               : E("BUILD",              "development"),
			"data.path"           : E("DATA_PATH",          os.path.abspath("Data")),
			"cache.path"          : E("CACHE_PATH",         os.path.abspath("Cache")),
			"log.path"            : E("LOG_PATH",           os.path.abspath("Logs")),
			"cache.api.path"      : E("CACHE_PATH",         os.path.abspath("Cache")) + "/api",
			"workqueue.path"      : E("CACHE_PATH",         os.path.abspath("Data/_workqueue")),
			"library.path"        : E("LIBRARY_PATH",       os.path.abspath("Library")),
			"library.python.path" : E("LIBRARY_PYTHON_PATH",os.path.abspath(".")),
		}

	def __init__( self, config=None, components=[], pageServer=None, libraryServer=None):
		"""Creates a new webapp, setting the `isProduction` property if `$devmode` is enabled,
		creates the `${cache.path}`, `${data.path}` and `${cache.api.path}` if necessary` and
		registers the given `pageServer`, `libraryServer` and `components`. By default this
		module `PageServer` and `LibraryServer` will be instanciated."""
		Application.__init__(self,
			defaults  = self.DefaultConfig(),
			config    = config or APPNAME.lower(),
		)
		is_production = self.isProduction = (self.config("devmode")!=1)
		if not is_production:
			import ipdb
		for d in (self.config("cache.path"), self.config("data.path"), self.config("cache.api.path")):
			if not os.path.isdir(d):
				os.makedirs(d)
		if isinstance(API_CACHE, FileCache):
			API_CACHE.setPath(self.config("cache.api.path"))
		components = ([
			pageServer    or PageServer(),
			libraryServer or LibraryServer(
				self.config("library.path"),
				cache           = LIBRARY_CACHE,
				cacheAggregates = is_production,
				minify          = is_production,
				compress        = is_production,
				cacheDuration   = is_production and 60 * 60 or 0
			),
		] + components)
		self.register(*components)

# -----------------------------------------------------------------------------
#
# MAIN
#
# -----------------------------------------------------------------------------

def createApp(config=(APPNAME.lower() + ".conf")):
	"""Creates the application with given path as config file."""
	return WebApp(config)

def start( app=None, runCondition=True, method=STANDALONE ):
	"""Runs the given application (by default created by 'createApp()' as
	standalone."""
	if method == STANDALONE:
		info("Starting Web application")
	if app is None: app = createApp()
	name     = app.config("appname")
	lib_python_path = app.config("library.python.path")
	if method == STANDALONE:
		info(app.config())
		info(app.info())
	if not lib_python_path in sys.path:
		sys.path.insert(0, lib_python_path)
	else:
		return run(
			app          = app,
			name         = name,
			method       = method,
		)

# This is wrapper to make the module GUnicorn-compatible
APPLICATION = None
def application(environ, startReponse):
	global APPLICATION
	if not APPLICATION:
		APPLICATION = start(method=WSGI)
		for _ in ON_INIT: _(APPLICATION)
	app = APPLICATION.stack.app()
	return APPLICATION(environ, startReponse)

if __name__ == "__main__":
	start(method=STANDALONE)

# EOF - vim: tw=80 ts=4 sw=4 noet
