#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project           : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author            : Sebastien Pierre                    <sebastien@ffctn.com>
# License           : Revised BSD License
# -----------------------------------------------------------------------------
# Creation date     : 2015-07-21
# Last modification : 2020-03-30
# -----------------------------------------------------------------------------

import retro.core,types
from   retro.web import updateWrapper

# SEE: http://stackoverflow.com/questions/16386148/why-browser-do-not-follow-redirects-using-xmlhttprequest-and-cors/20854800#20854800

def cors(allowAll=True):
	"""A decorator for a request handler that will ensure
	response."""
	def decorator(f):
		def wrapper( *args, **kwargs ):
			response = f(*args, **kwargs)
			assert not isinstance(response, types.CoroutineType), "Handler is async, use '@acors' instead"
			return setCORSHeaders(response, args[1].header("Origin"), allowAll=allowAll)
		return updateWrapper(wrapper, f)
	return decorator

def acors(allowAll=True):
	"""A decorator for a request handler that will ensure
	response."""
	def decorator(f):
		async def wrapper( *args, **kwargs ):
			coro = f(*args, **kwargs)
			assert isinstance(coro, types.CoroutineType), "Handler is async, use '@acors' instead"
			response = await coro
			return setCORSHeaders(response, args[1].header("Origin"), allowAll=allowAll)
		return updateWrapper(wrapper, f)
	return decorator



def setCORSHeaders(r, origin=None, allowAll=True):
	"""Takes the given request or response, and
	return (a response) with the CORS headers set
	properly.

	See <https://en.wikipedia.org/wiki/Cross-origin_resource_sharing>
	"""
	if isinstance(r, retro.core.Request):
		origin = origin or r.header("Origin")
		r = r.respond()
	# SEE: https://remysharp.com/2011/04/21/getting-cors-working
	# If the request returns a 0 status code, it's likely because of CORS
	r.setHeader("Access-Control-Allow-Origin", origin if origin and not allowAll else "*")
	r.setHeader("Access-Control-Allow-Headers", "X-Requested-With")
	r.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, UPDATE")
	return r

# EOF - vim: ts=4 sw=4 noet
