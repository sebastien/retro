#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project           : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author            : Sebastien Pierre                    <sebastien@ffctn.com>
# License           : Revised BSD License
# -----------------------------------------------------------------------------
# Creation date     : 2015-07-21
# Last modification : 2015-08-11
# -----------------------------------------------------------------------------

import functools

CAPTIVE_COOKIE = "captive.loggedin"

def captive(f):
	"""A decorator that a captive portal query and returns the corresponding
	response."""
	def wrapper( self, request, *args, **kwargs ):
		if not captiveHandler(request): return f(self, request, *args, **kwargs)
	functools.update_wrapper(wrapper, f)
	return wrapper

def setLoggedIn( request ):
	return request.setCookie(CAPTIVE_COOKIE, "true")

def isLoggedIn( request ):
	return request.cookie(CAPTIVE_COOKIE) == "true"

def captiveHandler( request ):
	"""Processes the request and returns the appropriate response (if any),
	if the request was detected as a captive portal."""
	# Apple's Captive Network support
	# SEE: http://stackoverflow.com/questions/12151218/dealing-with-ios-captive-network-support
	if "CaptiveNetworkSupport" in request.header("User-Agent"):
		return setLoggedIn(request.respond("<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"))
	if isLoggedIn(request):
		return None
	# The generate_204 is generated on Android devices
	if request.path() == "/generate_204":
		return setLoggedIn(request.respond("OK", status=204).setCookie(CAPTIVE_COOKIE, "true"))
	return None

# EOF - vim: ts=4 sw=4 noet
