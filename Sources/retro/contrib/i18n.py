# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 17-Dec-2012
# Last mod  : 17-Dec-2012
# -----------------------------------------------------------------------------

import re, functools

__doc__ = """
A set of classes of functions to detect languages and manage translations.
"""

DEFAULT_LANGUAGE = "en"
COOKIE_LANGUAGE  = "lang"

def guessLanguage( request ):
	"""Detects the language code associated with the given browser, either
	by detecting it from the browser info or by cookie."""
	lang = request.param("lang") or request.param("language")
	if lang and len(lang) == 2:
		return lang.lower()
	lang  = request.cookie(COOKIE_LANGUAGE)
	if lang and len(lang) == 2:
		return lang.lower()
	languages = request.environ("HTTP_ACCEPT_LANGUAGE")
	if languages:
		# NOTE: This is a bit botchy, as we'd be supposed to parse the q=X to
		# properly order the language, but we assume that languages are properly
		# ordered.
		# Accept-Language is like: 'fr,fr-fr;q=0.8,en-us;q=0.5,en;q=0.3'
		return languages.split(",")[0].split("-")[0].lower()
	return DEFAULT_LANGUAGE

def localize(handler):
	"""Decorator that detects if a language prefix (eg. '/en/' or '/fr/') is
	used, and if not, will redirect to the a prefixed path by detecting the
	language (and settig the language cookie `COOKIE_LANGUAGE`) if
	not already.

	You should use this decorator after the `@on` and `@expose`.
	"""
	@functools.wraps(handler)
	def wrapper(inst, request, lang, *args, **kwargs):
		if not lang:
			lang = guessLanguage(request)
			# Once guessed, set language for next requests
			request.cookie(COOKIE_LANGUAGE,lang)
			return request.redirect("/" + lang + request.path())
		return handler(inst, request, lang, *args, **kwargs)
	return wrapper

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
		for lang, value in languages.items(): v[lang] = value
		return cls

	@classmethod
	def Get( cls, key, lang ):
		if cls.ALL.has_key(key):
			v = cls.ALL[key]
			if v and lang in v:
				return v[lang]
		return None

# EOF - vim: tw=80 ts=4 sw=4 noet
