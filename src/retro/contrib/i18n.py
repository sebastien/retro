# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 17-Dec-2012
# Last mod  : 06-Aug-2014
# -----------------------------------------------------------------------------

import re, functools, logging
from   retro.core import Request, IS_PYTHON3

__doc__ = """
A set of classes of functions to detect languages and manage translations.
"""

if IS_PYTHON3: unicode = str

DEFAULT_LANGUAGE = "en"
COOKIE_LANGUAGE  = "lang"
LOCALIZE_SKIP    = ["lib","api"]
LOCALES          = []
ENABLED          = True
STRINGS          = {}
RE_LANG          = re.compile("^\w\w(\-\w\w)?$")
RE_LANG_PREFIX   = re.compile("^/?(\w\w(\-\w\w)?)/?$")

def disable():
	global ENABLED
	ENABLED = False

def ensable():
	global ENABLED
	ENABLED = True

def setLocales( locales ):
	global LOCALES
	LOCALES = [] + locales
	return LOCALES

def T(text, lang=None ):
	# FIXME: Use Translations instead
	if lang is None: lang = DEFAULT_LANGUAGE
	if isinstance(lang, Request): lang = guessLanguage(lang)
	if isinstance(text, dict):
		return text.get(lang) or None
	if text not in STRINGS: STRINGS.setdefault(text, {})
	if lang in STRINGS[text]:
		return STRINGS[text][lang]
	elif lang == DEFAULT_LANGUAGE:
		return text
	logging.error("Missing {0} translation for string: {1}".format(lang, repr(text)))
	return text

def guessLanguage( request ):
	"""Detects the language code associated with the given browser, either
	by detecting it from the browser info or by cookie."""
	if type(request) in (str, unicode):
		lang = request
		lang = lang.split("-")[0].lower().strip()
		if lang in LOCALES:
			return lang
		else:
			return DEFAULT_LANGUAGE
	elif not request:
		return DEFAULT_LANGUAGE
	else:
		lang = request.param("lang") or request.param("language")
		if lang and RE_LANG.match(lang):
			lang = lang.split("-")[0].lower().strip()
			if lang in LOCALES:
				return lang
			else:
				return DEFAULT_LANGUAGE
		lang  = request.cookie(COOKIE_LANGUAGE)
		if lang and RE_LANG.match(lang):
			lang = lang.split("-")[0].lower().strip()
			if lang in LOCALES:
				return lang
			else:
				return DEFAULT_LANGUAGE
		languages = request.environ("HTTP_ACCEPT_LANGUAGE")
		if languages:
			# NOTE: This is a bit botchy, as we'd be supposed to parse the q=X to
			# properly order the language, but we assume that languages are properly
			# ordered.
			# Accept-Language is like: 'fr,fr-fr;q=0.8,en-us;q=0.5,en;q=0.3'
			languages = [_.split("-")[0].strip().lower() for _ in languages.split(",")]
			if not LOCALES:
				return languages[0]
			else:
				for language in languages:
					if language in LOCALES:
						return language
				return DEFAULT_LANGUAGE
	return DEFAULT_LANGUAGE

def localize(handler):
	"""Decorator that detects if a language prefix (eg. '/en/' or '/fr/') is
	used, and if not, will redirect to the a prefixed path by detecting the
	language (and settig the language cookie `COOKIE_LANGUAGE`) if
	not already.

	If the `lang` query string is set, the localize function will automatically
	redirect.

	You should use this decorator after the `@on` and `@expose` (meaning it
	needs to be the last on the chain of decorators.
	"""
	@functools.wraps(handler)
	def retro_i18n_localize_wrapper(inst, request, lang=None, *args, **kwargs):
		app = request.environ("retro.app")
		# NOTE: This should be super optimized as it's called each time
		if ENABLED and app and app.config("i18n.localize") is not False:
			prefix = app.config("base")
			path   = request.path()
			if path.startswith(prefix): path = path[len(prefix):]
			if path and path[0] != "/": path = "/" + path
			if not lang:
				# There's no language specified, so we have to guess it
				lang = request.param("lang") or lang
				for skip in LOCALIZE_SKIP:
					if path.startswith(skip):
						return handler(inst, request, lang, *args, **kwargs)
				lang = guessLanguage(request)
				# Once guessed, set language for next requests
				request.cookie(COOKIE_LANGUAGE,lang)
				# if path is like /LL or /LL-LL (ex /en /en-ca)
				m    = RE_LANG_PREFIX.match(path)
				path = prefix + (m.group(1) + "/index" if m else lang + path)
				return request.redirect(path)
			elif request.param("lang") and request.param("lang") != lang:
				# We override the current language, so we redirect to the url
				l    = request.param("lang")
				if lang:
					path = path.split(lang, 1)
					path.insert(1, l)
					path = "".join(path).replace("lang=" +  l, "").replace("&&","&")
					while path.endswith("?"): path = path[:-1]
				else:
					path = prefix + l + path
				request.cookie(COOKIE_LANGUAGE,l)
				return request.redirect(path)
		return handler(inst, request, lang, *args, **kwargs)
	return retro_i18n_localize_wrapper

# -----------------------------------------------------------------------------
#
# TRANSLATIONS
#
# -----------------------------------------------------------------------------

class Translations:
	"""A class that allows to get and set translations"""

	ALL = {}

	@classmethod
	def Add( cls, key, **languages ):
		v = cls.ALL.setdefault(key,{})
		for lang, value in list(languages.items()): v[lang] = value
		return cls

	@classmethod
	def Get( cls, key, lang ):
		if key in cls.ALL:
			v = cls.ALL[key]
			if v and lang in v:
				return v[lang]
		return None

# EOF - vim: tw=80 ts=4 sw=4 noet
