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
		return captiveHandler(request) or f(self, request, *args, **kwargs)
	functools.update_wrapper(wrapper, f)
	return wrapper

def setLoggedIn( request ):
	return request.cookie(CAPTIVE_COOKIE, "true")

def isLoggedIn( request ):
	return request.cookie(CAPTIVE_COOKIE) == "true"

def captiveHandler( request ):
	"""Processes the request and returns the appropriate response (if any),
	if the request was detected as a captive portal."""
	# Apple's Captive Network support
	# SEE: http://stackoverflow.com/questions/12151218/dealing-with-ios-captive-network-support
	if "CaptiveNetworkSupport" in request.header("User-Agent"):
		setLoggedIn(request)
		return request.respond("<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>")
	# If we're logged in already, we don't return anything, which should passs
	# the requestt to the wrapper
	elif isLoggedIn(request):
		return None
	# The generate_204 is generated on Android devices. We set the logged in
	# cookie and then return the 204 status with no content
	elif request.path() == "/generate_204":
		setLoggedIn(request)
		return request.respond(None, None, status=204)
	else:
		return None

# EOF - vim: ts=4 sw=4 noet
