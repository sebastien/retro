#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Retro - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 07-Nov-2007
# Last mod  : 07-Nov-2007
# -----------------------------------------------------------------------------

import os, stat

# ------------------------------------------------------------------------------
#
# CACHE OBJECT
#
# ------------------------------------------------------------------------------

class Cache:

	def __init__( self ):
		# TODO: Add cache clearing functions
		self._cachedSig  = {}
		self._cachedData = {}

	def cache( self, signatureFunction  ):
		"""A decorator that will memoize the result of the function as long as
		the 'signatureFunction' returns the same result. The signatureFunction
		takes the same arguments as the cached/decorated function."""
		def decorator(function):
			function_tag = repr(function)
			def cache_wrapper(*args):
				signature = signatureFunction(*args)
				if self._cachedSig.get(function_tag) != signatureFunction:
					result = function(*args)
					self._cachedSig [function_tag] = signature
					self._cachedData[function_tag] = result
					return result
				else:
					result = ielf._cachedData[function_tag]
					return result

	def get( self, tag, sig ):
		if self._cachedSig.get(tag) != sig:
			return True, None
		else:
			return False, self._cachedData.get(tag)

	def put( self, tag, sig, data ):
		self._cachedSig[tag]  = sig
		self._cachedData[tag] = data

	def filemod( self, path, *args ):
		return  os.stat(path)[stat.ST_MTIME]

# EOF
