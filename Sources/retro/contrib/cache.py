#!/usr/bin/env python
# Encoding: iso-8859-1
# -----------------------------------------------------------------------------
# Project   : Retro - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 07-Nov-2007
# Last mod  : 17-May-2010
# -----------------------------------------------------------------------------

import os, stat, threading

# ------------------------------------------------------------------------------
#
# CACHE OBJECT
#
# ------------------------------------------------------------------------------

class MemoryCache:
	"""A simple cache system using a weighted LRU style dictionary."""

	def __init__( self, limit=100 ):
		self.data   = {}
		self.weight = 0
		self.limit  = 100
		self.lock   = threading.Lock()
		self.enabled = True

	def enable( self ):
		self.enabled = True

	def disable( self ):
		self.enabled = False

	def get( self, key ):
		d = self.data.get(key)
		if d:
			# We increase the hit count
			d[1] += 1
			return d[2]
		else:
			return None

	def has( self, key ):
		res = self.data.get(key)
		return res and True

	def set( self, key, data, weight=1 ):
		self.lock.acquire()
		if self.data.has_key(key):
			# We update the data if it's already there
			previous       = self.data[key]
			self.weight   -= previous[0]
			previous[0]    = weight
			previous[2]    = data
			self.data[key] = previous
		else:
			self.data[key] = [weight, 0, data]
			self.weight   += weight
		self.lock.release()
		if self.weight > self.limit:
			self.cleanup()

	def remove( self, key ):
		if self.has(key):
			del self.data[key]

	def cleanup( self ):
		self.lock.acquire()
		items = self.data.items()
		# FIXME: This is slooooow
		# We compare the hits
		items.sort(lambda a,b:cmp(a[1][1], b[1][1]))
		i = 0
		while self.weight > self.limit and i < len(items):
			del self.data[items[i][0]]
			self.weight -= items[i][1][0]
			i += 1
		self.lock.release()

class FileCache:
	"""A simplistic filesystem-based cache"""

	def __init__( self, path ):
		self.path = path
		self.enabled = True
		assert os.path.exists(path)
		assert os.path.isdir(path)

	def get( self, key ):
		if self.has(key):
			f = file(key + ".cache", 'r')
			c = f.read()
			f.close()
			return c
		else:
			return None

	def set( self, key, data ):
		f = file(key + ".cache", 'w')
		f.write(data)
		f.close()

	def remove( self, key):
		if self.has(key):
			os.unlink(key + ".cache")

	def has( self, key ):
		return os.path.exists(key + ".cache")

class SignatureCache:
	"""A specific type of cache that takes a signature."""

	def __init__( self ):
		# TODO: Add cache clearing functions
		self._cachedSig  = {}
		self._cachedData = {}
		self.enabled = True

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

	def get( self, tag, sig=0 ):
		if self._cachedSig.get(tag) != sig:
			return True, None
		else:
			return False, self._cachedData.get(tag)

	def put( self, tag, sig, data ):
		self._cachedSig[tag]  = sig
		self._cachedData[tag] = data

	def filemod( self, path, *args ):
		return  os.stat(path)[stat.ST_MTIME]

# EOF - vim: tw=80 ts=4 sw=4 noet
