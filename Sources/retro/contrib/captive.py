#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project           : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author            : Sebastien Pierre                    <sebastien@ffctn.com>
# License           : Revised BSD License
# -----------------------------------------------------------------------------
# Creation date     : 2015-07-21
# Last modification : 2015-07-21
# -----------------------------------------------------------------------------

def captive(f):
	"""A decorator that a captive portal query and returns the corresponding
	response."""
	def wrapper( request, *args, **kwargs ):
		if not captiveHandler(request): return f(request, *args, **kwargs)
	functools.update_wrapper(wrapper, f)
	return wrapper

def captiveHandler( request ):
	"""Processes the request and returns the appropriate responese (if any),
	if the request was detected as a captive portal."""
	# Apple's Captive Network support
	# SEE: http://stackoverflow.com/questions/12151218/dealing-with-ios-captive-network-support
	if "CaptiveNetworkSupport" in request.header("User-Agent"):
		return request.respond("<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>")
	# The generate_204 is generated on Android devices
	if request.path() == "/generate_204":
		return request.respond("OK", status=204)
	return None

# EOF - vim: ts=4 sw=4 noet
